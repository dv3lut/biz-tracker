"""Backward compatibility shim for the removed incremental scheduler."""
from __future__ import annotations

from app.services.sync_scheduler import SyncScheduler

__all__ = ["SyncScheduler"]