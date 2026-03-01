from __future__ import annotations


def test_rate_limit_compat_exports():
    from app.api.middlewares.rate_limit import RateLimitMiddleware, RateLimitPolicy

    assert RateLimitMiddleware is not None
    assert RateLimitPolicy is not None
