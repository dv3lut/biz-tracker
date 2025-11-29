"""Collection helpers for synchronization runs."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Sequence

from sqlalchemy.orm import Session

from app.db import models
from app.observability import log_event, serialize_alert, serialize_establishment
from app.services.alert_service import AlertService
from app.services.sync.day_replay import (
    collect_day_replay_from_cache,
    filter_ready_google_matches,
    load_replay_establishments,
)
from app.services.sync.google_enrichment import create_google_progress_callback, run_google_enrichment
from app.services.sync.google_only import collect_google_only, load_google_resync_targets
from app.services.sync.mode import SyncMode
from app.utils.dates import subtract_months
from app.utils.hashing import sha256_digest

from .context import SyncContext, SyncResult, UpdatedEstablishmentInfo
from .pages import collect_pages
from .persistence import SyncPersistenceMixin
from .utils import append_run_note, format_target_naf_note


class SyncCollectorMixin(SyncPersistenceMixin):
    """Provide data collection and persistence helpers for sync runs."""

    def _collect_sync(self, context: SyncContext) -> SyncResult:
        if context.mode == SyncMode.DAY_REPLAY and context.replay_for_date:
            cached = self._load_replay_establishments(
                context.session,
                target_date=context.replay_for_date,
                naf_codes=context.target_naf_codes,
            )
            if cached:
                log_event(
                    "sync.day_replay.cached_data",
                    run_id=str(context.run.id),
                    scope_key=context.run.scope_key,
                    target_date=context.replay_for_date.isoformat(),
                    cached_establishment_count=len(cached),
                    force_google=context.force_google_replay,
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
            )

        if not context.mode.requires_sirene_fetch:
            return self._collect_google_only(context)

        state = context.state
        should_persist_state = context.persist_state
        replay_for_date = context.replay_for_date
        months_back = max(self._settings.sync.months_back, 1)
        creation_range: tuple[date, date] | None = None
        if replay_for_date:
            creation_range = (replay_for_date, replay_for_date)
        since_creation: date | None = None
        if creation_range is None:
            since_creation = self._compute_since_creation(state, months_back=months_back)
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
            state.last_creation_date = None
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
            months_back=months_back,
            since_creation=effective_since,
            creation_range=creation_range,
            persist_state=should_persist_state,
        )
        new_entities_total = page_result.new_entities
        new_entities_payload = page_result.new_payloads
        updated_entities = page_result.updated_entities
        updated_payloads = page_result.updated_payloads
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
        google_candidates, force_refresh_google = self._resolve_google_candidates(
            context,
            new_entities_total,
            naf_codes,
        )

        if context.mode.google_enabled:
            alert_service = AlertService(
                context.session,
                context.run,
                client_notifications_enabled=context.client_notifications_enabled,
                admin_notifications_enabled=context.admin_notifications_enabled,
                target_client_ids=context.target_client_ids,
            )
            include_backlog = not force_refresh_google
            progress_callback = create_google_progress_callback(context.session, context.run)
            enrichment_result, alerts_created = run_google_enrichment(
                session=context.session,
                targets=google_candidates,
                include_backlog=include_backlog,
                force_refresh=force_refresh_google,
                alert_service=alert_service,
                progress_callback=progress_callback,
            )

            google_queue_count = enrichment_result.queue_count
            google_eligible_count = enrichment_result.eligible_count
            google_matched_count = enrichment_result.matched_count
            google_pending_count = enrichment_result.pending_count
            google_api_call_count = enrichment_result.api_call_count

            context.run.google_queue_count = google_queue_count
            context.run.google_eligible_count = google_eligible_count
            context.run.google_matched_count = google_matched_count
            context.run.google_pending_count = google_pending_count
            context.run.google_api_call_count = google_api_call_count

            log_event(
                "sync.google.summary",
                run_id=str(context.run.id),
                scope_key=context.run.scope_key,
                queue_count=google_queue_count,
                eligible_count=google_eligible_count,
                matched_count=google_matched_count,
                remaining_count=google_pending_count,
                api_call_count=google_api_call_count,
                new_establishment_count=len(new_entities_total),
                google_candidate_count=len(google_candidates),
                force_refresh=force_refresh_google,
                include_backlog=include_backlog,
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
                    rehydrated_count=len(additional),
                    total_candidates=len(candidates),
                )
            else:
                log_event(
                    "sync.day_replay.no_additional_candidates",
                    run_id=str(context.run.id),
                    scope_key=context.run.scope_key,
                    target_date=context.replay_for_date.isoformat(),
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

    def _compute_since_creation(self, state: models.SyncState, *, months_back: int) -> date:
        baseline = subtract_months(self._current_date(), months_back)
        last_creation = state.last_creation_date
        if not last_creation:
            return baseline

        overlap_days = max(self._settings.sync.creation_overlap_days, 0)
        candidate = last_creation - timedelta(days=overlap_days)
        today = self._current_date()
        if candidate > today:
            candidate = today
        if candidate < baseline:
            candidate = baseline
        return candidate

    def _current_date(self) -> date:
        return datetime.utcnow().date()

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

        targets = load_google_resync_targets(context.session, mode, context.target_naf_codes)
        target_count = len(targets)
        note_prefix = "google_refresh_targets" if mode == SyncMode.GOOGLE_REFRESH else "google_pending_targets"
        if target_count:
            run.notes = f"{run.notes + ' | ' if run.notes else ''}{note_prefix}: {target_count}"

        return collect_google_only(
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
    ) -> list[models.Establishment]:
        return load_replay_establishments(
            session,
            target_date=target_date,
            naf_codes=naf_codes,
        )

    def _filter_ready_google_matches(
        self,
        establishments: Sequence[models.Establishment],
    ) -> list[models.Establishment]:
        return filter_ready_google_matches(establishments)

