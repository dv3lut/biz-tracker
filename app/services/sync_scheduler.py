"""Background scheduler triggering unified synchronisations automatically."""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta

from app.config import get_settings
from app.db import models
from app.db.session import session_scope
from app.services.sync.mode import DEFAULT_SYNC_MODE
from app.services.sync_service import SyncService
from app.observability import log_event

_LOGGER = logging.getLogger(__name__)


class SyncScheduler:
    """Background worker periodically issuing unified sync runs."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._service = SyncService()
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._settings.is_local:
            _LOGGER.info("Automatic synchronisation disabled in local environment.")
            log_event(
                "scheduler.disabled",
                scope_key=self._settings.sync.scope_key,
                reason="local_environment",
            )
            return
        if not self._settings.sync.auto_enabled:
            _LOGGER.info("Automatic synchronisation disabled via configuration.")
            log_event(
                "scheduler.disabled",
                scope_key=self._settings.sync.scope_key,
                minutes=self._settings.sync.auto_poll_minutes,
                reason="config_disabled",
            )
            return
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, name="SyncScheduler", daemon=True)
            self._thread.start()
            _LOGGER.info(
                "Automatic synchronisation scheduler started (interval=%s min).",
                self._settings.sync.auto_poll_minutes,
            )
            log_event(
                "scheduler.started",
                scope_key=self._settings.sync.scope_key,
                interval_minutes=self._settings.sync.auto_poll_minutes,
            )

    def stop(self) -> None:
        with self._lock:
            if not self._thread:
                return
            self._stop_event.set()
            self._thread.join(timeout=5)
            self._thread = None
            _LOGGER.info("Automatic synchronisation scheduler stopped.")
            log_event(
                "scheduler.stopped",
                scope_key=self._settings.sync.scope_key,
            )

    def _run_loop(self) -> None:
        interval_seconds = max(self._settings.sync.auto_poll_minutes, 1) * 60
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception:  # pragma: no cover - defensive logging
                _LOGGER.exception("Automatic synchronisation tick failed.")
            self._stop_event.wait(interval_seconds)

    def _tick(self) -> None:
        scope_key = self._service.settings.sync.scope_key
        minimum_delay = timedelta(minutes=self._service.settings.sync.minimum_delay_minutes)

        with session_scope() as session:
            if self._service.has_active_run(session, scope_key):
                _LOGGER.debug("A synchronisation is already active; skipping auto trigger.")
                log_event(
                    "scheduler.skip",
                    reason="active_run",
                    scope_key=scope_key,
                )
                return

            state = session.get(models.SyncState, scope_key)
            if state and state.last_synced_at:
                next_allowed = state.last_synced_at + minimum_delay
                if datetime.utcnow() < next_allowed:
                    _LOGGER.debug("Minimum delay not reached for auto sync (next at %s).", next_allowed)
                    log_event(
                        "scheduler.skip",
                        reason="minimum_delay",
                        scope_key=scope_key,
                        next_allowed=next_allowed,
                    )
                    return

            run = self._service.prepare_sync_run(
                session,
                check_informations=True,
                mode=DEFAULT_SYNC_MODE,
            )
            if not run:
                _LOGGER.debug("No synchronisation to trigger automatically (informations service up-to-date).")
                log_event(
                    "scheduler.skip",
                    reason="no_updates",
                    scope_key=scope_key,
                )
                return

            session.commit()
            session.refresh(run)
            run_id = run.id

        _LOGGER.info("Automatic synchronisation scheduled (run=%s).", run_id)
        log_event(
            "scheduler.run_scheduled",
            run_id=str(run_id),
            scope_key=scope_key,
        )
        worker = threading.Thread(
            target=self._service.execute_sync_run,
            args=(run_id,),
            kwargs={"triggered_by": "scheduler"},
            daemon=True,
            name=f"SyncWorker-{run_id}",
        )
        worker.start()
