"""Synchronization orchestration."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Optional, Sequence

from sqlalchemy.orm import Session

from app.clients.sirene_client import SireneClient
from app.config import Settings, get_settings
from app.db import models
from app.services.alert_service import AlertService
from app.services.establishment_mapper import extract_fields
from app.utils.dates import parse_datetime
from app.utils.hashing import sha256_digest

_LOGGER = logging.getLogger(__name__)


@dataclass
class SyncContext:
    session: Session
    run: models.SyncRun
    state: models.SyncState
    client: SireneClient
    settings: Settings


class SyncService:
    """Run full and incremental synchronizations against the Sirene API."""

    def __init__(self) -> None:
        self._settings = get_settings()

    def run_full_sync(self, session: Session, *, resume: bool = True) -> models.SyncRun:
        scope_key = self._settings.sync.full_scope_key
        run = self._start_run(session, scope_key=scope_key, run_type="full", resume=resume)
        client = SireneClient()
        state = self._get_or_create_state(session, scope_key)
        context = SyncContext(session=session, run=run, state=state, client=client, settings=self._settings)
        try:
            self._collect_full(context, resume=resume)
            self._finish_run(run, state)
            session.flush()
        except Exception:
            run.status = "failed"
            run.finished_at = datetime.utcnow()
            session.flush()
            client.close()
            raise
        client.close()
        return run

    def run_incremental_sync(self, session: Session) -> Optional[models.SyncRun]:
        scope_key = self._settings.sync.incremental_scope_key
        client = SireneClient()
        state = self._get_or_create_state(session, scope_key)
        infos = client.get_informations()
        collection = self._extract_collection_info(infos, "etablissements")
        if not collection:
            _LOGGER.warning("Impossible de récupérer les métadonnées 'etablissements' depuis le service informations.")
            client.close()
            return None

        latest_treated = parse_datetime(collection.get("dateDernierTraitementMaximum"))
        if not latest_treated:
            _LOGGER.warning("dateDernierTraitementMaximum absente ou invalide dans le service informations.")
            client.close()
            return None

        if state.last_treated_max and latest_treated <= state.last_treated_max:
            _LOGGER.info("Aucune mise à jour détectée depuis la dernière exécution (%s).", state.last_treated_max)
            client.close()
            return None

        run = self._start_run(session, scope_key=scope_key, run_type="incremental", resume=True)
        run.notes = f"dateDernierTraitementMaximum: {latest_treated.isoformat()}"
        run.query_checksum = self._incremental_query_checksum(state)

        context = SyncContext(session=session, run=run, state=state, client=client, settings=self._settings)
        try:
            self._collect_incremental(context, latest_treated)
            state.last_treated_max = latest_treated
            self._finish_run(run, state)
            session.flush()
        except Exception:
            run.status = "failed"
            run.finished_at = datetime.utcnow()
            session.flush()
            client.close()
            raise
        client.close()
        return run

    def _start_run(self, session: Session, *, scope_key: str, run_type: str, resume: bool) -> models.SyncRun:
        run = models.SyncRun(scope_key=scope_key, run_type=run_type, status="running")
        session.add(run)
        if resume:
            last_run = (
                session.query(models.SyncRun)
                .filter(models.SyncRun.scope_key == scope_key, models.SyncRun.status == "success")
                .order_by(models.SyncRun.started_at.desc())
                .first()
            )
            if last_run:
                run.resumed_from_run_id = last_run.id
        session.flush()
        return run

    def _get_or_create_state(self, session: Session, scope_key: str) -> models.SyncState:
        state = session.get(models.SyncState, scope_key)
        if not state:
            state = models.SyncState(scope_key=scope_key)
            session.add(state)
            session.flush()
        return state

    def _collect_full(self, context: SyncContext, *, resume: bool) -> None:
        state = context.state
        query = self._build_restaurant_query()
        checksum = sha256_digest(query)
        context.run.query_checksum = checksum

        if state.query_checksum and state.query_checksum != checksum:
            _LOGGER.info("La requête a changé, réinitialisation du curseur.")
            state.last_cursor = None
            state.cursor_completed = False
        state.query_checksum = checksum

        if not resume:
            state.last_cursor = None
            state.cursor_completed = False

        champs = self._build_fields_parameter()
        cursor_value = state.last_cursor if state.last_cursor and not state.cursor_completed else "*"

        new_entities_total: list[models.Establishment] = []

        while True:
            payload = context.client.search_establishments(
                query=query,
                nombre=self._settings.sirene.page_size,
                curseur=cursor_value,
                champs=champs,
            )
            header = payload.get("header", {})
            etablissements = payload.get("etablissements", [])
            context.run.api_call_count += 1
            context.run.fetched_records += len(etablissements)

            new_entities = self._upsert_establishments(context.session, etablissements)
            context.run.created_records += len(new_entities)
            if context.run.run_type != "full":
                new_entities_total.extend(new_entities)

            cursor_value = header.get("curseurSuivant")
            state.last_cursor = cursor_value
            state.last_total = header.get("total")
            state.last_synced_at = datetime.utcnow()
            context.session.flush()

            if not etablissements or not cursor_value or cursor_value == header.get("curseur"):
                state.cursor_completed = True
                break

        state.last_successful_run_id = context.run.id
        if new_entities_total and context.run.run_type != "full":
            AlertService(context.session, context.run).create_alerts(new_entities_total)

    def _collect_incremental(self, context: SyncContext, latest_treated: datetime) -> None:
        state = context.state
        champs = self._build_fields_parameter()
        start = state.last_treated_max or (latest_treated - timedelta(days=1))
        # Slightly extend the range to avoid missing borderline updates.
        start_value = (start - timedelta(minutes=5)).isoformat() if start else None
        end_value = (latest_treated + timedelta(seconds=1)).isoformat()

        query = self._build_incremental_query(start_value, end_value)
        checksum = sha256_digest(query)
        context.run.query_checksum = checksum

        cursor_value = "*"
        state.cursor_completed = False

        new_entities_total: list[models.Establishment] = []

        while True:
            payload = context.client.search_establishments(
                query=query,
                nombre=self._settings.sirene.page_size,
                curseur=cursor_value,
                champs=champs,
            )
            header = payload.get("header", {})
            etablissements = payload.get("etablissements", [])
            context.run.api_call_count += 1
            context.run.fetched_records += len(etablissements)

            new_entities = self._upsert_establishments(context.session, etablissements)
            context.run.created_records += len(new_entities)
            new_entities_total.extend(new_entities)

            cursor_value = header.get("curseurSuivant")
            state.last_cursor = cursor_value
            state.last_total = header.get("total")
            state.last_synced_at = datetime.utcnow()
            context.session.flush()

            if not etablissements or not cursor_value or cursor_value == header.get("curseur"):
                state.cursor_completed = True
                break

        state.last_successful_run_id = context.run.id
        if new_entities_total:
            AlertService(context.session, context.run).create_alerts(new_entities_total)

    def _finish_run(self, run: models.SyncRun, state: models.SyncState) -> None:
        run.status = "success"
        run.finished_at = datetime.utcnow()
        state.last_successful_run_id = run.id

    def _build_restaurant_query(self) -> str:
        naf_query = " OR ".join(
            f"activitePrincipaleEtablissement:{code}" for code in self._settings.sirene.restaurant_naf_codes
        )
        if len(self._settings.sirene.restaurant_naf_codes) > 1:
            naf_query = f"({naf_query})"
        base = f"periode(({naf_query}) AND etatAdministratifEtablissement:A)"
        return base

    def _build_incremental_query(self, start_iso: Optional[str], end_iso: str) -> str:
        clauses = []
        if start_iso:
            clauses.append(
                f"dateDernierTraitementEtablissement:[{start_iso} TO {end_iso}]"
            )
            clauses.append(
                f"dateDernierTraitementUniteLegale:[{start_iso} TO {end_iso}]"
            )
        else:
            clauses.append(f"dateDernierTraitementEtablissement:[* TO {end_iso}]")
            clauses.append(f"dateDernierTraitementUniteLegale:[* TO {end_iso}]")
        treated_clause = " OR ".join(clauses)
        return f"({treated_clause}) AND {self._build_restaurant_query()}"

    def _build_fields_parameter(self) -> str:
        fields = {
            "identificationStandardEtablissement",
            "denominationUsuelleEtablissement",
            "enseigne1Etablissement",
            "enseigne2Etablissement",
            "enseigne3Etablissement",
            "denominationUniteLegale",
            "denominationUsuelle1UniteLegale",
            "denominationUsuelle2UniteLegale",
            "denominationUsuelle3UniteLegale",
            "nomUsageUniteLegale",
            "nomUniteLegale",
            "prenom1UniteLegale",
            "libelleActivitePrincipaleEtablissement",
        }
        return ",".join(sorted(fields))

    def _upsert_establishments(self, session: Session, etablissements: Sequence[dict[str, object]]) -> list[models.Establishment]:
        new_entities: list[models.Establishment] = []
        now = datetime.utcnow()
        for payload in etablissements:
            fields = extract_fields(payload)
            siret = fields.get("siret")
            if not siret:
                continue
            entity = session.get(models.Establishment, siret)
            if entity:
                for key, value in fields.items():
                    setattr(entity, key, value)
                entity.last_seen_at = now
            else:
                entity = models.Establishment(**fields)
                entity.first_seen_at = now
                entity.last_seen_at = now
                session.add(entity)
                new_entities.append(entity)
        session.flush()
        return new_entities

    def _extract_collection_info(self, payload: dict[str, object], name: str) -> Optional[dict[str, object]]:
        if not isinstance(payload, dict):
            return None
        possible_keys = ["collections", "collection", "datasets", "data"]
        for key in possible_keys:
            value = payload.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and item.get("nom") == name:
                        return item
                    if isinstance(item, dict) and item.get("name") == name:
                        return item
                    if isinstance(item, dict) and item.get("collection") == name:
                        return item
                    nested = self._extract_collection_info(item, name)
                    if nested:
                        return nested
            elif isinstance(value, dict):
                nested = self._extract_collection_info(value, name)
                if nested:
                    return nested
        if name in payload and isinstance(payload[name], dict):
            return payload[name]
        for item in payload.values():
            if isinstance(item, dict):
                nested = self._extract_collection_info(item, name)
                if nested:
                    return nested
        return None

    def _incremental_query_checksum(self, state: models.SyncState) -> str:
        base = f"{state.scope_key}:{state.last_treated_max.isoformat() if state.last_treated_max else 'none'}"
        return sha256_digest(base)
