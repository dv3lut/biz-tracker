"""Helpers for Google-only sync modes."""
from __future__ import annotations

import time
from typing import Callable, Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import models
from app.observability import log_event, serialize_establishment
from app.services.alerts.alert_service import AlertService

from .context import SyncContext, SyncResult
from .google_enrichment import create_google_progress_callback, run_google_enrichment
from .mode import SyncMode
from .utils import tag_google_error_rate

LogAlertsFn = Callable[[models.SyncRun, Sequence[models.Alert]], list[dict[str, object]]]


def load_google_resync_targets(
    session: Session,
    mode: SyncMode,
    target_naf_codes: Sequence[str] | None = None,
    google_statuses: Sequence[str] | None = None,
) -> list[models.Establishment]:
    stmt = select(models.Establishment).order_by(models.Establishment.first_seen_at.asc())
    cleaned_statuses = [status.strip().lower() for status in google_statuses or [] if status and status.strip()]
    if cleaned_statuses:
        status_conditions = []
        normalized_status = func.lower(func.trim(models.Establishment.google_check_status))
        for status in cleaned_statuses:
            if status == "pending":
                status_conditions.append(
                    or_(models.Establishment.google_check_status.is_(None), normalized_status == "pending")
                )
            else:
                status_conditions.append(normalized_status == status)
        if status_conditions:
            stmt = stmt.where(or_(*status_conditions))
    elif mode == SyncMode.GOOGLE_PENDING:
        stmt = stmt.where(
            (models.Establishment.google_last_checked_at.is_(None))
            | (models.Establishment.google_check_status == "pending"),
        )
    if target_naf_codes:
        stmt = stmt.where(models.Establishment.naf_code.in_(target_naf_codes))
    return session.execute(stmt).scalars().all()


def collect_google_only(
    context: SyncContext,
    targets: Sequence[models.Establishment],
    *,
    log_alerts: LogAlertsFn,
) -> SyncResult:
    started_at = time.perf_counter()
    session = context.session
    run = context.run
    mode = context.mode
    google_statuses = context.google_target_statuses or []

    alert_service = (
        AlertService(
            session,
            run,
            client_notifications_enabled=context.client_notifications_enabled,
            admin_notifications_enabled=context.admin_notifications_enabled,
            target_client_ids=context.target_client_ids,
        )
        if mode.dispatch_alerts
        else None
    )
    progress_callback = create_google_progress_callback(session, run)

    google_queue_count = 0
    google_eligible_count = 0
    google_matched_count = 0
    google_pending_count = 0
    google_api_call_count = 0
    google_api_error_count = 0
    google_immediate_matches: list[models.Establishment] = []
    google_late_matches: list[models.Establishment] = []
    google_matches_payload: list[dict[str, object]] = []
    alerts_created: list[models.Alert] = []

    if not targets:
        log_event(
            "sync.google_only.skipped",
            run_id=str(run.id),
            scope_key=run.scope_key,
            mode=mode.value,
            google_statuses=google_statuses,
            reason="no_targets",
        )
        run.google_queue_count = 0
        run.google_eligible_count = 0
        run.google_matched_count = 0
        run.google_pending_count = 0
        run.google_immediate_matched_count = 0
        run.google_late_matched_count = 0
        run.google_api_call_count = 0
        session.commit()
    else:
        enrichment_result, alerts_created = run_google_enrichment(
            session=session,
            targets=targets,
            include_backlog=False,
            reset_google_state=context.google_reset_state,
            recheck_all=(mode == SyncMode.GOOGLE_REFRESH),
            alert_service=alert_service if mode.dispatch_alerts else None,
            progress_callback=progress_callback,
        )

        google_queue_count = enrichment_result.queue_count
        google_eligible_count = enrichment_result.eligible_count
        google_matched_count = enrichment_result.matched_count
        google_pending_count = enrichment_result.pending_count
        google_api_call_count = enrichment_result.api_call_count
        google_api_error_count = enrichment_result.api_error_count
        missing_contact_checked_count = enrichment_result.missing_contact_checked_count
        missing_contact_updated_count = enrichment_result.missing_contact_updated_count
        retry_backlog_count = enrichment_result.retry_backlog_count
        retry_backlog_age_buckets = enrichment_result.retry_backlog_age_buckets
        missing_contact_age_buckets = enrichment_result.missing_contact_age_buckets

        run.google_queue_count = google_queue_count
        run.google_eligible_count = google_eligible_count
        run.google_matched_count = google_matched_count
        run.google_pending_count = google_pending_count
        run.google_api_call_count = google_api_call_count

        log_event(
            "sync.google_only.summary",
            run_id=str(run.id),
            scope_key=run.scope_key,
            mode=mode.value,
            google_statuses=google_statuses,
            queue_count=google_queue_count,
            eligible_count=google_eligible_count,
            matched_count=google_matched_count,
            remaining_count=google_pending_count,
            api_call_count=google_api_call_count,
            api_error_count=google_api_error_count,
            missing_contact_checked_count=missing_contact_checked_count,
            missing_contact_updated_count=missing_contact_updated_count,
            retry_backlog_count=retry_backlog_count,
            retry_backlog_age_buckets=retry_backlog_age_buckets,
            missing_contact_age_buckets=missing_contact_age_buckets,
            error_rate=(
                round(google_api_error_count / google_api_call_count, 4)
                if google_api_call_count > 0
                else 0.0
            ),
            target_count=len(targets),
        )

        tag_google_error_rate(
            run,
            api_call_count=google_api_call_count,
            api_error_count=google_api_error_count,
            threshold=0.10,
            event_name="sync.google_only.error_rate.high",
        )

        if enrichment_result.matches:
            for match in enrichment_result.matches:
                if match.created_run_id == run.id:
                    google_immediate_matches.append(match)
                else:
                    google_late_matches.append(match)
            run.google_immediate_matched_count = len(google_immediate_matches)
            run.google_late_matched_count = len(google_late_matches)

            google_matches_payload = [serialize_establishment(item) for item in enrichment_result.matches]
            log_event(
                "sync.google.enrichment",
                run_id=str(run.id),
                scope_key=run.scope_key,
                matched_count=len(google_matches_payload),
                immediate_matched_count=run.google_immediate_matched_count,
                late_matched_count=run.google_late_matched_count,
                establishments=google_matches_payload,
            )
            for match_payload in google_matches_payload:
                log_event(
                    "sync.google.match",
                    run_id=str(run.id),
                    scope_key=run.scope_key,
                    establishment=match_payload,
                )
        else:
            run.google_immediate_matched_count = 0
            run.google_late_matched_count = 0

        session.commit()

    alerts_payload = log_alerts(run, alerts_created)
    alerts_sent_count = sum(1 for alert in alerts_created if alert.sent_at)
    duration = time.perf_counter() - started_at

    return SyncResult(
        mode=mode,
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
        max_creation_date=None,
        google_queue_count=google_queue_count,
        google_eligible_count=google_eligible_count,
        google_matched_count=google_matched_count,
        google_pending_count=google_pending_count,
        google_api_call_count=google_api_call_count,
        google_api_error_count=google_api_error_count,
        alerts_sent_count=alerts_sent_count,
    )
