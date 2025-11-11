"""Synchronization orchestration."""
from __future__ import annotations

import logging
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional, Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from app.clients.sirene_client import SireneClient
from app.config import Settings, get_settings
from app.db import models
from app.db.session import session_scope
from app.services.alert_service import AlertService
from app.services.google_business_service import GoogleBusinessService
from app.services.email_service import EmailService
from app.services.establishment_mapper import extract_fields
from app.services.client_service import get_admin_emails
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
class UpdatedEstablishmentInfo:
    establishment: models.Establishment
    changed_fields: list[str]


@dataclass
class SyncResult:
    last_treated: datetime | None
    new_establishments: list[models.Establishment]
    new_establishment_payloads: list[dict[str, object]]
    updated_establishments: list[UpdatedEstablishmentInfo]
    updated_payloads: list[dict[str, object]]
    google_immediate_matches: list[models.Establishment]
    google_late_matches: list[models.Establishment]
    google_match_payloads: list[dict[str, object]]
    alerts: list[models.Alert]
    alert_payloads: list[dict[str, object]]
    page_count: int
    duration_seconds: float
    google_queue_count: int
    google_eligible_count: int
    google_matched_count: int
    google_pending_count: int
    alerts_sent_count: int


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
            summary_payload = self._build_run_summary_payload(run, result)
            email_summary = self._send_run_summary_email(session, run, summary_payload)
            summary_payload["email"] = email_summary
            run.summary = summary_payload
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
                    "updated_establishment_count": len(result.updated_establishments),
                    "google_match_count": result.google_matched_count,
                    "google": {
                        "queue_count": result.google_queue_count,
                        "eligible_count": result.google_eligible_count,
                        "matched_count": result.google_matched_count,
                        "immediate_matches": len(result.google_immediate_matches),
                        "late_matches": len(result.google_late_matches),
                        "pending_count": result.google_pending_count,
                    },
                    "alert_count": len(result.alerts),
                    "alerts_sent_count": result.alerts_sent_count,
                    "email": email_summary,
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
                    summary_payload = self._build_run_summary_payload(run, result)
                    email_summary = self._send_run_summary_email(session, run, summary_payload)
                    summary_payload["email"] = email_summary
                    run.summary = summary_payload
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
                            "updated_establishment_count": len(result.updated_establishments),
                            "google_match_count": result.google_matched_count,
                            "google": {
                                "queue_count": result.google_queue_count,
                                "eligible_count": result.google_eligible_count,
                                "matched_count": result.google_matched_count,
                                "immediate_matches": len(result.google_immediate_matches),
                                "late_matches": len(result.google_late_matches),
                                "pending_count": result.google_pending_count,
                            },
                            "alert_count": len(result.alerts),
                            "alerts_sent_count": result.alerts_sent_count,
                            "email": email_summary,
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
        updated_entities: list[UpdatedEstablishmentInfo] = []
        updated_payloads: list[dict[str, object]] = []
        google_immediate_matches: list[models.Establishment] = []
        google_late_matches: list[models.Establishment] = []
        google_matches_payload: list[dict[str, object]] = []
        alerts_payload: list[dict[str, object]] = []
        alerts_created: list[models.Alert] = []
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

            new_entities, updated_batch = self._upsert_establishments(context.session, etablissements, context.run.id)
            context.run.created_records += len(new_entities)
            context.run.updated_records += len(updated_batch)
            new_entities_total.extend(new_entities)
            updated_entities.extend(updated_batch)

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

            if updated_batch:
                updated_batch_payload: list[dict[str, object]] = []
                for info in updated_batch:
                    payload = serialize_establishment(info.establishment)
                    payload["changed_fields"] = list(info.changed_fields)
                    updated_batch_payload.append(payload)
                    log_event(
                        "sync.updated_establishment",
                        run_id=str(context.run.id),
                        scope_key=context.run.scope_key,
                        establishment=payload,
                    )
                updated_payloads.extend(updated_batch_payload)
                log_event(
                    "sync.updated_establishments.batch",
                    run_id=str(context.run.id),
                    scope_key=context.run.scope_key,
                    page=page_count,
                    count=len(updated_batch_payload),
                    establishments=updated_batch_payload,
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
            enrichment = google_service.enrich(new_entities_total)
        finally:
            google_service.close()

        context.run.google_queue_count = enrichment.queue_count
        context.run.google_eligible_count = enrichment.eligible_count
        context.run.google_matched_count = enrichment.matched_count
        context.run.google_pending_count = enrichment.remaining_count

        log_event(
            "sync.google.summary",
            run_id=str(context.run.id),
            scope_key=context.run.scope_key,
            queue_count=enrichment.queue_count,
            eligible_count=enrichment.eligible_count,
            matched_count=enrichment.matched_count,
            remaining_count=enrichment.remaining_count,
            new_establishment_count=len(new_entities_total),
        )

        if enrichment.matches:
            for match in enrichment.matches:
                if match.created_run_id == context.run.id:
                    google_immediate_matches.append(match)
                else:
                    google_late_matches.append(match)
            context.run.google_immediate_matched_count = len(google_immediate_matches)
            context.run.google_late_matched_count = len(google_late_matches)

            google_matches_payload = [serialize_establishment(item) for item in enrichment.matches]
            log_event(
                "sync.google.enrichment",
                run_id=str(context.run.id),
                scope_key=context.run.scope_key,
                matched_count=len(google_matches_payload),
                immediate_matched_count=context.run.google_immediate_matched_count,
                late_matched_count=context.run.google_late_matched_count,
                establishments=google_matches_payload,
            )
            for match_payload in google_matches_payload:
                log_event(
                    "sync.google.match",
                    run_id=str(context.run.id),
                    scope_key=context.run.scope_key,
                    establishment=match_payload,
                )

            alerts = alert_service.create_google_alerts(enrichment.matches)
            if alerts:
                alerts_created.extend(alerts)
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

        alerts_sent_count = sum(1 for alert in alerts_created if alert.sent_at)

        duration = time.perf_counter() - collection_started
        log_event(
            "sync.collection.completed",
            run_id=str(context.run.id),
            scope_key=context.run.scope_key,
            duration_seconds=duration,
            page_count=page_count,
            fetched_records=context.run.fetched_records,
            created_records=context.run.created_records,
            updated_records=context.run.updated_records,
            api_call_count=context.run.api_call_count,
            google_queue_count=enrichment.queue_count,
            google_eligible_count=enrichment.eligible_count,
            google_matched_count=enrichment.matched_count,
            google_pending_count=enrichment.remaining_count,
            google_immediate_matched_count=context.run.google_immediate_matched_count,
            google_late_matched_count=context.run.google_late_matched_count,
            alerts_created=len(alerts_created),
            alerts_sent=alerts_sent_count,
        )

        return SyncResult(
            last_treated=latest_treated,
            new_establishments=new_entities_total,
            new_establishment_payloads=new_entities_payload,
            updated_establishments=updated_entities,
            updated_payloads=updated_payloads,
            google_immediate_matches=google_immediate_matches,
            google_late_matches=google_late_matches,
            google_match_payloads=google_matches_payload,
            alerts=alerts_created,
            alert_payloads=alerts_payload,
            page_count=page_count,
            duration_seconds=duration,
            google_queue_count=enrichment.queue_count,
            google_eligible_count=enrichment.eligible_count,
            google_matched_count=enrichment.matched_count,
            google_pending_count=enrichment.remaining_count,
            alerts_sent_count=alerts_sent_count,
        )

    def _build_run_summary_payload(self, run: models.SyncRun, result: SyncResult) -> dict[str, Any]:
        def summarize_establishment(establishment: models.Establishment) -> dict[str, Any]:
            return {
                "siret": establishment.siret,
                "name": establishment.name,
                "code_postal": establishment.code_postal,
                "libelle_commune": establishment.libelle_commune or establishment.libelle_commune_etranger,
                "naf_code": establishment.naf_code,
                "google_status": establishment.google_check_status,
                "google_place_url": establishment.google_place_url,
                "google_place_id": establishment.google_place_id,
                "created_run_id": str(establishment.created_run_id) if establishment.created_run_id else None,
                "first_seen_at": establishment.first_seen_at.isoformat() if establishment.first_seen_at else None,
                "last_seen_at": establishment.last_seen_at.isoformat() if establishment.last_seen_at else None,
            }

        samples = {
            "new_establishments": [summarize_establishment(item) for item in result.new_establishments[:10]],
            "updated_establishments": [],
            "google_late_matches": [summarize_establishment(item) for item in result.google_late_matches[:10]],
            "google_immediate_matches": [summarize_establishment(item) for item in result.google_immediate_matches[:10]],
        }
        for info in result.updated_establishments[:10]:
            payload = summarize_establishment(info.establishment)
            payload["changed_fields"] = list(info.changed_fields)
            samples["updated_establishments"].append(payload)

        summary_stats = {
            "fetched_records": run.fetched_records,
            "created_records": run.created_records,
            "updated_records": run.updated_records,
            "api_call_count": run.api_call_count,
            "google": {
                "queue_count": run.google_queue_count,
                "eligible_count": run.google_eligible_count,
                "matched_count": run.google_matched_count,
                "immediate_matches": run.google_immediate_matched_count,
                "late_matches": run.google_late_matched_count,
                "pending_count": run.google_pending_count,
            },
            "alerts": {
                "created": len(result.alerts),
                "sent": result.alerts_sent_count,
            },
        }

        return {
            "run": {
                "id": str(run.id),
                "scope_key": run.scope_key,
                "status": run.status,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                "duration_seconds": result.duration_seconds,
                "page_count": result.page_count,
            },
            "stats": summary_stats,
            "samples": samples,
        }

    def _send_run_summary_email(self, session: Session, run: models.SyncRun, summary: dict[str, Any]) -> dict[str, Any]:
        email_service = EmailService()
        recipients = get_admin_emails(session)
        if not recipients:
            log_event(
                "sync.summary.email.skipped",
                run_id=str(run.id),
                scope_key=run.scope_key,
                reason="no_recipients",
            )
            return {"sent": False, "recipients": [], "subject": None, "reason": "no_recipients"}
        if not email_service.is_enabled():
            log_event(
                "sync.summary.email.skipped",
                run_id=str(run.id),
                scope_key=run.scope_key,
                reason="email_disabled",
            )
            return {"sent": False, "recipients": recipients, "subject": None, "reason": "email_disabled"}
        if not email_service.is_configured():
            log_event(
                "sync.summary.email.skipped",
                run_id=str(run.id),
                scope_key=run.scope_key,
                reason="email_not_configured",
            )
            return {"sent": False, "recipients": recipients, "subject": None, "reason": "email_not_configured"}

        started_at_display = run.started_at.strftime("%Y-%m-%d %H:%M") if run.started_at else "inconnu"
        subject = f"[{run.scope_key}] Synthese run {started_at_display}"
        body = self._render_run_summary_email(run, summary)

        try:
            email_service.send(subject, body, recipients)
        except Exception as exc:  # noqa: BLE001 - log and continue
            _LOGGER.warning("Échec de l'envoi de la synthèse du run %s: %s", run.id, exc)
            log_event(
                "sync.summary.email.error",
                run_id=str(run.id),
                scope_key=run.scope_key,
                reason="send_error",
                error={"type": type(exc).__name__, "message": str(exc)},
            )
            return {"sent": False, "recipients": recipients, "subject": subject, "reason": "send_error"}

        log_event(
            "sync.summary.email.sent",
            run_id=str(run.id),
            scope_key=run.scope_key,
            recipients=recipients,
            subject=subject,
        )
        return {"sent": True, "recipients": recipients, "subject": subject}


    def _render_run_summary_email(self, run: models.SyncRun, summary: dict[str, Any]) -> str:
        run_data = summary.get("run", {})
        stats = summary.get("stats", {})
        google_stats = stats.get("google", {})
        alerts_stats = stats.get("alerts", {})
        samples = summary.get("samples", {})

        def format_sample(sample: dict[str, Any], *, include_changes: bool = False) -> str:
            name = sample.get("name") or "(nom indisponible)"
            siret = sample.get("siret") or "N/A"
            postal = sample.get("code_postal") or ""
            commune = sample.get("libelle_commune") or ""
            location = " ".join(part for part in [postal, commune] if part)
            google_status = sample.get("google_status") or "unknown"
            line = f"- {name} — {siret}"
            if location:
                line += f" ({location})"
            line += f" | Google: {google_status}"
            place_url = sample.get("google_place_url")
            if place_url:
                line += f" | {place_url}"
            if include_changes and sample.get("changed_fields"):
                changes = ", ".join(sample["changed_fields"])
                line += f" | champs: {changes}"
            return line

        lines = [
            f"Synthèse du run {run_data.get('id', run.id)} ({run.scope_key})",
            f"Statut: {run_data.get('status', run.status)}",
            f"Début: {run_data.get('started_at')}",
            f"Fin: {run_data.get('finished_at')}",
            f"Durée: {run_data.get('duration_seconds')} s",
            f"Pages traitées: {run_data.get('page_count')}",
            "",
            "Statistiques:",
            f"- Enregistrements récupérés: {stats.get('fetched_records')}",
            f"- Nouveaux établissements: {stats.get('created_records')}",
            f"- Établissements mis à jour: {stats.get('updated_records')}",
            f"- Appels API: {stats.get('api_call_count')}",
            "",
            "Google Places:",
            f"- Correspondances immédiates: {google_stats.get('immediate_matches')}",
            f"- Correspondances tardives: {google_stats.get('late_matches')}",
            f"- Total correspondances: {google_stats.get('matched_count')}",
            f"- En file d'attente: {google_stats.get('pending_count')}",
            "",
            "Alertes:",
            f"- Créées: {alerts_stats.get('created')}",
            f"- Envoyées: {alerts_stats.get('sent')}",
        ]

        new_samples = samples.get("new_establishments", [])
        if new_samples:
            lines.append("")
            lines.append("Nouveaux établissements (top 10):")
            for sample in new_samples:
                lines.append(format_sample(sample))

        updated_samples = samples.get("updated_establishments", [])
        if updated_samples:
            lines.append("")
            lines.append("Établissements mis à jour (top 10):")
            for sample in updated_samples:
                lines.append(format_sample(sample, include_changes=True))

        late_samples = samples.get("google_late_matches", [])
        if late_samples:
            lines.append("")
            lines.append("Correspondances Google tardives (top 10):")
            for sample in late_samples:
                lines.append(format_sample(sample))

        immediate_samples = samples.get("google_immediate_matches", [])
        if immediate_samples:
            lines.append("")
            lines.append("Correspondances Google immédiates (top 10):")
            for sample in immediate_samples:
                lines.append(format_sample(sample))

        return "\n".join(lines).strip()

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
    ) -> tuple[list[models.Establishment], list[UpdatedEstablishmentInfo]]:
        new_entities: list[models.Establishment] = []
        updated_entities: list[UpdatedEstablishmentInfo] = []
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
                changed_fields: list[str] = []
                for key, value in fields.items():
                    current_value = getattr(entity, key)
                    if current_value != value:
                        setattr(entity, key, value)
                        changed_fields.append(key)
                entity.last_seen_at = now
                entity.last_run_id = run_id
                if changed_fields:
                    updated_entities.append(UpdatedEstablishmentInfo(entity, changed_fields))
            else:
                fields["created_run_id"] = run_id
                fields["last_run_id"] = run_id
                entity = models.Establishment(**fields)
                entity.first_seen_at = now
                entity.last_seen_at = now
                session.add(entity)
                new_entities.append(entity)
        session.flush()
        return new_entities, updated_entities

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
