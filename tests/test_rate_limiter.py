from __future__ import annotations

from app.services.rate_limiter import RateLimiter, SlidingWindowRateLimiter


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


def test_sliding_window_rate_limiter_enforces_per_second_limit() -> None:
    limiter = SlidingWindowRateLimiter(max_per_second=2, max_per_minute=100)

    assert limiter.allow("ip", now=10.0) is True
    assert limiter.allow("ip", now=10.1) is True
    assert limiter.allow("ip", now=10.2) is False

    # Window slides: once we're past 1s, it should allow again.
    assert limiter.allow("ip", now=11.1) is True


def test_sliding_window_rate_limiter_enforces_per_minute_limit() -> None:
    limiter = SlidingWindowRateLimiter(max_per_second=100, max_per_minute=3)

    assert limiter.allow("ip", now=0.0) is True
    assert limiter.allow("ip", now=10.0) is True
    assert limiter.allow("ip", now=20.0) is True
    assert limiter.allow("ip", now=30.0) is False

    # Window slides: once we're past 60s, it should allow again.
    assert limiter.allow("ip", now=61.0) is True


def test_sliding_window_rate_limiter_reset_and_now_default(monkeypatch) -> None:
    limiter = SlidingWindowRateLimiter(max_per_second=0, max_per_minute=0)

    monotonic_values = iter([5.0, 5.0, 5.0])
    monkeypatch.setattr("app.services.rate_limiter.time.monotonic", lambda: next(monotonic_values))

    assert limiter.allow("ip") is True
    assert limiter.allow("ip") is False

    limiter.reset()
    assert limiter.allow("ip") is True
