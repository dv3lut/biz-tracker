"""Utility helpers shared across synchronization mixins."""
from __future__ import annotations

import logging
import unicodedata
from typing import Sequence

from app.db import models
from app.observability import log_event


_LOGGER = logging.getLogger(__name__)


def log_and_print(level: int, message: str, *args: object) -> None:
    """Log the message and mirror it to stdout for realtime visibility."""

    rendered = message % args if args else message
    print(rendered, flush=True)
    _LOGGER.log(level, message, *args)


def normalize_text(value: str) -> str:
    """Return a lowercase ASCII-only representation of the provided value."""

    normalized = unicodedata.normalize("NFKD", value)
    stripped = "".join(char for char in normalized if not unicodedata.combining(char))
    return stripped.lower()


def append_run_note(run: models.SyncRun, note: str) -> None:
    """Append a human-readable note to the provided run."""

    if not note:
        return
    existing = run.notes or ""
    run.notes = f"{existing + ' | ' if existing else ''}{note}"


def tag_google_error_rate(
    run: models.SyncRun,
    *,
    api_call_count: int,
    api_error_count: int,
    threshold: float = 0.10,
    event_name: str = "sync.google.error_rate.high",
) -> None:
    """Tag/log une sync lorsque le taux d'erreurs Google dépasse le seuil.

    - Ajoute une note lisible dans run.notes
    - Émet un log_event dédié (pour dashboards/alerting)
    """

    if api_call_count <= 0:
        return
    if api_error_count <= 0:
        return

    error_rate = api_error_count / api_call_count
    if error_rate < threshold:
        return

    percent = round(error_rate * 100, 1)
    append_run_note(run, f"ALERTE Google: {api_error_count}/{api_call_count} erreurs ({percent}%)")
    log_event(
        event_name,
        run_id=str(run.id),
        scope_key=run.scope_key,
        api_call_count=api_call_count,
        api_error_count=api_error_count,
        error_rate=round(error_rate, 4),
        threshold=threshold,
    )


def format_target_naf_note(naf_codes: Sequence[str]) -> str:
    """Return a concise note describing the targeted NAF filters."""

    codes = [code for code in naf_codes if code]
    if not codes:
        return ""
    preview = ", ".join(codes[:5])
    remaining = len(codes) - len(codes[:5])
    if remaining > 0:
        return f"NAF ciblées: {preview} (+{remaining})"
    return f"NAF ciblées: {preview}"


__all__ = [
    "append_run_note",
    "format_target_naf_note",
    "log_and_print",
    "normalize_text",
    "tag_google_error_rate",
]
