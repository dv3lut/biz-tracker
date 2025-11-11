"""Synchronization orchestration."""
from __future__ import annotations

import logging
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from app.clients.sirene_client import SireneClient
from app.config import Settings, get_settings
from app.db import models
from app.db.session import session_scope
from app.services.alert_service import AlertService
from app.services.google_business_service import GoogleBusinessService
from app.services.establishment_mapper import extract_fields
from app.observability import log_event, serialize_alert, serialize_establishment, serialize_sync_run
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


@dataclass
class SyncResult:
    last_treated: datetime | None
    new_establishments: list[dict[str, object]]
    google_matches: list[dict[str, object]]
    alerts: list[dict[str, object]]
    page_count: int
    duration_seconds: float


class SyncService:
    """Run Sirene synchronisations and persist new establishments and alerts."""

    def __init__(self) -> None:
        self._settings = get_settings()

    @property
    def settings(self) -> Settings:
        """Expose cached settings (useful for orchestrator helpers)."""

        return self._settings

    def run_sync(
        self,
        session: Session,
        *,
        resume: bool = True,
    ) -> models.SyncRun:
        run, state = self._initialize_sync_run(
            session,
            resume=resume,
            status="running",
        )

        client = SireneClient()
        context = SyncContext(session=session, run=run, state=state, client=client, settings=self._settings)
        log_event(
            "sync.run.started",
            run_id=str(run.id),
            scope_key=run.scope_key,
            resume=resume,
            triggered_by="cli",
            run=serialize_sync_run(run),
        )
        started_at = time.perf_counter()
        try:
            result = self._collect_sync(context, resume=resume)
            self._finish_run(run, state, last_treated_max=result.last_treated)
            session.commit()
            duration = time.perf_counter() - started_at
            log_event(
                "sync.run.completed",
                run_id=str(run.id),
                scope_key=run.scope_key,
                status=run.status,
                duration_seconds=duration,
                result={
                    "page_count": result.page_count,
                    "new_establishment_count": len(result.new_establishments),
                    "google_match_count": len(result.google_matches),
                    "alert_count": len(result.alerts),
                },
                run=serialize_sync_run(run),
            )
        except Exception as exc:
            session.rollback()
            run.status = "failed"
            run.finished_at = datetime.utcnow()
            session.commit()
            log_event(
                "sync.run.failed",
                level=logging.ERROR,
                run_id=str(run.id),
                scope_key=run.scope_key,
                resume=resume,
                run=serialize_sync_run(run),
                error={
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            )
            raise
        finally:
            client.close()
        return run

    def prepare_sync_run(
        self,
        session: Session,
        *,
        resume: bool = True,
        check_informations: bool = False,
    ) -> Optional[models.SyncRun]:
        state = self._get_or_create_state(session, self._settings.sync.scope_key)
        latest_treated: datetime | None = None
        if check_informations:
            latest_treated = self._fetch_latest_treated()
            if latest_treated and state.last_treated_max and latest_treated <= state.last_treated_max:
                _LOGGER.info(
                    "Aucune mise à jour détectée depuis la dernière exécution (%s).",
                    state.last_treated_max,
                )
                log_event(
                    "sync.run.skipped_no_changes",
                    scope_key=self._settings.sync.scope_key,
                    last_known_treated=state.last_treated_max,
                    latest_treated=latest_treated,
                )
                return None

        run, _state = self._initialize_sync_run(
            session,
            resume=resume,
            status="pending",
            state=state,
        )
        if latest_treated:
            run.notes = f"dateDernierTraitementMaximum: {latest_treated.isoformat()}"
        log_event(
            "sync.run.prepared",
            run_id=str(run.id),
            scope_key=run.scope_key,
            resume=resume,
            status=run.status,
            check_informations=check_informations,
            run=serialize_sync_run(run),
        )
        return run

    def execute_sync_run(self, run_id: UUID, *, resume: bool, triggered_by: str = "background") -> None:
        try:
            with session_scope() as session:
                run = session.get(models.SyncRun, run_id)
                if not run:
                    _log_and_print(logging.WARNING, "Run %s introuvable pour la synchronisation.", run_id)
                    log_event(
                        "sync.run.missing",
                        level=logging.WARNING,
                        run_id=str(run_id),
                    )
                    return
                state = self._get_or_create_state(session, run.scope_key)
                run.status = "running"
                run.started_at = datetime.utcnow()
                session.commit()

                log_event(
                    "sync.run.started",
                    run_id=str(run.id),
                    scope_key=run.scope_key,
                    resume=resume,
                    triggered_by=triggered_by,
                    run=serialize_sync_run(run),
                )
                _log_and_print(logging.INFO, "Synchronisation démarrée (run=%s)", run.id)

                client = SireneClient()
                context = SyncContext(session=session, run=run, state=state, client=client, settings=self._settings)
                started_at = time.perf_counter()
                try:
                    result = self._collect_sync(context, resume=resume)
                    self._finish_run(run, state, last_treated_max=result.last_treated)
                    session.commit()
                    duration = time.perf_counter() - started_at
                    log_event(
                        "sync.run.completed",
                        run_id=str(run.id),
                        scope_key=run.scope_key,
                        status=run.status,
                        resume=resume,
                        triggered_by=triggered_by,
                        duration_seconds=duration,
                        result={
                            "page_count": result.page_count,
                            "new_establishment_count": len(result.new_establishments),
                            "google_match_count": len(result.google_matches),
                            "alert_count": len(result.alerts),
                        },
                        run=serialize_sync_run(run),
                    )
                    _log_and_print(logging.INFO, "Synchronisation terminée (run=%s, créés=%s)", run.id, run.created_records)
                except Exception as exc:
                    session.rollback()
                    run.status = "failed"
                    run.finished_at = datetime.utcnow()
                    session.commit()
                    log_event(
                        "sync.run.failed",
                        level=logging.ERROR,
                        run_id=str(run.id),
                        scope_key=run.scope_key,
                        resume=resume,
                        triggered_by=triggered_by,
                        run=serialize_sync_run(run),
                        error={
                            "type": type(exc).__name__,
                            "message": str(exc),
                        },
                    )
                    raise
                finally:
                    client.close()
        except Exception:
            _LOGGER.exception("Synchronisation asynchrone échouée (run=%s)", run_id)
            print(f"Synchronisation asynchrone échouée (run={run_id})", flush=True)
            with session_scope() as session:
                run = session.get(models.SyncRun, run_id)
                if run:
                    run.status = "failed"
                    run.finished_at = datetime.utcnow()
                    session.commit()

    def has_active_run(self, session: Session, scope_key: str) -> bool:
        active_statuses = ("running", "pending")
        existing = (
            session.query(models.SyncRun.id)
            .filter(models.SyncRun.scope_key == scope_key, models.SyncRun.status.in_(active_statuses))
            .first()
        )
        return existing is not None

    def _fetch_latest_treated(self, client: Optional[SireneClient] = None) -> datetime | None:
        owned_client = client is None
        client = client or SireneClient()
        try:
            infos = client.get_informations()
        finally:
            if owned_client:
                client.close()

        collection = self._extract_collection_info(infos, "etablissements") if isinstance(infos, dict) else None
        if not collection:
            return None

        latest_treated = parse_datetime(collection.get("dateDernierTraitementMaximum"))
        if not latest_treated:
            return None
        return latest_treated

    def _initialize_sync_run(
        self,
        session: Session,
        *,
        resume: bool,
        status: str,
        state: Optional[models.SyncState] = None,
    ) -> tuple[models.SyncRun, models.SyncState]:
        scope_key = self._settings.sync.scope_key
        state = state or self._get_or_create_state(session, scope_key)
        run = self._start_run(
            session,
            scope_key=scope_key,
            run_type="sync",
            resume=resume,
            initial_status=status,
        )
        return run, state

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

    def _collect_sync(self, context: SyncContext, *, resume: bool) -> SyncResult:
        state = context.state
        months_back = max(self._settings.sync.months_back, 1)
        since_creation = subtract_months(datetime.utcnow().date(), months_back)
        query = self._build_restaurant_query(since_creation=since_creation)
        checksum = sha256_digest(query)
        context.run.query_checksum = checksum

        if state.query_checksum and state.query_checksum != checksum:
            _LOGGER.info("La requête a changé, réinitialisation du curseur.")
            log_event(
                "sync.cursor.reset",
                run_id=str(context.run.id),
                scope_key=context.run.scope_key,
                reason="query_changed",
                previous_checksum=state.query_checksum,
                new_checksum=checksum,
            )
            state.last_cursor = None
            state.cursor_completed = False
        state.query_checksum = checksum

        if not resume:
            log_event(
                "sync.cursor.reset",
                run_id=str(context.run.id),
                scope_key=context.run.scope_key,
                reason="forced_full_run",
            )
            state.last_cursor = None
            state.cursor_completed = False

        latest_treated = self._fetch_latest_treated(context.client)
        if latest_treated:
            context.run.notes = f"dateDernierTraitementMaximum: {latest_treated.isoformat()}"
            log_event(
                "sync.informations.latest_treated",
                run_id=str(context.run.id),
                scope_key=context.run.scope_key,
                latest_treated=latest_treated,
            )

        champs = self._build_fields_parameter()
        cursor_value = state.last_cursor if state.last_cursor and not state.cursor_completed else "*"
        tri = "dateCreationEtablissement desc"

        alert_service = AlertService(context.session, context.run)
        new_entities_total: list[models.Establishment] = []
        new_entities_payload: list[dict[str, object]] = []
        google_matches_payload: list[dict[str, object]] = []
        alerts_payload: list[dict[str, object]] = []
        page_count = 0
        collection_started = time.perf_counter()

        log_event(
            "sync.collection.started",
            run_id=str(context.run.id),
            scope_key=context.run.scope_key,
            resume=resume,
            months_back=months_back,
            since_creation=since_creation,
            page_size=self._settings.sirene.page_size,
            initial_cursor=cursor_value,
        )

        while True:
            page_size = self._settings.sirene.page_size
            page_count += 1
            page_started = time.perf_counter()

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
            new_entities_total.extend(new_entities)

            if new_entities:
                batch_payload = [serialize_establishment(entity) for entity in new_entities]
                new_entities_payload.extend(batch_payload)
                log_event(
                    "sync.new_establishments.batch",
                    run_id=str(context.run.id),
                    scope_key=context.run.scope_key,
                    page=page_count,
                    count=len(batch_payload),
                    establishments=batch_payload,
                )
                for establishment_payload in batch_payload:
                    log_event(
                        "sync.new_establishment",
                        run_id=str(context.run.id),
                        scope_key=context.run.scope_key,
                        establishment=establishment_payload,
                    )

            next_cursor = header.get("curseurSuivant")
            state.last_cursor = next_cursor
            context.run.last_cursor = next_cursor
            total_value = header.get("total")
            try:
                state.last_total = int(total_value) if total_value is not None else state.last_total
            except (TypeError, ValueError):
                _LOGGER.debug("Valeur 'total' non exploitable: %s", total_value)
            state.last_synced_at = datetime.utcnow()
            context.session.flush()
            context.session.commit()

            current_cursor = cursor_value or "*"
            page_duration = time.perf_counter() - page_started
            log_event(
                "sync.page.processed",
                run_id=str(context.run.id),
                scope_key=context.run.scope_key,
                page=page_count,
                fetched=len(etablissements),
                created=len(new_entities),
                api_call_count=context.run.api_call_count,
                cursor=current_cursor,
                next_cursor=next_cursor,
                reported_total=total_value,
                duration_seconds=page_duration,
            )

            if not etablissements or not next_cursor or next_cursor == header.get("curseur"):
                state.cursor_completed = True
                break

            cursor_value = next_cursor

        google_service = GoogleBusinessService(context.session)
        try:
            matched_establishments = google_service.enrich(new_entities_total)
        finally:
            google_service.close()

        if matched_establishments:
            google_matches_payload = [serialize_establishment(item) for item in matched_establishments]
            log_event(
                "sync.google.enrichment",
                run_id=str(context.run.id),
                scope_key=context.run.scope_key,
                matched_count=len(google_matches_payload),
                establishments=google_matches_payload,
            )
            for match_payload in google_matches_payload:
                log_event(
                    "sync.google.match",
                    run_id=str(context.run.id),
                    scope_key=context.run.scope_key,
                    establishment=match_payload,
                )

            alerts = alert_service.create_google_alerts(matched_establishments)
            if alerts:
                alerts_payload = [serialize_alert(alert) for alert in alerts]
                log_event(
                    "sync.alerts.created",
                    run_id=str(context.run.id),
                    scope_key=context.run.scope_key,
                    count=len(alerts_payload),
                    alerts=alerts_payload,
                )
                for alert_payload in alerts_payload:
                    log_event(
                        "sync.alert.created",
                        run_id=str(context.run.id),
                        scope_key=context.run.scope_key,
                        alert=alert_payload,
                    )
        context.session.commit()

        duration = time.perf_counter() - collection_started
        log_event(
            "sync.collection.completed",
            run_id=str(context.run.id),
            scope_key=context.run.scope_key,
            duration_seconds=duration,
            page_count=page_count,
            fetched_records=context.run.fetched_records,
            created_records=context.run.created_records,
            api_call_count=context.run.api_call_count,
        )

        return SyncResult(
            last_treated=latest_treated,
            new_establishments=new_entities_payload,
            google_matches=google_matches_payload,
            alerts=alerts_payload,
            page_count=page_count,
            duration_seconds=duration,
        )

    def _finish_run(self, run: models.SyncRun, state: models.SyncState, *, last_treated_max: datetime | None) -> None:
        run.status = "success"
        run.finished_at = datetime.utcnow()
        state.last_successful_run_id = run.id
        if last_treated_max:
            state.last_treated_max = last_treated_max

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
