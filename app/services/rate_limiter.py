"""Rate limiters.

This module contains small, dependency-free primitives:
- `RateLimiter`: enforces a minimum delay between calls (used for outbound calls).
- `SlidingWindowRateLimiter`: enforces max calls per time window (used for inbound API throttling).
"""
from __future__ import annotations

from collections import deque
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


class SlidingWindowRateLimiter:
    """Sliding window limiter with per-key tracking.

    This is designed for inbound throttling where we must reject requests (429)
    instead of delaying them.
    """

    def __init__(self, *, max_per_second: int, max_per_minute: int) -> None:
        self._max_per_second = max(max_per_second, 1)
        self._max_per_minute = max(max_per_minute, 1)
        self._lock = threading.Lock()
        self._hits_last_second: dict[str, deque[float]] = {}
        self._hits_last_minute: dict[str, deque[float]] = {}

    def reset(self) -> None:
        """Clear internal state (mainly for tests)."""

        with self._lock:
            self._hits_last_second.clear()
            self._hits_last_minute.clear()

    def allow(self, key: str, now: float | None = None) -> bool:
        """Return True if the request should be allowed for this key."""

        if now is None:
            now = time.monotonic()

        with self._lock:
            second_hits = self._hits_last_second.setdefault(key, deque())
            minute_hits = self._hits_last_minute.setdefault(key, deque())

            one_second_ago = now - 1.0
            one_minute_ago = now - 60.0

            while second_hits and second_hits[0] <= one_second_ago:
                second_hits.popleft()
            while minute_hits and minute_hits[0] <= one_minute_ago:
                minute_hits.popleft()

            if len(second_hits) >= self._max_per_second:
                return False
            if len(minute_hits) >= self._max_per_minute:
                return False

            second_hits.append(now)
            minute_hits.append(now)
            return True
