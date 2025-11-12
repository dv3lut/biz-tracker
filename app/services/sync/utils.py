"""Utility helpers shared across synchronization mixins."""
from __future__ import annotations

import logging
import unicodedata


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


__all__ = ["log_and_print", "normalize_text"]
