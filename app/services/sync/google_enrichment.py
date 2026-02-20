"""Utilities to run Google enrichment consistently across sync workflows."""
from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Callable, Sequence

from sqlalchemy.orm import Session

from app.db import models
from app.observability import log_event, serialize_establishment
from app.services.alerts.alert_service import AlertService
from app.services.google_business.google_business_service import GoogleBusinessService

ProgressCallback = Callable[[int, int, int, int, int], None] | None


@dataclass(slots=True)
class GoogleEnrichmentResult:
    """Snapshot of the Google enrichment run."""

    queue_count: int
    eligible_count: int
    matched_count: int
    pending_count: int
    api_call_count: int
    api_error_count: int
    matches: list[models.Establishment]
    missing_contact_checked_count: int
    missing_contact_updated_count: int
    retry_backlog_count: int
    retry_backlog_age_buckets: dict[str, int] | None
    missing_contact_age_buckets: dict[str, int] | None


def create_google_progress_callback(session: Session, run: models.SyncRun) -> Callable[[int, int, int, int, int], None]:
    """Return a callback that persists Google progress updates sparingly."""

    last_snapshot: tuple[int, int, int, int, int] | None = None

    def update_progress(
        queue_count: int,
        eligible_count: int,
        processed_count: int,
        matched_count: int,
        pending_count: int,
    ) -> None:
        nonlocal last_snapshot
        snapshot = (queue_count, eligible_count, processed_count, matched_count, pending_count)
        if snapshot == last_snapshot:
            return
        last_snapshot = snapshot
        run.google_queue_count = queue_count
        run.google_eligible_count = eligible_count
        run.google_matched_count = matched_count
        run.google_pending_count = pending_count
        session.flush()
        session.commit()

    return update_progress


def run_google_enrichment(
    *,
    session: Session,
    targets: Sequence[models.Establishment],
    include_backlog: bool,
    reset_google_state: bool,
    recheck_all: bool = False,
    run: models.SyncRun | None = None,
    alert_service: AlertService | None = None,
    progress_callback: ProgressCallback = None,
) -> tuple[GoogleEnrichmentResult, list[models.Alert]]:
    """Execute Google enrichment and optional alert creation in a unified way."""

    log_event(
        "sync.google.enrichment.started",
        target_count=len(targets),
        include_backlog=include_backlog,
        reset_google_state=reset_google_state,
        recheck_all=recheck_all,
        alerts_enabled=bool(alert_service),
    )
    started_at = time.perf_counter()

    google_service = GoogleBusinessService(session)
    try:
        enrichment = google_service.enrich(
            targets,
            progress_callback=progress_callback,
            include_backlog=include_backlog,
            reset_google_state=reset_google_state,
            recheck_all=recheck_all,
            run=run,
        )
    finally:
        google_service.close()

    duration = time.perf_counter() - started_at
    log_event(
        "sync.google.enrichment.completed",
        duration_seconds=duration,
        queue_count=enrichment.queue_count,
        eligible_count=enrichment.eligible_count,
        matched_count=enrichment.matched_count,
        remaining_count=enrichment.remaining_count,
        api_call_count=enrichment.api_call_count,
        missing_contact_checked_count=enrichment.missing_contact_checked_count,
        missing_contact_updated_count=enrichment.missing_contact_updated_count,
        retry_backlog_count=enrichment.retry_backlog_count,
        retry_backlog_age_buckets=enrichment.retry_backlog_age_buckets,
        missing_contact_age_buckets=enrichment.missing_contact_age_buckets,
    )

    alerts: list[models.Alert] = []
    if alert_service:
        log_event(
            "sync.alerts.dispatch.started",
            candidate_count=len(enrichment.matches),
        )
        alert_started_at = time.perf_counter()
        alerts = alert_service.create_google_alerts(enrichment.matches)
        log_event(
            "sync.alerts.dispatch.completed",
            duration_seconds=time.perf_counter() - alert_started_at,
            alerts_created=len(alerts),
        )

    result = GoogleEnrichmentResult(
        queue_count=enrichment.queue_count,
        eligible_count=enrichment.eligible_count,
        matched_count=enrichment.matched_count,
        pending_count=enrichment.remaining_count,
        api_call_count=enrichment.api_call_count,
        api_error_count=enrichment.api_error_count,
        matches=list(enrichment.matches),
        missing_contact_checked_count=enrichment.missing_contact_checked_count,
        missing_contact_updated_count=enrichment.missing_contact_updated_count,
        retry_backlog_count=enrichment.retry_backlog_count,
        retry_backlog_age_buckets=enrichment.retry_backlog_age_buckets,
        missing_contact_age_buckets=enrichment.missing_contact_age_buckets,
    )
    return result, alerts


# ---------------------------------------------------------------------------
# Shared post-processing helpers used by collector, google_only, day_replay
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class GoogleMatchesSummary:
    """Classified Google matches with serialized payloads."""

    immediate_matches: list[models.Establishment] = field(default_factory=list)
    late_matches: list[models.Establishment] = field(default_factory=list)
    match_payloads: list[dict[str, object]] = field(default_factory=list)


def update_run_google_counters(
    run: models.SyncRun,
    enrichment_result: GoogleEnrichmentResult,
) -> None:
    """Copy core Google enrichment counters onto the SyncRun record."""
    run.google_queue_count = enrichment_result.queue_count
    run.google_eligible_count = enrichment_result.eligible_count
    run.google_matched_count = enrichment_result.matched_count
    run.google_pending_count = enrichment_result.pending_count
    run.google_api_call_count = enrichment_result.api_call_count


def classify_google_matches(
    run: models.SyncRun,
    matches: Sequence[models.Establishment],
) -> GoogleMatchesSummary:
    """Split matches into immediate/late, update run counters, serialize and log.

    This replaces the duplicated match-splitting and logging blocks that were
    present in collector.py, google_only.py, and day_replay.py.
    """
    if not matches:
        run.google_immediate_matched_count = 0
        run.google_late_matched_count = 0
        return GoogleMatchesSummary()

    immediate: list[models.Establishment] = []
    late: list[models.Establishment] = []
    for match in matches:
        if match.created_run_id == run.id:
            immediate.append(match)
        else:
            late.append(match)

    run.google_immediate_matched_count = len(immediate)
    run.google_late_matched_count = len(late)

    payloads = [serialize_establishment(item) for item in matches]
    log_event(
        "sync.google.enrichment",
        run_id=str(run.id),
        scope_key=run.scope_key,
        matched_count=len(payloads),
        immediate_matched_count=len(immediate),
        late_matched_count=len(late),
        establishments=payloads,
    )
    for payload in payloads:
        log_event(
            "sync.google.match",
            run_id=str(run.id),
            scope_key=run.scope_key,
            establishment=payload,
        )

    return GoogleMatchesSummary(
        immediate_matches=immediate,
        late_matches=late,
        match_payloads=payloads,
    )
