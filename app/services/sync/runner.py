"""Run orchestration mixin for synchronization service."""
from __future__ import annotations

import logging
import time
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db import models
from app.db.session import session_scope
from app.observability import log_event, run_context, serialize_sync_run
from app.services.sync.context import SyncContext, SyncResult
from app.services.sync.mode import DEFAULT_SYNC_MODE, SyncMode
from app.utils.dates import utcnow

from .preparation import SyncRunPreparationMixin
from .utils import log_and_print

_LOGGER = logging.getLogger(__name__)


class SyncRunnerMixin(SyncRunPreparationMixin):
    """Expose high-level orchestration helpers reused by the SyncService."""

    def run_sync(
        self,
        session: Session,
    ) -> models.SyncRun:
        run, state = self._initialize_sync_run(session, status="running", mode=DEFAULT_SYNC_MODE)
        with run_context(run.id):
            context = self._build_context(session, run, state)
            log_event(
                "sync.run.started",
                run_id=str(run.id),
                scope_key=run.scope_key,
                triggered_by="cli",
                mode=context.mode.value,
                run=serialize_sync_run(run),
            )
            started_at = time.perf_counter()
            try:
                result = self._collect_sync(context)
                self._finish_run(
                    run,
                    state,
                    last_treated_max=result.last_treated,
                    last_creation_date=result.max_creation_date,
                    mode=result.mode,
                )
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
                    mode=result.mode.value,
                    duration_seconds=duration,
                    result=self._serialize_result(result, email_summary),
                    run=serialize_sync_run(run),
                )
            except Exception as exc:
                session.rollback()
                run.status = "failed"
                run.finished_at = utcnow()
                session.commit()
                log_event(
                    "sync.run.failed",
                    level=logging.ERROR,
                    run_id=str(run.id),
                    scope_key=run.scope_key,
                    run=serialize_sync_run(run),
                    error={"type": type(exc).__name__, "message": str(exc)},
                )
                self._send_run_failure_email(session, run, exc, triggered_by="cli")
                raise
            finally:
                context.client.close()
        return run

    def execute_sync_run(self, run_id: UUID, *, triggered_by: str = "background") -> None:
        with run_context(run_id):
            try:
                with session_scope() as session:
                    run = session.get(models.SyncRun, run_id)
                    if not run:
                        log_event(
                            "sync.run.missing",
                            level=logging.WARNING,
                            run_id=str(run_id),
                        )
                        log_and_print(logging.WARNING, "Run %s introuvable pour la synchronisation.", run_id)
                        return
                    state = self._get_or_create_state(session, run.scope_key)
                    run.status = "running"
                    run.started_at = utcnow()
                    session.commit()

                    log_event(
                        "sync.run.started",
                        run_id=str(run.id),
                        scope_key=run.scope_key,
                        triggered_by=triggered_by,
                        mode=run.mode,
                        run=serialize_sync_run(run),
                    )
                    log_and_print(logging.INFO, "Synchronisation démarrée (run=%s)", run.id)

                    context = self._build_context(session, run, state)
                    started_at = time.perf_counter()
                    try:
                        result = self._collect_sync(context)
                        self._finish_run(
                            run,
                            state,
                            last_treated_max=result.last_treated,
                            last_creation_date=result.max_creation_date,
                            mode=result.mode,
                        )
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
                            triggered_by=triggered_by,
                            mode=result.mode.value,
                            duration_seconds=duration,
                            result=self._serialize_result(result, email_summary),
                            run=serialize_sync_run(run),
                        )
                        log_and_print(
                            logging.INFO,
                            "Synchronisation terminée (run=%s, créés=%s)",
                            run.id,
                            run.created_records,
                        )
                    except Exception as exc:
                        session.rollback()
                        run.status = "failed"
                        run.finished_at = utcnow()
                        session.commit()
                        log_event(
                            "sync.run.failed",
                            level=logging.ERROR,
                            run_id=str(run.id),
                            scope_key=run.scope_key,
                            triggered_by=triggered_by,
                            run=serialize_sync_run(run),
                            error={"type": type(exc).__name__, "message": str(exc)},
                        )
                        self._send_run_failure_email(session, run, exc, triggered_by=triggered_by)
                        raise
                    finally:
                        context.client.close()
            except Exception:
                _LOGGER.exception("Synchronisation asynchrone échouée (run=%s)", run_id)
                print(f"Synchronisation asynchrone échouée (run={run_id})", flush=True)
                with session_scope() as session:
                    run = session.get(models.SyncRun, run_id)
                    if run:
                        run.status = "failed"
                        run.finished_at = utcnow()
                        session.commit()

    def _finish_run(
        self,
        run: models.SyncRun,
        state: models.SyncState,
        *,
        last_treated_max: datetime | None,
        last_creation_date: date | None,
        mode: SyncMode | None = None,
    ) -> None:
        run.status = "success"
        run.finished_at = utcnow()
        try:
            resolved_mode = mode or SyncMode(run.mode)
        except ValueError:
            resolved_mode = DEFAULT_SYNC_MODE

        if not resolved_mode.updates_state:
            log_event(
                "sync.debug.exit.301_skip_state_update_mode",
                run_id=str(run.id),
                scope_key=run.scope_key,
                mode=resolved_mode.value,
                reason="mode_does_not_update_state",
            )
            return

        if run.target_naf_codes:
            log_event(
                "sync.debug.exit.302_skip_state_update_target_naf",
                run_id=str(run.id),
                scope_key=run.scope_key,
                target_naf_codes=run.target_naf_codes,
                reason="target_naf_scope_run",
            )
            return

        state.last_successful_run_id = run.id
        if last_treated_max:
            state.last_treated_max = last_treated_max
        if last_creation_date:
            state.last_creation_date = last_creation_date

    def _serialize_result(self, result: SyncResult, email_summary: dict[str, Any]) -> dict[str, Any]:
        return {
            "page_count": result.page_count,
            "new_establishment_count": len(result.new_establishments),
            "updated_establishment_count": len(result.updated_establishments),
            "google_match_count": result.google_matched_count,
            "mode": result.mode.value,
            "google": {
                "enabled": result.mode.google_enabled,
                "queue_count": result.google_queue_count,
                "eligible_count": result.google_eligible_count,
                "matched_count": result.google_matched_count,
                "immediate_matches": len(result.google_immediate_matches),
                "late_matches": len(result.google_late_matches),
                "pending_count": result.google_pending_count,
                "api_call_count": result.google_api_call_count,
            },
            "alert_count": len(result.alerts),
            "alerts_sent_count": result.alerts_sent_count,
            "email": email_summary,
        }
