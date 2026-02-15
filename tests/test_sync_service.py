from __future__ import annotations

from app.config import Settings
from app.services.sync_service import SyncService


def test_sync_service_exposes_settings() -> None:
    service = SyncService()
    assert isinstance(service.settings, Settings)
