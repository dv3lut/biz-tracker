"""Helpers dedicated to day replay collection flows."""
from __future__ import annotations

import time
from datetime import date
from typing import Callable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.observability import log_event, serialize_establishment
from app.services.alert_service import AlertService

from .context import SyncContext, SyncResult
from .google_enrichment import create_google_progress_callback, run_google_enrichment

LogAlertsFn = Callable[[models.SyncRun, Sequence[models.Alert]], list[dict[str, object]]]


def load_replay_establishments(
    session: Session,
    *,
    target_date: date,
    naf_codes: Sequence[str] | None = None,
) -> list[models.Establishment]:
    stmt = select(models.Establishment).where(models.Establishment.date_creation == target_date)
    if naf_codes:
        stmt = stmt.where(models.Establishment.naf_code.in_(naf_codes))
    stmt = stmt.order_by(models.Establishment.siret.asc())
    return session.scalars(stmt).all()


def collect_day_replay_from_cache(
    context: SyncContext,
    establishments: Sequence[models.Establishment],
    *,
    log_alerts: LogAlertsFn,
) -> SyncResult:
    started_at = time.perf_counter()
    session = context.session
    run = context.run
    alert_service = AlertService(
        session,
        run,
        client_notifications_enabled=context.client_notifications_enabled,
        admin_notifications_enabled=context.admin_notifications_enabled,
        target_client_ids=context.target_client_ids,
    )

    ready_matches = filter_ready_google_matches(establishments)
    has_ready_matches = bool(ready_matches)
    should_run_google = (not has_ready_matches) or context.force_google_replay

    google_queue_count = 0
    google_eligible_count = 0
    google_matched_count = 0
    google_pending_count = 0
    google_api_call_count = 0
    google_immediate_matches: list[models.Establishment] = []
    google_late_matches: list[models.Establishment] = []
    google_matches_payload: list[dict[str, object]] = []
    alerts_created: list[models.Alert] = []

    if should_run_google and context.mode.google_enabled:
        progress_callback = create_google_progress_callback(session, run)
        enrichment_result, alerts_created = run_google_enrichment(
            session=session,
            targets=establishments,
            include_backlog=False,
            force_refresh=context.force_google_replay,
            alert_service=alert_service,
            progress_callback=progress_callback,
        )

        google_queue_count = enrichment_result.queue_count
        google_eligible_count = enrichment_result.eligible_count
        google_matched_count = enrichment_result.matched_count
        google_pending_count = enrichment_result.pending_count
        google_api_call_count = enrichment_result.api_call_count
        google_immediate_matches = [match for match in enrichment_result.matches if match.created_run_id == run.id]
        google_late_matches = [match for match in enrichment_result.matches if match.created_run_id != run.id]
        google_matches_payload = [serialize_establishment(item) for item in enrichment_result.matches]

        if google_matches_payload:
            log_event(
                "sync.day_replay.google_enrichment",
                run_id=str(run.id),
                scope_key=run.scope_key,
                matched_count=len(google_matches_payload),
                force_refresh=context.force_google_replay,
            )
    else:
        google_queue_count = 0
        google_eligible_count = len(ready_matches)
        google_matched_count = len(ready_matches)
        google_pending_count = 0
        google_api_call_count = 0
        google_immediate_matches = []
        google_late_matches = ready_matches
        if ready_matches:
            google_matches_payload = [serialize_establishment(item) for item in ready_matches]
            log_event(
                "sync.day_replay.google_skipped",
                run_id=str(run.id),
                scope_key=run.scope_key,
                reason="existing_matches",
                reused_matches=len(ready_matches),
            )
            alerts_created = alert_service.create_google_alerts(ready_matches)
        else:
            log_event(
                "sync.day_replay.google_skipped",
                run_id=str(run.id),
                scope_key=run.scope_key,
                reason="no_matches",
                reused_matches=0,
            )
            alerts_created = []

    alerts_payload = log_alerts(run, alerts_created)

    run.google_queue_count = google_queue_count
    run.google_eligible_count = google_eligible_count
    run.google_matched_count = google_matched_count
    run.google_pending_count = google_pending_count
    run.google_api_call_count = google_api_call_count
    run.google_immediate_matched_count = len(google_immediate_matches)
    run.google_late_matched_count = len(google_late_matches)
    session.commit()

    alerts_sent_count = sum(1 for alert in alerts_created if alert.sent_at)
    duration = time.perf_counter() - started_at

    log_event(
        "sync.day_replay.cached_completed",
        run_id=str(run.id),
        scope_key=run.scope_key,
        duration_seconds=duration,
        establishment_count=len(establishments),
        google_called=should_run_google and context.mode.google_enabled,
        force_google=context.force_google_replay,
        ready_matches=len(ready_matches),
        google_api_call_count=google_api_call_count,
        alerts_created=len(alerts_created),
        alerts_sent=alerts_sent_count,
    )

    return SyncResult(
        mode=context.mode,
        last_treated=None,
        new_establishments=[],
        new_establishment_payloads=[],
        updated_establishments=[],
        updated_payloads=[],
        google_immediate_matches=google_immediate_matches,
        google_late_matches=google_late_matches,
        google_match_payloads=google_matches_payload,
        alerts=alerts_created,
        alert_payloads=alerts_payload,
        page_count=0,
        duration_seconds=duration,
        max_creation_date=context.replay_for_date,
        google_queue_count=google_queue_count,
        google_eligible_count=google_eligible_count,
        google_matched_count=google_matched_count,
        google_pending_count=google_pending_count,
        google_api_call_count=google_api_call_count,
        alerts_sent_count=alerts_sent_count,
    )


def filter_ready_google_matches(
    establishments: Sequence[models.Establishment],
) -> list[models.Establishment]:
    return [item for item in establishments if _has_ready_google_listing(item)]


def _has_ready_google_listing(establishment: models.Establishment) -> bool:
    status = (getattr(establishment, "google_check_status", "") or "").lower()
    if status != "found":
        return False
    has_url = bool(getattr(establishment, "google_place_url", None))
    has_place_id = bool(getattr(establishment, "google_place_id", None))
    return has_url or has_place_id
