"""Synchronization orchestration."""
from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable, Optional, Sequence
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.clients.sirene_client import SireneClient
from app.config import Settings, get_settings
from app.db import models
from app.db.session import session_scope
from app.services.alert_service import AlertService
from app.services.establishment_mapper import extract_fields
from app.utils.dates import parse_datetime, subtract_months
from app.utils.hashing import sha256_digest

_LOGGER = logging.getLogger(__name__)


def _log_and_print(level: int, message: str, *args: object) -> None:
    """Log the message and mirror it to stdout for realtime visibility."""

    rendered = message % args if args else message
    print(rendered, flush=True)
    _LOGGER.log(level, message, *args)


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    stripped = "".join(char for char in normalized if not unicodedata.combining(char))
    return stripped.lower()


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

    @property
    def settings(self) -> Settings:
        """Expose cached settings (useful for orchestrator helpers)."""

        return self._settings

    def run_full_sync(
        self,
        session: Session,
        *,
        resume: bool = True,
        max_records: Optional[int] = None,
    ) -> models.SyncRun:
        run, state = self._initialize_full_run(
            session,
            resume=resume,
            max_records=max_records,
            status="running",
        )

        client = SireneClient()
        context = SyncContext(session=session, run=run, state=state, client=client, settings=self._settings)
        try:
            self._collect_full(context, resume=resume, max_records=max_records)
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
        prepared = self._prepare_incremental_run(session, status="running")
        if not prepared:
            return None

        run, state, latest_treated, creation_floor = prepared
        client = SireneClient()
        context = SyncContext(session=session, run=run, state=state, client=client, settings=self._settings)
        try:
            self._collect_incremental(context, latest_treated, creation_floor)
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

    def prepare_full_run(
        self,
        session: Session,
        *,
        resume: bool = True,
        max_records: Optional[int] = None,
    ) -> models.SyncRun:
        run, _state = self._initialize_full_run(
            session,
            resume=resume,
            max_records=max_records,
            status="pending",
        )
        return run

    def prepare_incremental_run(self, session: Session) -> Optional[tuple[models.SyncRun, datetime, date]]:
        prepared = self._prepare_incremental_run(session, status="pending")
        if not prepared:
            return None
        run, _state, latest_treated, creation_floor = prepared
        return run, latest_treated, creation_floor

    def execute_full_run(self, run_id: UUID, *, resume: bool, max_records: Optional[int]) -> None:
        try:
            with session_scope() as session:
                run = session.get(models.SyncRun, run_id)
                if not run:
                    _log_and_print(logging.WARNING, "Run %s introuvable pour la synchronisation complète.", run_id)
                    return
                state = self._get_or_create_state(session, run.scope_key)
                run.status = "running"
                run.started_at = datetime.utcnow()
                session.flush()

                _log_and_print(logging.INFO, "Synchronisation complète démarrée (run=%s)", run.id)

                client = SireneClient()
                context = SyncContext(session=session, run=run, state=state, client=client, settings=self._settings)
                try:
                    effective_max_records = max_records if max_records is not None else run.max_records
                    self._collect_full(context, resume=resume, max_records=effective_max_records)
                    self._finish_run(run, state)
                    session.flush()
                    _log_and_print(logging.INFO, "Synchronisation complète terminée (run=%s, créés=%s)", run.id, run.created_records)
                finally:
                    client.close()
        except Exception:
            _LOGGER.exception("Synchronisation complète asynchrone échouée (run=%s)", run_id)
            print(f"Synchronisation complète asynchrone échouée (run={run_id})", flush=True)
            with session_scope() as session:
                run = session.get(models.SyncRun, run_id)
                if run:
                    run.status = "failed"
                    run.finished_at = datetime.utcnow()
                    session.flush()

    def execute_incremental_run(self, run_id: UUID, *, latest_treated: datetime, creation_floor: date) -> None:
        try:
            with session_scope() as session:
                run = session.get(models.SyncRun, run_id)
                if not run:
                    _log_and_print(logging.WARNING, "Run %s introuvable pour la synchronisation incrémentale.", run_id)
                    return
                state = self._get_or_create_state(session, run.scope_key)
                run.status = "running"
                run.started_at = datetime.utcnow()
                session.flush()

                _log_and_print(logging.INFO, "Synchronisation incrémentale démarrée (run=%s)", run.id)

                client = SireneClient()
                context = SyncContext(session=session, run=run, state=state, client=client, settings=self._settings)
                try:
                    self._collect_incremental(context, latest_treated, creation_floor)
                    state.last_treated_max = latest_treated
                    self._finish_run(run, state)
                    session.flush()
                    _log_and_print(logging.INFO, "Synchronisation incrémentale terminée (run=%s, créés=%s)", run.id, run.created_records)
                finally:
                    client.close()
        except Exception:
            _LOGGER.exception("Synchronisation incrémentale asynchrone échouée (run=%s)", run_id)
            print(f"Synchronisation incrémentale asynchrone échouée (run={run_id})", flush=True)
            with session_scope() as session:
                run = session.get(models.SyncRun, run_id)
                if run:
                    run.status = "failed"
                    run.finished_at = datetime.utcnow()
                    session.flush()

    def has_active_run(self, session: Session, scope_key: str) -> bool:
        active_statuses = ("running", "pending")
        existing = (
            session.query(models.SyncRun.id)
            .filter(models.SyncRun.scope_key == scope_key, models.SyncRun.status.in_(active_statuses))
            .first()
        )
        return existing is not None

    def _initialize_full_run(
        self,
        session: Session,
        *,
        resume: bool,
        max_records: Optional[int],
        status: str,
    ) -> tuple[models.SyncRun, models.SyncState]:
        scope_key = self._settings.sync.full_scope_key
        run = self._start_run(
            session,
            scope_key=scope_key,
            run_type="full",
            resume=resume,
            initial_status=status,
        )
        if max_records is not None:
            if max_records < 1:
                raise ValueError("max_records must be a positive integer when provided.")
            run.max_records = max_records
        state = self._get_or_create_state(session, scope_key)
        session.flush()
        return run, state

    def _determine_creation_floor(self, session: Session) -> date:
        buffer_days = max(self._settings.sync.incremental_creation_window_days, 1)
        buffer_delta = timedelta(days=buffer_days)
        today = datetime.utcnow().date()
        floor = today - buffer_delta

        max_creation = session.query(func.max(models.Establishment.date_creation)).scalar()
        if max_creation:
            capped_max = min(max_creation, today)
            candidate = capped_max - buffer_delta
            if candidate > floor:
                floor = candidate

        full_window_floor = subtract_months(today, self._settings.sync.full_sync_months_back)
        if full_window_floor > today:
            full_window_floor = today
        if full_window_floor > floor:
            floor = full_window_floor

        if floor > today:
            floor = today

        return floor

    def _prepare_incremental_run(
        self,
        session: Session,
        *,
        status: str,
    ) -> Optional[tuple[models.SyncRun, models.SyncState, datetime, date]]:
        scope_key = self._settings.sync.incremental_scope_key
        state = self._get_or_create_state(session, scope_key)
        creation_floor = self._determine_creation_floor(session)
        client = SireneClient()
        try:
            infos = client.get_informations()
        finally:
            client.close()

        collection = self._extract_collection_info(infos, "etablissements")
        if not collection:
            _LOGGER.warning("Impossible de récupérer les métadonnées 'etablissements' depuis le service informations.")
            return None

        latest_treated = parse_datetime(collection.get("dateDernierTraitementMaximum"))
        if not latest_treated:
            _LOGGER.warning("dateDernierTraitementMaximum absente ou invalide dans le service informations.")
            return None

        if state.last_treated_max and latest_treated <= state.last_treated_max:
            _LOGGER.info("Aucune mise à jour détectée depuis la dernière exécution (%s).", state.last_treated_max)
            return None

        run = self._start_run(
            session,
            scope_key=scope_key,
            run_type="incremental",
            resume=True,
            initial_status=status,
        )
        run.notes = f"dateDernierTraitementMaximum: {latest_treated.isoformat()}"
        run.query_checksum = self._incremental_query_checksum(state)
        session.flush()
        return run, state, latest_treated, creation_floor

    def _start_run(
        self,
        session: Session,
        *,
        scope_key: str,
        run_type: str,
        resume: bool,
        initial_status: str,
    ) -> models.SyncRun:
        run = models.SyncRun(scope_key=scope_key, run_type=run_type, status=initial_status)
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

    def _collect_full(self, context: SyncContext, *, resume: bool, max_records: Optional[int]) -> None:
        state = context.state
        months_back = max(self._settings.sync.full_sync_months_back, 1)
        since_creation = subtract_months(datetime.utcnow().date(), months_back)
        query = self._build_restaurant_query(since_creation=since_creation)
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
        tri = "dateCreationEtablissement desc"

        new_entities_total: list[models.Establishment] = []

        while True:
            page_size = self._settings.sirene.page_size
            if max_records is not None:
                remaining = max_records - context.run.fetched_records
                if remaining <= 0:
                    break
                page_size = min(page_size, remaining)

            payload = context.client.search_establishments(
                query=query,
                nombre=page_size,
                curseur=cursor_value,
                champs=champs,
                date=self._settings.sirene.current_period_date,
                tri=tri,
            )
            header = payload.get("header", {})
            etablissements = payload.get("etablissements", [])
            context.run.api_call_count += 1
            context.run.fetched_records += len(etablissements)

            new_entities = self._upsert_establishments(context.session, etablissements, context.run.id)
            context.run.created_records += len(new_entities)
            if context.run.run_type != "full":
                new_entities_total.extend(new_entities)

            cursor_value = header.get("curseurSuivant")
            state.last_cursor = cursor_value
            total_value = header.get("total")
            try:
                state.last_total = int(total_value) if total_value is not None else state.last_total
            except (TypeError, ValueError):
                _LOGGER.debug("Valeur 'total' non exploitable: %s", total_value)
            state.last_synced_at = datetime.utcnow()
            context.session.flush()

            if max_records is not None and context.run.fetched_records >= max_records:
                state.cursor_completed = False
                break

            if not etablissements or not cursor_value or cursor_value == header.get("curseur"):
                state.cursor_completed = True
                break

        state.last_successful_run_id = context.run.id
        if new_entities_total and context.run.run_type != "full":
            AlertService(context.session, context.run).create_alerts(new_entities_total)

    def _collect_incremental(self, context: SyncContext, latest_treated: datetime, creation_floor: date) -> None:
        state = context.state
        champs = self._build_fields_parameter()
        start = state.last_treated_max or (latest_treated - timedelta(days=1))
        # Slightly extend the range to avoid missing borderline updates.
        start_value = (start - timedelta(minutes=5)).isoformat() if start else None
        end_value = (latest_treated + timedelta(seconds=1)).isoformat()

        query = self._build_incremental_query(start_value, end_value, creation_floor)
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
                date=self._settings.sirene.current_period_date,
            )
            header = payload.get("header", {})
            etablissements = payload.get("etablissements", [])
            context.run.api_call_count += 1
            context.run.fetched_records += len(etablissements)

            new_entities = self._upsert_establishments(context.session, etablissements, context.run.id)
            context.run.created_records += len(new_entities)
            new_entities_total.extend(new_entities)

            cursor_value = header.get("curseurSuivant")
            state.last_cursor = cursor_value
            total_value = header.get("total")
            try:
                state.last_total = int(total_value) if total_value is not None else state.last_total
            except (TypeError, ValueError):
                _LOGGER.debug("Valeur 'total' non exploitable: %s", total_value)
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

    def _build_restaurant_query(self, *, since_creation: Optional[date] = None) -> str:
        naf_terms = [f"activitePrincipaleEtablissement:{code}" for code in self._settings.sirene.restaurant_naf_codes]
        naf_query = " OR ".join(naf_terms)
        if len(naf_terms) > 1:
            naf_query = f"({naf_query})"
        period_clause = f"periode({naf_query} AND etatAdministratifEtablissement:A)"
        if since_creation:
            creation_clause = f"dateCreationEtablissement:[{since_creation.isoformat()} TO *]"
            return f"{period_clause} AND {creation_clause}"
        return period_clause

    def _build_incremental_query(self, start_iso: Optional[str], end_iso: str, creation_floor: Optional[date]) -> str:
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
        return f"({treated_clause}) AND {self._build_restaurant_query(since_creation=creation_floor)}"

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
        }
        return ",".join(sorted(fields))

    def _upsert_establishments(
        self,
        session: Session,
        etablissements: Sequence[dict[str, object]],
        run_id: UUID,
    ) -> list[models.Establishment]:
        new_entities: list[models.Establishment] = []
        now = datetime.utcnow()
        for payload in etablissements:
            fields = extract_fields(payload)
            siret = fields.get("siret")
            if not siret:
                continue
            if fields.get("etat_administratif") != "A":
                existing = session.get(models.Establishment, siret)
                if existing:
                    session.delete(existing)
                continue
            entity = session.get(models.Establishment, siret)
            if entity:
                for key, value in fields.items():
                    setattr(entity, key, value)
                entity.last_seen_at = now
                entity.last_run_id = run_id
            else:
                fields["created_run_id"] = run_id
                fields["last_run_id"] = run_id
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
        normalized_target = _normalize_text(name)

        def matches(candidate: object) -> bool:
            if not isinstance(candidate, str):
                return False
            return _normalize_text(candidate) == normalized_target

        dates_updates = payload.get("datesDernieresMisesAJourDesDonnees")
        if isinstance(dates_updates, list):
            for item in dates_updates:
                if isinstance(item, dict) and matches(item.get("collection")):
                    return item

        possible_keys = ["collections", "collection", "datasets", "data"]
        for key in possible_keys:
            value = payload.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        if any(matches(item.get(field)) for field in ("nom", "name", "collection")):
                            return item
                    nested = self._extract_collection_info(item, name)
                    if nested:
                        return nested
            elif isinstance(value, dict):
                nested = self._extract_collection_info(value, name)
                if nested:
                    return nested
        for key, nested_value in payload.items():
            if matches(key) and isinstance(nested_value, dict):
                return nested_value
        for item in payload.values():
            if isinstance(item, dict):
                nested = self._extract_collection_info(item, name)
                if nested:
                    return nested
        return None

    def _incremental_query_checksum(self, state: models.SyncState) -> str:
        base = f"{state.scope_key}:{state.last_treated_max.isoformat() if state.last_treated_max else 'none'}"
        return sha256_digest(base)
