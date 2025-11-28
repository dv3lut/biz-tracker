"""Preparation helpers for synchronization runs."""
from __future__ import annotations

import logging
from datetime import datetime, date
from typing import Optional

from sqlalchemy.orm import Session

from app.clients.sirene_client import SireneClient
from app.db import models
from app.observability import log_event, serialize_sync_run
from app.services.sync.context import SyncContext
from app.services.sync.mode import DEFAULT_SYNC_MODE, SyncMode
from app.utils.dates import parse_datetime

from .utils import append_run_note, format_target_naf_note, normalize_text

_LOGGER = logging.getLogger(__name__)


class SyncRunPreparationMixin:
    """Expose helpers to prepare and inspect sync runs before execution."""

    def prepare_sync_run(
        self,
        session: Session,
        *,
        check_informations: bool = False,
        mode: SyncMode = DEFAULT_SYNC_MODE,
        replay_for_date: date | None = None,
        target_naf_codes: list[str] | None = None,
    ) -> Optional[models.SyncRun]:
        scope_key = self._settings.sync.scope_key
        state = self._get_or_create_state(session, scope_key)
        latest_treated: datetime | None = None
        naf_filter = target_naf_codes or None

        if mode.requires_replay_date:
            if replay_for_date is None:
                raise ValueError("Une date doit être fournie pour le mode 'day_replay'.")
            if replay_for_date > datetime.utcnow().date():
                raise ValueError("Impossible de rejouer une journée future.")
            run = self._start_run(
                session,
                scope_key=scope_key,
                run_type="sync_replay",
                initial_status="pending",
                mode=mode,
            )
            run.replay_for_date = replay_for_date
            formatted_date = replay_for_date.isoformat()
            append_run_note(run, f"Rejeu du {formatted_date}")
            run.target_naf_codes = naf_filter
            if naf_filter:
                append_run_note(run, format_target_naf_note(naf_filter))
            log_event(
                "sync.run.prepared",
                run_id=str(run.id),
                scope_key=run.scope_key,
                status=run.status,
                check_informations=False,
                mode=mode.value,
                replay_for_date=formatted_date,
                target_naf_codes=naf_filter,
                run=serialize_sync_run(run),
            )
            return run

        if mode.requires_sirene_fetch and check_informations:
            latest_treated = self._fetch_latest_treated()
            if latest_treated and state.last_treated_max and latest_treated <= state.last_treated_max:
                _LOGGER.info(
                    "Aucune mise à jour détectée depuis la dernière exécution (%s).",
                    state.last_treated_max,
                )
                log_event(
                    "sync.run.skipped_no_changes",
                    scope_key=scope_key,
                    last_known_treated=state.last_treated_max,
                    latest_treated=latest_treated,
                )
                return None

        if mode.requires_sirene_fetch:
            run, _state = self._initialize_sync_run(
                session,
                status="pending",
                state=state,
                mode=mode,
            )
        else:
            run = self._start_run(
                session,
                scope_key=scope_key,
                run_type="google_sync",
                initial_status="pending",
                mode=mode,
            )
        if latest_treated:
            append_run_note(run, f"dateDernierTraitementMaximum: {latest_treated.isoformat()}")
        run.target_naf_codes = naf_filter
        if naf_filter:
            append_run_note(run, format_target_naf_note(naf_filter))
        log_event(
            "sync.run.prepared",
            run_id=str(run.id),
            scope_key=run.scope_key,
            status=run.status,
            check_informations=check_informations,
            mode=mode.value,
            target_naf_codes=naf_filter,
            run=serialize_sync_run(run),
        )
        return run

    def has_active_run(self, session: Session, scope_key: str) -> bool:
        active_statuses = ("running", "pending")
        existing = (
            session.query(models.SyncRun.id)
            .filter(models.SyncRun.scope_key == scope_key, models.SyncRun.status.in_(active_statuses))
            .first()
        )
        return existing is not None

    def _fetch_latest_treated(self, client: Optional[SireneClient] = None) -> datetime | None:
        owned_client = client is None
        client = client or SireneClient()
        try:
            infos = client.get_informations()
        finally:
            if owned_client:
                client.close()

        collection = self._extract_collection_info(infos, "etablissements") if isinstance(infos, dict) else None
        if not collection:
            return None

        latest_treated = parse_datetime(collection.get("dateDernierTraitementMaximum"))
        if not latest_treated:
            return None
        return latest_treated

    def _initialize_sync_run(
        self,
        session: Session,
        *,
        status: str,
        state: Optional[models.SyncState] = None,
        mode: SyncMode = DEFAULT_SYNC_MODE,
    ) -> tuple[models.SyncRun, models.SyncState]:
        scope_key = self._settings.sync.scope_key
        state = state or self._get_or_create_state(session, scope_key)
        missing_run_id: str | None = None
        if state.last_successful_run_id:
            existing_last_run = session.get(models.SyncRun, state.last_successful_run_id)
            if existing_last_run is None:
                missing_run_id = str(state.last_successful_run_id)
                state.last_successful_run_id = None
                state.last_treated_max = None
                state.last_creation_date = None

        previous_cursor = state.last_cursor
        cursor_was_completed = state.cursor_completed

        run = self._start_run(
            session,
            scope_key=scope_key,
            run_type="sync",
            initial_status=status,
            mode=mode,
        )

        state.last_cursor = None
        state.cursor_completed = False

        if missing_run_id or previous_cursor or cursor_was_completed:
            reason = "missing_history" if missing_run_id else "forced_fresh_run"
            log_event(
                "sync.cursor.reset",
                run_id=str(run.id),
                scope_key=scope_key,
                reason=reason,
                missing_run_id=missing_run_id,
            )
        return run, state

    def _start_run(
        self,
        session: Session,
        *,
        scope_key: str,
        run_type: str,
        initial_status: str,
        mode: SyncMode = DEFAULT_SYNC_MODE,
    ) -> models.SyncRun:
        run = models.SyncRun(scope_key=scope_key, run_type=run_type, status=initial_status, mode=mode.value)
        session.add(run)
        session.flush()
        return run

    def _get_or_create_state(self, session: Session, scope_key: str) -> models.SyncState:
        state = session.get(models.SyncState, scope_key)
        if not state:
            state = models.SyncState(scope_key=scope_key)
            session.add(state)
            session.flush()
        return state

    def _extract_collection_info(self, payload: dict[str, object], name: str) -> Optional[dict[str, object]]:
        if not isinstance(payload, dict):
            return None
        normalized_target = normalize_text(name)

        def matches(candidate: object) -> bool:
            if not isinstance(candidate, str):
                return False
            return normalize_text(candidate) == normalized_target

        dates_updates = payload.get("datesDernieresMisesAJourDesDonnees")
        if isinstance(dates_updates, list):
            for item in dates_updates:
                if isinstance(item, dict) and matches(item.get("collection")):
                    return item

        possible_keys = ["collections", "collection", "datasets", "data"]
        for key in possible_keys:
            value = payload.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        if any(matches(item.get(field)) for field in ("nom", "name", "collection")):
                            return item
                    nested = self._extract_collection_info(item, name)
                    if nested:
                        return nested
            elif isinstance(value, dict):
                nested = self._extract_collection_info(value, name)
                if nested:
                    return nested
        for key, nested_value in payload.items():
            if matches(key) and isinstance(nested_value, dict):
                return nested_value
        for item in payload.values():
            if isinstance(item, dict):
                nested = self._extract_collection_info(item, name)
                if nested:
                    return nested
        return None

    def _build_context(self, session: Session, run: models.SyncRun, state: models.SyncState) -> SyncContext:
        client = SireneClient()
        try:
            mode = SyncMode(run.mode)
        except ValueError:
            mode = DEFAULT_SYNC_MODE
        replay_for_date = run.replay_for_date
        target_naf_codes = list(run.target_naf_codes or [])
        persist_state = mode.updates_state and not target_naf_codes
        return SyncContext(
            session=session,
            run=run,
            state=state,
            client=client,
            settings=self._settings,
            mode=mode,
            replay_for_date=replay_for_date,
            persist_state=persist_state,
            client_notifications_enabled=mode.client_notifications_enabled,
            target_naf_codes=target_naf_codes or None,
        )
