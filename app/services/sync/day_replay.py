"""Helpers dedicated to day replay collection flows."""
from __future__ import annotations

import time
from datetime import date, datetime, time as dt_time
from typing import Callable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import models
from app.observability import log_event
from app.services.alerts.alert_service import AlertService
from app.services.sync.replay_reference import DayReplayReference, DEFAULT_DAY_REPLAY_REFERENCE

from .context import SyncContext, SyncResult
from .google_enrichment import (
    classify_google_matches,
    create_google_progress_callback,
    run_google_enrichment,
    update_run_google_counters,
)
from .utils import tag_google_error_rate

LogAlertsFn = Callable[[models.SyncRun, Sequence[models.Alert]], list[dict[str, object]]]


def load_replay_establishments(
    session: Session,
    *,
    target_date: date,
    naf_codes: Sequence[str] | None = None,
    reference: DayReplayReference = DEFAULT_DAY_REPLAY_REFERENCE,
) -> list[models.Establishment]:
    stmt = select(models.Establishment)
    if reference is DayReplayReference.INSERTION_DATE:
        start_at = datetime.combine(target_date, dt_time.min)
        end_at = datetime.combine(target_date, dt_time.max)
        stmt = stmt.where(
            models.Establishment.first_seen_at >= start_at,
            models.Establishment.first_seen_at <= end_at,
        )
    else:
        stmt = stmt.where(models.Establishment.date_creation == target_date)
    if naf_codes:
        stmt = stmt.where(models.Establishment.naf_code.in_(naf_codes))
    stmt = stmt.options(selectinload(models.Establishment.directors))
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

    google_api_error_count = 0
    matches_summary = None
    alerts_created: list[models.Alert] = []

    if should_run_google and context.mode.google_enabled:
        progress_callback = create_google_progress_callback(session, run)
        enrichment_result, _ = run_google_enrichment(
            session=session,
            targets=establishments,
            include_backlog=False,
            reset_google_state=False,
            recheck_all=context.force_google_replay,
            run=run,
            alert_service=None,
            progress_callback=progress_callback,
        )

        update_run_google_counters(run, enrichment_result)
        google_api_error_count = enrichment_result.api_error_count
        matches_summary = classify_google_matches(run, enrichment_result.matches)

        if matches_summary.match_payloads:
            log_event(
                "sync.day_replay.google_enrichment",
                run_id=str(run.id),
                scope_key=run.scope_key,
                matched_count=len(matches_summary.match_payloads),
                recheck_all=context.force_google_replay,
            )

        alerts_created = alert_service.create_google_alerts(list(establishments))

        tag_google_error_rate(
            run,
            api_call_count=run.google_api_call_count,
            api_error_count=google_api_error_count,
            threshold=0.10,
            event_name="sync.day_replay.google.error_rate.high",
        )
    else:
        run.google_queue_count = 0
        run.google_eligible_count = len(ready_matches)
        run.google_matched_count = len(ready_matches)
        run.google_pending_count = 0
        run.google_api_call_count = 0
        run.google_immediate_matched_count = 0
        run.google_late_matched_count = len(ready_matches)
        if ready_matches:
            log_event(
                "sync.day_replay.google_skipped",
                run_id=str(run.id),
                scope_key=run.scope_key,
                reason="existing_matches",
                reused_matches=len(ready_matches),
            )
        else:
            log_event(
                "sync.day_replay.google_skipped",
                run_id=str(run.id),
                scope_key=run.scope_key,
                reason="no_matches",
                reused_matches=0,
            )

        alerts_created = alert_service.create_google_alerts(list(establishments))

    alerts_payload = log_alerts(run, alerts_created)

    # Run counters are already set by update_run_google_counters or the else branch
    session.commit()

    alerts_sent_count = sum(1 for alert in alerts_created if alert.sent_at)
    duration = time.perf_counter() - started_at
    google_api_call_count = run.google_api_call_count or 0

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
        google_api_error_count=google_api_error_count,
        google_error_rate=(
            round(google_api_error_count / google_api_call_count, 4)
            if google_api_call_count > 0
            else 0.0
        ),
        alerts_created=len(alerts_created),
        alerts_sent=alerts_sent_count,
    )

    immediate = matches_summary.immediate_matches if matches_summary else []
    late = matches_summary.late_matches if matches_summary else ready_matches
    payloads = matches_summary.match_payloads if matches_summary else []

    return SyncResult(
        mode=context.mode,
        last_treated=None,
        new_establishments=[],
        new_establishment_payloads=[],
        updated_establishments=[],
        updated_payloads=[],
        google_immediate_matches=immediate,
        google_late_matches=late,
        google_match_payloads=payloads,
        alerts=alerts_created,
        alert_payloads=alerts_payload,
        page_count=0,
        duration_seconds=duration,
        max_creation_date=context.replay_for_date,
        google_queue_count=run.google_queue_count or 0,
        google_eligible_count=run.google_eligible_count or 0,
        google_matched_count=run.google_matched_count or 0,
        google_pending_count=run.google_pending_count or 0,
        google_api_call_count=google_api_call_count,
        google_api_error_count=google_api_error_count,
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
