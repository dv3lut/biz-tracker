"""Shared enumerations for sync modes."""
from __future__ import annotations

from enum import Enum


class SyncMode(str, Enum):
    """Supported run modes for synchronisations."""

    FULL = "full"
    SIRENE_ONLY = "sirene_only"

    @property
    def google_enabled(self) -> bool:
        """Return True when Google enrichment must run."""

        return self is not SyncMode.SIRENE_ONLY


DEFAULT_SYNC_MODE = SyncMode.FULL

__all__ = ["SyncMode", "DEFAULT_SYNC_MODE"]
