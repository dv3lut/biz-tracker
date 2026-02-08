"""Helpers for LinkedIn-only sync modes."""
from __future__ import annotations

import time
from typing import Callable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.observability import log_event

from .context import SyncContext, SyncResult
from .mode import SyncMode

LogAlertsFn = Callable[[models.SyncRun, Sequence[models.Alert]], list[dict[str, object]]]


def load_linkedin_resync_targets(
    session: Session,
    mode: SyncMode,
    target_naf_codes: Sequence[str] | None = None,
) -> list[models.Establishment]:
    """Load establishments with directors needing LinkedIn enrichment.

    Args:
        session: Database session.
        mode: Sync mode (LINKEDIN_PENDING or LINKEDIN_REFRESH).
        target_naf_codes: Optional NAF code filter.

    Returns:
        List of establishments with physical person directors.
    """
    # Base query: establishments with at least one physical person director
    stmt = (
        select(models.Establishment)
        .join(models.Director)
        .where(models.Director.type_dirigeant == "personne physique")
        .distinct()
        .order_by(models.Establishment.first_seen_at.asc())
    )

    if mode == SyncMode.LINKEDIN_PENDING:
        # Only establishments with directors not yet checked
        stmt = stmt.where(
            (models.Director.linkedin_last_checked_at.is_(None))
            | (models.Director.linkedin_check_status == "pending"),
        )

    if target_naf_codes:
        stmt = stmt.where(models.Establishment.naf_code.in_(target_naf_codes))

    return list(session.execute(stmt).scalars().all())


def collect_linkedin_only(
    context: SyncContext,
    targets: Sequence[models.Establishment],
    *,
    log_alerts: LogAlertsFn,
) -> SyncResult:
    """Collect LinkedIn profiles for establishments (LinkedIn-only mode).

    Args:
        context: Sync context with session, run, etc.
        targets: Establishments to enrich.
        log_alerts: Callback to log created alerts.

    Returns:
        SyncResult with enrichment statistics.
    """
    from app.services.linkedin import LinkedInLookupService

    started_at = time.perf_counter()
    session = context.session
    run = context.run
    mode = context.mode

    linkedin_searched_count = 0
    linkedin_found_count = 0
    linkedin_not_found_count = 0
    linkedin_error_count = 0
    linkedin_api_call_count = 0

    if not targets:
        log_event(
            "sync.linkedin_only.skipped",
            run_id=str(run.id),
            scope_key=run.scope_key,
            mode=mode.value,
            reason="no_targets",
        )
        session.commit()
        return SyncResult(
            mode=mode,
            page_count=0,
            new_establishments=[],
            updated_establishments=[],
            google_queue_count=0,
            google_eligible_count=0,
            google_matched_count=0,
            google_pending_count=0,
            google_api_call_count=0,
            google_api_error_count=0,
            google_immediate_matches=[],
            google_late_matches=[],
            alerts=[],
            alerts_sent_count=0,
            last_treated=None,
            max_creation_date=None,
        )

    log_event(
        "sync.linkedin_only.started",
        run_id=str(run.id),
        scope_key=run.scope_key,
        mode=mode.value,
        target_count=len(targets),
    )

    linkedin_service = LinkedInLookupService(session)
    force_refresh = mode == SyncMode.LINKEDIN_REFRESH

    # Create progress callback to update run counters
    def linkedin_progress_callback(
        total: int,
        searched: int,
        found: int,
        not_found: int,
        error: int,
    ) -> None:
        run.linkedin_queue_count = total
        run.linkedin_searched_count = searched
        run.linkedin_found_count = found
        run.linkedin_not_found_count = not_found
        run.linkedin_error_count = error
        session.flush()

    try:
        enrichment_result = linkedin_service.enrich_batch(
            targets,
            run_id=run.id,
            force_refresh=force_refresh,
            progress_callback=linkedin_progress_callback,
        )

        linkedin_searched_count = enrichment_result.searched_count
        linkedin_found_count = enrichment_result.found_count
        linkedin_not_found_count = enrichment_result.not_found_count
        linkedin_error_count = enrichment_result.error_count
        linkedin_api_call_count = enrichment_result.api_call_count

        # Final update of run counters
        run.linkedin_queue_count = enrichment_result.total_directors
        run.linkedin_searched_count = linkedin_searched_count
        run.linkedin_found_count = linkedin_found_count
        run.linkedin_not_found_count = linkedin_not_found_count
        run.linkedin_error_count = linkedin_error_count

        session.commit()

    finally:
        linkedin_service.close()

    duration = time.perf_counter() - started_at

    log_event(
        "sync.linkedin_only.completed",
        run_id=str(run.id),
        scope_key=run.scope_key,
        mode=mode.value,
        duration_seconds=duration,
        target_count=len(targets),
        searched_count=linkedin_searched_count,
        found_count=linkedin_found_count,
        not_found_count=linkedin_not_found_count,
        error_count=linkedin_error_count,
        api_call_count=linkedin_api_call_count,
    )

    # Store LinkedIn stats in run summary
    if run.summary is None:
        run.summary = {}
    run.summary["linkedin"] = {
        "searched_count": linkedin_searched_count,
        "found_count": linkedin_found_count,
        "not_found_count": linkedin_not_found_count,
        "error_count": linkedin_error_count,
        "api_call_count": linkedin_api_call_count,
    }
    session.commit()

    return SyncResult(
        mode=mode,
        page_count=0,
        new_establishments=[],
        updated_establishments=[],
        google_queue_count=0,
        google_eligible_count=0,
        google_matched_count=0,
        google_pending_count=0,
        google_api_call_count=0,
        google_api_error_count=0,
        google_immediate_matches=[],
        google_late_matches=[],
        alerts=[],
        alerts_sent_count=0,
        last_treated=None,
        max_creation_date=None,
    )


__all__ = ["collect_linkedin_only", "load_linkedin_resync_targets"]
