"""Utilities to run Google enrichment consistently across sync workflows."""
from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Callable, Sequence

from sqlalchemy.orm import Session

from app.db import models
from app.observability import log_event
from app.services.alert_service import AlertService
from app.services.google_business_service import GoogleBusinessService

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
    )
    return result, alerts
