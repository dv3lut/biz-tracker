"""Synchronization orchestration service."""
from __future__ import annotations

import logging

from app.config import Settings, get_settings
from app.services.sync.collector import SyncCollectorMixin
from app.services.sync.runner import SyncRunnerMixin
from app.services.sync.summary import SyncSummaryMixin


class SyncService(SyncRunnerMixin, SyncCollectorMixin, SyncSummaryMixin):
    """Run Sirene synchronisations and persist new establishments and alerts."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._logger = logging.getLogger(__name__)

    @property
    def settings(self) -> Settings:
        """Expose cached settings for callers needing direct access."""

        return self._settings

__all__ = ["SyncService"]
