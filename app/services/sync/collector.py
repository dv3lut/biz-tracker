"""Collection helpers for synchronization runs."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from app.db import models
from app.observability import log_event, serialize_alert, serialize_establishment
from app.services.alert_service import AlertService
from app.services.google_business_service import GoogleBusinessService
from app.utils.dates import subtract_months
from app.utils.hashing import sha256_digest

from .context import SyncContext, SyncResult, UpdatedEstablishmentInfo
from .pages import collect_pages
from .persistence import SyncPersistenceMixin


class SyncCollectorMixin(SyncPersistenceMixin):
    """Provide data collection and persistence helpers for sync runs."""

    def _collect_sync(self, context: SyncContext) -> SyncResult:
        state = context.state
        months_back = max(self._settings.sync.months_back, 1)
        since_creation = self._compute_since_creation(state, months_back=months_back)
        naf_codes = self._load_active_naf_codes(context.session)
        query = self._build_restaurant_query(naf_codes, since_creation=since_creation)
        checksum = sha256_digest(query)
        context.run.query_checksum = checksum

        if state.query_checksum and state.query_checksum != checksum:
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
        state.query_checksum = checksum

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
        page_result = collect_pages(
            self,
            context,
            query=query,
            champs=champs,
            cursor_value=cursor_value,
            tri=tri,
            months_back=months_back,
            since_creation=since_creation,
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

        google_service = GoogleBusinessService(context.session)
        last_google_progress: tuple[int, int, int, int, int] | None = None

        def update_google_progress(
            queue_count: int,
            eligible_count: int,
            processed_count: int,
            matched_count: int,
            pending_count: int,
        ) -> None:
            nonlocal last_google_progress
            snapshot = (queue_count, eligible_count, processed_count, matched_count, pending_count)
            if snapshot == last_google_progress:
                return
            last_google_progress = snapshot
            context.run.google_queue_count = queue_count
            context.run.google_eligible_count = eligible_count
            context.run.google_matched_count = matched_count
            context.run.google_pending_count = pending_count
            context.session.flush()
            context.session.commit()

        try:
            enrichment = google_service.enrich(new_entities_total, progress_callback=update_google_progress)
        finally:
            google_service.close()

        context.run.google_queue_count = enrichment.queue_count
        context.run.google_eligible_count = enrichment.eligible_count
        context.run.google_matched_count = enrichment.matched_count
        context.run.google_pending_count = enrichment.remaining_count
        context.run.google_api_call_count = enrichment.api_call_count

        log_event(
            "sync.google.summary",
            run_id=str(context.run.id),
            scope_key=context.run.scope_key,
            queue_count=enrichment.queue_count,
            eligible_count=enrichment.eligible_count,
            matched_count=enrichment.matched_count,
            remaining_count=enrichment.remaining_count,
            api_call_count=enrichment.api_call_count,
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
            google_queue_count=enrichment.queue_count,
            google_eligible_count=enrichment.eligible_count,
            google_matched_count=enrichment.matched_count,
            google_pending_count=enrichment.remaining_count,
            google_api_call_count=enrichment.api_call_count,
            google_immediate_matched_count=context.run.google_immediate_matched_count,
            google_late_matched_count=context.run.google_late_matched_count,
            alerts_created=len(alerts_created),
            alerts_sent=alerts_sent_count,
            latest_creation_date=page_result.max_creation_date,
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
            max_creation_date=page_result.max_creation_date,
            google_queue_count=enrichment.queue_count,
            google_eligible_count=enrichment.eligible_count,
            google_matched_count=enrichment.matched_count,
            google_pending_count=enrichment.remaining_count,
            google_api_call_count=enrichment.api_call_count,
            alerts_sent_count=alerts_sent_count,
        )

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

