from __future__ import annotations

from app.services.rate_limiter import RateLimiter


def test_rate_limiter_enforces_minimum_interval(monkeypatch):
    limiter = RateLimiter(max_calls_per_minute=2)
    sleep_calls: list[float] = []
    monotonic_values = iter([100.0, 100.1, 100.1, 130.0, 160.0, 160.1])

    monkeypatch.setattr("app.services.rate_limiter.time.sleep", lambda duration: sleep_calls.append(duration))
    monkeypatch.setattr("app.services.rate_limiter.time.monotonic", lambda: next(monotonic_values))

    limiter.acquire()  # primes last call
    limiter.acquire()  # should trigger sleep
    limiter.acquire()  # enough time elapsed, no sleep

    assert sleep_calls == [30.0]
