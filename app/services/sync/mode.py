"""Shared enumerations for sync modes."""
from __future__ import annotations

from enum import Enum


class SyncMode(str, Enum):
    """Supported run modes for synchronisations."""

    FULL = "full"
    SIRENE_ONLY = "sirene_only"
    GOOGLE_PENDING = "google_pending"
    GOOGLE_REFRESH = "google_refresh"

    @property
    def google_enabled(self) -> bool:
        """Return True when Google enrichment must run."""

        return self is not SyncMode.SIRENE_ONLY

    @property
    def requires_sirene_fetch(self) -> bool:
        """Return True when the Sirene collector must run."""

        return self not in {SyncMode.GOOGLE_PENDING, SyncMode.GOOGLE_REFRESH}

    @property
    def is_google_only(self) -> bool:
        """Return True when the run exclusively targets Google enrichment."""

        return self in {SyncMode.GOOGLE_PENDING, SyncMode.GOOGLE_REFRESH}

    @property
    def dispatch_alerts(self) -> bool:
        """Return True when Google alerts should be sent."""

        return self in {SyncMode.FULL, SyncMode.GOOGLE_PENDING}


DEFAULT_SYNC_MODE = SyncMode.FULL

__all__ = ["SyncMode", "DEFAULT_SYNC_MODE"]
