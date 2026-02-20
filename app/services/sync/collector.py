"""Collection helpers for synchronization runs."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import models
from app.db.session import session_scope
from app.observability import log_event, serialize_alert, serialize_establishment
from app.services.alerts.alert_service import AlertService
from app.services.sync.day_replay import (
    collect_day_replay_from_cache,
    filter_ready_google_matches,
    load_replay_establishments,
)
from app.services.sync.google_enrichment import create_google_progress_callback, run_google_enrichment
from app.services.sync.google_only import collect_google_only, load_google_resync_targets
from app.services.sync.mode import SyncMode
from app.services.sync.replay_reference import DEFAULT_DAY_REPLAY_REFERENCE, DayReplayReference
from app.utils.dates import subtract_months, utcnow
from app.utils.hashing import sha256_digest

from .context import SyncContext, SyncResult, UpdatedEstablishmentInfo
from .pages import collect_pages
from .persistence import SyncPersistenceMixin
from .utils import append_run_note, format_target_naf_note, tag_google_error_rate
from .annuaire_enrichment import enrich_establishments_from_annuaire
from .linkedin_only import collect_linkedin_only, load_linkedin_resync_targets
from .website_scrape_only import collect_website_scrape_only, load_website_scrape_targets


class SyncCollectorMixin(SyncPersistenceMixin):
    """Provide data collection and persistence helpers for sync runs."""

    def _collect_sync(self, context: SyncContext) -> SyncResult:
        if context.mode == SyncMode.DAY_REPLAY and context.replay_for_date:
            cached = self._load_replay_establishments(
                context.session,
                target_date=context.replay_for_date,
                naf_codes=context.target_naf_codes,
                reference=context.replay_reference,
            )
            if cached:
                log_event(
                    "sync.day_replay.cached_data",
                    run_id=str(context.run.id),
                    scope_key=context.run.scope_key,
                    target_date=context.replay_for_date.isoformat(),
                    cached_establishment_count=len(cached),
                    force_google=context.force_google_replay,
                    reference=context.replay_reference.value,
                )
                log_event(
                    "sync.debug.exit.201_day_replay_return_cache",
                    run_id=str(context.run.id),
                    scope_key=context.run.scope_key,
                    reason="day_replay_cache_hit",
                    target_date=context.replay_for_date.isoformat(),
                    cached_establishment_count=len(cached),
                )
                return collect_day_replay_from_cache(
                    context,
                    cached,
                    log_alerts=self._log_alerts_created,
                )
            log_event(
                "sync.day_replay.cache_miss",
                run_id=str(context.run.id),
                scope_key=context.run.scope_key,
                target_date=context.replay_for_date.isoformat(),
                reference=context.replay_reference.value,
            )

        if not context.mode.requires_sirene_fetch:
            if context.mode.is_linkedin_only:
                log_event(
                    "sync.debug.exit.202_mode_linkedin_only",
                    run_id=str(context.run.id),
                    scope_key=context.run.scope_key,
                    reason="mode_without_sirene_fetch",
                    mode=context.mode.value,
                )
                return self._collect_linkedin_only(context)
            if context.mode.is_website_scrape_only:
                log_event(
                    "sync.debug.exit.203_mode_website_scrape_only",
                    run_id=str(context.run.id),
                    scope_key=context.run.scope_key,
                    reason="mode_without_sirene_fetch",
                    mode=context.mode.value,
                )
                return self._collect_website_scrape(context)
            log_event(
                "sync.debug.exit.204_mode_google_only",
                run_id=str(context.run.id),
                scope_key=context.run.scope_key,
                reason="mode_without_sirene_fetch",
                mode=context.mode.value,
            )
            return self._collect_google_only(context)

        state = context.state
        should_persist_state = context.persist_state
        replay_for_date = context.replay_for_date
        # months_back: provient du contexte (fourni par l'utilisateur) ou None pour synchro incrémentale
        months_back = context.months_back
        creation_range: tuple[date, date] | None = None
        if replay_for_date:
            creation_range = (replay_for_date, replay_for_date)
        since_creation: date | None = None
        if creation_range is None:
            if months_back is not None:
                # Synchro avec mois dans le passé explicites
                since_creation = subtract_months(self._current_date(), months_back)
            else:
                # Synchro incrémentale standard: utilise le checkpoint existant
                since_creation = self._compute_since_creation_incremental(state)
        if context.target_naf_codes:
            naf_codes = context.target_naf_codes
            append_run_note(context.run, format_target_naf_note(context.target_naf_codes))
            log_event(
                "sync.collection.naf_filter_applied",
                run_id=str(context.run.id),
                scope_key=context.run.scope_key,
                target_naf_codes=context.target_naf_codes,
            )
        else:
            naf_codes = self._load_active_naf_codes(context.session)
        query = self._build_restaurant_query(
            naf_codes,
            since_creation=since_creation,
            creation_range=creation_range,
        )
        checksum = sha256_digest(query)
        context.run.query_checksum = checksum

        if should_persist_state and state.query_checksum and state.query_checksum != checksum:
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
        if should_persist_state:
            state.query_checksum = checksum

        latest_treated = self._fetch_latest_treated(context.client)
        if latest_treated:
            latest_note = f"dateDernierTraitementMaximum: {latest_treated.isoformat()}"
            append_run_note(context.run, latest_note)
            log_event(
                "sync.informations.latest_treated",
                run_id=str(context.run.id),
                scope_key=context.run.scope_key,
                latest_treated=latest_treated,
            )

        champs = self._build_fields_parameter()
        cursor_value = "*"
        if should_persist_state and state.last_cursor and not state.cursor_completed:
            cursor_value = state.last_cursor
        tri = "dateCreationEtablissement desc"

        effective_since = since_creation or (creation_range[0] if creation_range else None)

        page_result = collect_pages(
            self,
            context,
            query=query,
            champs=champs,
            cursor_value=cursor_value,
            tri=tri,
            months_back=months_back if months_back is not None else 0,
            since_creation=effective_since,
            creation_range=creation_range,
            persist_state=should_persist_state,
        )
        new_entities_total = page_result.new_entities
        new_entities_payload = page_result.new_payloads
        updated_entities = page_result.updated_entities
        updated_payloads = page_result.updated_payloads
        annuaire_candidates = page_result.annuaire_candidates

        # --- Annuaire enrichment (director & legal unit name) ---
        annuaire_targets = (
            list(new_entities_total)
            + [info.establishment for info in updated_entities]
            + list(annuaire_candidates)
        )
        unique_targets: dict[str, models.Establishment] = {}
        for establishment in annuaire_targets:
            if establishment.siret:
                unique_targets[establishment.siret] = establishment
        all_touched = list(unique_targets.values())
        annuaire_summary = enrich_establishments_from_annuaire(
            context.session,
            all_touched,
            run_id=str(context.run.id),
        )

        google_immediate_matches: list[models.Establishment] = []
        google_late_matches: list[models.Establishment] = []
        google_matches_payload: list[dict[str, object]] = []
        alerts_payload: list[dict[str, object]] = []
        alerts_created: list[models.Alert] = []
        page_count = page_result.page_count

        google_queue_count = 0
        google_eligible_count = 0
        google_matched_count = 0
        google_pending_count = 0
        google_api_call_count = 0
        google_api_error_count = 0
        linkedin_summary: dict[str, object] = {}
        linkedin_future = None
        linkedin_executor: ThreadPoolExecutor | None = None
        should_parallelize_linkedin = bool(context.mode.google_enabled and context.mode.linkedin_enabled)
        establishment_ids: list[object] = []
        if should_parallelize_linkedin and new_entities_total:
            establishment_ids = [est.id for est in new_entities_total if getattr(est, "id", None)]
            if establishment_ids:
                linkedin_executor = ThreadPoolExecutor(max_workers=1)
                linkedin_future = linkedin_executor.submit(
                    self._run_linkedin_enrichment_parallel,
                    context,
                    establishment_ids,
                )
        google_candidates, force_refresh_google = self._resolve_google_candidates(
            context,
            new_entities_total,
            naf_codes,
        )
        skip_client_alerts_empty_auto_full = (
            context.run.run_type == "sync_auto"
            and context.mode == SyncMode.FULL
            and not new_entities_total
            and not updated_entities
        )
        if skip_client_alerts_empty_auto_full:
            log_event(
                "sync.alerts.client_skipped",
                run_id=str(context.run.id),
                scope_key=context.run.scope_key,
                reason="empty_auto_full_no_sirene_delta",
                run_type=context.run.run_type,
                mode=context.mode.value,
                fetched_records=context.run.fetched_records,
                created_records=context.run.created_records,
                updated_records=context.run.updated_records,
            )

        try:
            if context.mode.google_enabled:
                # Désactiver les alertes si months_back est fourni (rattrapage historique)
                is_backfill = context.months_back is not None
                alerts_enabled = context.mode.dispatch_alerts and not is_backfill
                alert_service = (
                    AlertService(
                        context.session,
                        context.run,
                        client_notifications_enabled=(
                            context.client_notifications_enabled and not skip_client_alerts_empty_auto_full
                        ),
                        admin_notifications_enabled=context.admin_notifications_enabled,
                        target_client_ids=context.target_client_ids,
                    )
                    if alerts_enabled
                    else None
                )
                include_backlog = not force_refresh_google
                progress_callback = create_google_progress_callback(context.session, context.run)
                enrichment_result, alerts_created = run_google_enrichment(
                    session=context.session,
                    targets=google_candidates,
                    include_backlog=include_backlog,
                    reset_google_state=False,
                    recheck_all=force_refresh_google,
                    run=context.run,
                    alert_service=alert_service,
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

                context.run.google_queue_count = google_queue_count
                context.run.google_eligible_count = google_eligible_count
                context.run.google_matched_count = google_matched_count
                context.run.google_pending_count = google_pending_count
                context.run.google_api_call_count = google_api_call_count

                google_error_rate = (
                    round(google_api_error_count / google_api_call_count, 4)
                    if google_api_call_count > 0
                    else 0.0
                )

                log_event(
                    "sync.google.summary",
                    run_id=str(context.run.id),
                    scope_key=context.run.scope_key,
                    queue_count=google_queue_count,
                    eligible_count=google_eligible_count,
                    matched_count=google_matched_count,
                    remaining_count=google_pending_count,
                    api_call_count=google_api_call_count,
                    api_error_count=google_api_error_count,
                    error_rate=google_error_rate,
                    missing_contact_checked_count=missing_contact_checked_count,
                    missing_contact_updated_count=missing_contact_updated_count,
                    retry_backlog_count=retry_backlog_count,
                    retry_backlog_age_buckets=retry_backlog_age_buckets,
                    missing_contact_age_buckets=missing_contact_age_buckets,
                    new_establishment_count=len(new_entities_total),
                    google_candidate_count=len(google_candidates),
                    force_refresh=force_refresh_google,
                    reset_google_state=False,
                    recheck_all=force_refresh_google,
                    include_backlog=include_backlog,
                )

                tag_google_error_rate(
                    context.run,
                    api_call_count=google_api_call_count,
                    api_error_count=google_api_error_count,
                    threshold=0.10,
                    event_name="sync.google.error_rate.high",
                )

                if enrichment_result.matches:
                    for match in enrichment_result.matches:
                        if match.created_run_id == context.run.id:
                            google_immediate_matches.append(match)
                        else:
                            google_late_matches.append(match)
                    context.run.google_immediate_matched_count = len(google_immediate_matches)
                    context.run.google_late_matched_count = len(google_late_matches)

                    google_matches_payload = [serialize_establishment(item) for item in enrichment_result.matches]
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

                alerts_payload = self._log_alerts_created(context.run, alerts_created)
            else:
                log_event(
                    "sync.google.skipped",
                    run_id=str(context.run.id),
                    scope_key=context.run.scope_key,
                    reason="mode_sirene_only",
                )
                context.run.google_queue_count = 0
                context.run.google_eligible_count = 0
                context.run.google_matched_count = 0
                context.run.google_pending_count = 0
                context.run.google_api_call_count = 0
                context.run.google_immediate_matched_count = 0
                context.run.google_late_matched_count = 0
                alerts_payload = []
        finally:
            if linkedin_executor is not None:
                linkedin_executor.shutdown(wait=True)

        # --- LinkedIn enrichment (for physical person directors) ---
        if linkedin_future is not None:
            linkedin_summary = linkedin_future.result()
            self._apply_linkedin_summary(context.run, linkedin_summary)
        else:
            linkedin_summary = self._run_linkedin_enrichment(
                context,
                new_entities_total,
            )

        context.session.commit()

        alerts_payload = self._log_alerts_created(context.run, alerts_created)
        alerts_sent_count = sum(1 for alert in alerts_created if alert.sent_at)
        duration = page_result.duration_seconds
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
            google_queue_count=google_queue_count,
            google_eligible_count=google_eligible_count,
            google_matched_count=google_matched_count,
            google_pending_count=google_pending_count,
            google_api_call_count=google_api_call_count,
            google_immediate_matched_count=context.run.google_immediate_matched_count,
            google_late_matched_count=context.run.google_late_matched_count,
            alerts_created=len(alerts_created),
            alerts_sent=alerts_sent_count,
            latest_creation_date=page_result.max_creation_date,
            target_naf_codes=context.target_naf_codes,
        )

        return SyncResult(
            mode=context.mode,
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
            max_creation_date=page_result.max_creation_date,
            google_queue_count=google_queue_count,
            google_eligible_count=google_eligible_count,
            google_matched_count=google_matched_count,
            google_pending_count=google_pending_count,
            google_api_call_count=google_api_call_count,
            google_api_error_count=google_api_error_count,
            alerts_sent_count=alerts_sent_count,
        )

    def _resolve_google_candidates(
        self,
        context: SyncContext,
        base_candidates: Sequence[models.Establishment],
        naf_codes: Sequence[str],
    ) -> tuple[list[models.Establishment], bool]:
        candidates = list(base_candidates)
        force_refresh = False
        if context.mode == SyncMode.DAY_REPLAY and context.replay_for_date:
            replay_candidates = self._load_replay_establishments(
                context.session,
                target_date=context.replay_for_date,
                naf_codes=context.target_naf_codes or naf_codes,
                reference=context.replay_reference,
            )
            existing_sirets = {est.siret for est in candidates if getattr(est, "siret", None)}
            additional = [
                establishment
                for establishment in replay_candidates
                if establishment.siret and establishment.siret not in existing_sirets
            ]
            if additional:
                candidates.extend(additional)
                existing_sirets.update(establishment.siret for establishment in additional if establishment.siret)
                force_refresh = True
                log_event(
                    "sync.day_replay.rehydrated_candidates",
                    run_id=str(context.run.id),
                    scope_key=context.run.scope_key,
                    target_date=context.replay_for_date.isoformat(),
                    reference=context.replay_reference.value,
                    rehydrated_count=len(additional),
                    total_candidates=len(candidates),
                )
            else:
                log_event(
                    "sync.day_replay.no_additional_candidates",
                    run_id=str(context.run.id),
                    scope_key=context.run.scope_key,
                    target_date=context.replay_for_date.isoformat(),
                    reference=context.replay_reference.value,
                    total_candidates=len(candidates),
                )
        return candidates, force_refresh

    def _log_alerts_created(
        self,
        run: models.SyncRun,
        alerts: Sequence[models.Alert],
    ) -> list[dict[str, object]]:
        if not alerts:
            return []
        alerts_payload = [serialize_alert(alert) for alert in alerts]
        log_event(
            "sync.alerts.created",
            run_id=str(run.id),
            scope_key=run.scope_key,
            count=len(alerts_payload),
            alerts=alerts_payload,
        )
        for alert_payload in alerts_payload:
            log_event(
                "sync.alert.created",
                run_id=str(run.id),
                scope_key=run.scope_key,
                alert=alert_payload,
            )
        return alerts_payload

    def _run_linkedin_enrichment(
        self,
        context: SyncContext,
        establishments: Sequence[models.Establishment],
        *,
        session_override: Session | None = None,
        update_run_counters: bool = True,
    ) -> dict[str, object]:
        """Run LinkedIn enrichment for directors of new establishments.

        Args:
            context: Sync context.
            establishments: Establishments to enrich (typically new ones).

        Returns:
            Summary dict with enrichment statistics.
        """
        from app.services.linkedin import LinkedInLookupService

        if not context.mode.linkedin_enabled:
            log_event(
                "sync.linkedin.skipped",
                run_id=str(context.run.id),
                scope_key=context.run.scope_key,
                reason="mode_linkedin_disabled",
            )
            return {}

        if not establishments:
            log_event(
                "sync.linkedin.skipped",
                run_id=str(context.run.id),
                scope_key=context.run.scope_key,
                reason="no_establishments",
            )
            return {}

        session = session_override or context.session
        update_counters = bool(update_run_counters and session_override is None)
        linkedin_service = LinkedInLookupService(session)
        if not linkedin_service.enabled:
            log_event(
                "sync.linkedin.skipped",
                run_id=str(context.run.id),
                scope_key=context.run.scope_key,
                reason="apify_not_configured",
            )
            return {}

        progress_callback = None
        if update_counters:
            # Create progress callback to update run counters
            def linkedin_progress_callback(
                total: int,
                searched: int,
                found: int,
                not_found: int,
                error: int,
            ) -> None:
                context.run.linkedin_queue_count = total
                context.run.linkedin_searched_count = searched
                context.run.linkedin_found_count = found
                context.run.linkedin_not_found_count = not_found
                context.run.linkedin_error_count = error
                session.flush()

            progress_callback = linkedin_progress_callback

        try:
            result = linkedin_service.enrich_batch(
                establishments,
                run_id=context.run.id,
                force_refresh=False,
                progress_callback=progress_callback,
            )

            # Final update of run counters
            if update_counters:
                context.run.linkedin_queue_count = result.total_directors
                context.run.linkedin_searched_count = result.searched_count
                context.run.linkedin_found_count = result.found_count
                context.run.linkedin_not_found_count = result.not_found_count
                context.run.linkedin_error_count = result.error_count

            summary = {
                "total_directors": result.total_directors,
                "eligible_directors": result.eligible_directors,
                "searched_count": result.searched_count,
                "found_count": result.found_count,
                "not_found_count": result.not_found_count,
                "error_count": result.error_count,
                "skipped_nd_count": result.skipped_nd_count,
                "api_call_count": result.api_call_count,
            }

            log_event(
                "sync.linkedin.summary",
                run_id=str(context.run.id),
                scope_key=context.run.scope_key,
                **summary,
            )

            return summary

        finally:
            linkedin_service.close()

    def _run_linkedin_enrichment_parallel(
        self,
        context: SyncContext,
        establishment_ids: Sequence[object],
    ) -> dict[str, object]:
        if not establishment_ids:
            return {}

        with session_scope() as session:
            stmt = (
                select(models.Establishment)
                .where(models.Establishment.id.in_(establishment_ids))
                .options(selectinload(models.Establishment.directors))
            )
            establishments = session.execute(stmt).scalars().all()
            return self._run_linkedin_enrichment(
                context,
                establishments,
                session_override=session,
                update_run_counters=False,
            )

    def _apply_linkedin_summary(self, run: models.SyncRun, summary: dict[str, object]) -> None:
        if not summary:
            return
        run.linkedin_queue_count = int(summary.get("total_directors") or 0)
        run.linkedin_searched_count = int(summary.get("searched_count") or 0)
        run.linkedin_found_count = int(summary.get("found_count") or 0)
        run.linkedin_not_found_count = int(summary.get("not_found_count") or 0)
        run.linkedin_error_count = int(summary.get("error_count") or 0)

    def _compute_since_creation(self, state: models.SyncState, *, months_back: int) -> date:
        baseline = subtract_months(self._current_date(), months_back)
        return baseline

    def _compute_since_creation_incremental(self, state: models.SyncState) -> date:
        """Compute since_creation for incremental sync (no months_back).

        Always looks back `incremental_lookback_months` (default 1 month) to capture
        administratively backdated establishments.
        """
        lookback_months = max(self._settings.sync.incremental_lookback_months, 0)
        today = self._current_date()

        # Baseline : toujours regarder au moins X mois en arrière
        baseline = subtract_months(today, lookback_months) if lookback_months else today
        return baseline

    def _current_date(self) -> date:
        return utcnow().date()

    def _collect_google_only(self, context: SyncContext) -> SyncResult:
        run = context.run
        mode = context.mode
        if context.target_naf_codes:
            append_run_note(run, format_target_naf_note(context.target_naf_codes))
            log_event(
                "sync.collection.naf_filter_applied",
                run_id=str(run.id),
                scope_key=run.scope_key,
                target_naf_codes=context.target_naf_codes,
            )

        google_statuses = context.google_target_statuses
        if google_statuses:
            append_run_note(run, f"google_refresh_statuses: {', '.join(google_statuses)}")
        targets = load_google_resync_targets(
            context.session,
            mode,
            context.target_naf_codes,
            google_statuses=google_statuses,
        )
        target_count = len(targets)
        note_prefix = "google_refresh_targets" if mode == SyncMode.GOOGLE_REFRESH else "google_pending_targets"
        if target_count:
            run.notes = f"{run.notes + ' | ' if run.notes else ''}{note_prefix}: {target_count}"

        return collect_google_only(
            context=context,
            targets=targets,
            log_alerts=self._log_alerts_created,
        )

    def _collect_linkedin_only(self, context: SyncContext) -> SyncResult:
        """Collect LinkedIn profiles for directors (LinkedIn-only mode)."""
        run = context.run
        mode = context.mode
        if context.target_naf_codes:
            append_run_note(run, format_target_naf_note(context.target_naf_codes))
            log_event(
                "sync.collection.naf_filter_applied",
                run_id=str(run.id),
                scope_key=run.scope_key,
                target_naf_codes=context.target_naf_codes,
            )

        targets = load_linkedin_resync_targets(
            context.session,
            mode,
            target_naf_codes=context.target_naf_codes,
            linkedin_statuses=context.linkedin_target_statuses,
        )
        target_count = len(targets)
        note_prefix = "linkedin_refresh_targets" if mode == SyncMode.LINKEDIN_REFRESH else "linkedin_pending_targets"
        if target_count:
            run.notes = f"{run.notes + ' | ' if run.notes else ''}{note_prefix}: {target_count}"

        return collect_linkedin_only(
            context=context,
            targets=targets,
            log_alerts=self._log_alerts_created,
        )

    def _collect_website_scrape(self, context: SyncContext) -> SyncResult:
        run = context.run
        if context.target_naf_codes:
            append_run_note(run, format_target_naf_note(context.target_naf_codes))
            log_event(
                "sync.collection.naf_filter_applied",
                run_id=str(run.id),
                scope_key=run.scope_key,
                target_naf_codes=context.target_naf_codes,
            )

        website_statuses = getattr(context, "website_scrape_statuses", None)
        if website_statuses:
            append_run_note(run, f"website_scrape_statuses: {', '.join(website_statuses)}")

        targets = load_website_scrape_targets(
            context.session,
            context.target_naf_codes,
            website_statuses=website_statuses,
        )
        target_count = len(targets)
        if target_count:
            run.notes = f"{run.notes + ' | ' if run.notes else ''}website_scrape_targets: {target_count}"

        return collect_website_scrape_only(
            context=context,
            targets=targets,
            log_alerts=self._log_alerts_created,
        )

    def _load_replay_establishments(
        self,
        session: Session,
        *,
        target_date: date,
        naf_codes: Sequence[str] | None = None,
        reference: DayReplayReference | None = None,
    ) -> list[models.Establishment]:
        resolved_reference = reference or DEFAULT_DAY_REPLAY_REFERENCE
        return load_replay_establishments(
            session,
            target_date=target_date,
            naf_codes=naf_codes,
            reference=resolved_reference,
        )

    def _filter_ready_google_matches(
        self,
        establishments: Sequence[models.Establishment],
    ) -> list[models.Establishment]:
        return filter_ready_google_matches(establishments)

