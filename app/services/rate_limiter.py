"""Simple token bucket style rate limiter."""
from __future__ import annotations

import threading
import time


class RateLimiter:
    """Enforce a minimum delay between calls."""

    def __init__(self, max_calls_per_minute: int) -> None:
        self._lock = threading.Lock()
        self._interval = 60.0 / max(max_calls_per_minute, 1)
        self._last_call = 0.0

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            wait_time = self._interval - elapsed
            if wait_time > 0:
                time.sleep(wait_time)
            self._last_call = time.monotonic()
