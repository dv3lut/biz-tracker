"""In-memory cancellation registry for synchronization runs.

Since sync runs execute as FastAPI background tasks (same process), a module-level
set is sufficient to signal a cancellation request to the running task.
"""
from __future__ import annotations

_CANCEL_REQUESTED: set[str] = set()


class SyncCancellationError(Exception):
    """Raised when a sync run detects a cancellation request."""


def request_cancel(run_id: str) -> None:
    """Mark a run as pending cancellation."""
    _CANCEL_REQUESTED.add(run_id)


def is_cancel_requested(run_id: str) -> bool:
    """Return True if a cancellation has been requested for the given run."""
    return run_id in _CANCEL_REQUESTED


def clear_cancel(run_id: str) -> None:
    """Remove the cancellation request (call after the run terminates)."""
    _CANCEL_REQUESTED.discard(run_id)


__all__ = [
    "SyncCancellationError",
    "request_cancel",
    "is_cancel_requested",
    "clear_cancel",
]
