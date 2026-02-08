import asyncio

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from app.api.middlewares.rate_limit_middleware import RateLimitMiddleware, RateLimitPolicy


def _make_request(path: str, *, client_ip: str = "127.0.0.1", x_forwarded_for: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = [(b"user-agent", b"pytest")]
    if x_forwarded_for is not None:
        headers.append((b"x-forwarded-for", x_forwarded_for.encode("utf-8")))

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": headers,
        "client": (client_ip, 12345),
        "server": ("testserver", 80),
    }
    return Request(scope)


async def _ok_call_next(_request: Request) -> Response:
    return Response("ok", status_code=200)


async def _dummy_app(scope, receive, send) -> None:  # pragma: no cover
    return None


def test_public_contact_rate_limited_returns_429() -> None:
    public_policy = RateLimitPolicy(max_per_second=100, max_per_minute=2)
    default_policy = RateLimitPolicy(max_per_second=1000, max_per_minute=1000)

    middleware = RateLimitMiddleware(
        app=_dummy_app,
        public_policy=public_policy,
        default_policy=default_policy,
    )

    request = _make_request("/public/contact", client_ip="10.0.0.1")

    asyncio.run(middleware.dispatch(request, _ok_call_next))
    asyncio.run(middleware.dispatch(request, _ok_call_next))

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(middleware.dispatch(request, _ok_call_next))

    assert excinfo.value.status_code == 429


def test_rate_limit_uses_x_forwarded_for_first_ip() -> None:
    public_policy = RateLimitPolicy(max_per_second=100, max_per_minute=1)
    default_policy = RateLimitPolicy(max_per_second=1000, max_per_minute=1000)

    middleware = RateLimitMiddleware(
        app=_dummy_app,
        public_policy=public_policy,
        default_policy=default_policy,
    )

    request = _make_request(
        "/public/contact",
        client_ip="10.0.0.1",
        x_forwarded_for="203.0.113.42, 10.0.0.1",
    )

    asyncio.run(middleware.dispatch(request, _ok_call_next))

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(middleware.dispatch(request, _ok_call_next))

    assert excinfo.value.status_code == 429


def test_rate_limit_skips_docs_and_openapi_paths() -> None:
    public_policy = RateLimitPolicy(max_per_second=1, max_per_minute=1)
    default_policy = RateLimitPolicy(max_per_second=1, max_per_minute=1)

    middleware = RateLimitMiddleware(
        app=_dummy_app,
        public_policy=public_policy,
        default_policy=default_policy,
    )

    # Should not raise even if limit is 1/min.
    for path in ("/docs", "/redoc", "/openapi.json"):
        request = _make_request(path)
        asyncio.run(middleware.dispatch(request, _ok_call_next))
        asyncio.run(middleware.dispatch(request, _ok_call_next))
        asyncio.run(middleware.dispatch(request, _ok_call_next))


def test_rate_limit_skips_root_and_health_paths() -> None:
    public_policy = RateLimitPolicy(max_per_second=1, max_per_minute=1)
    default_policy = RateLimitPolicy(max_per_second=1, max_per_minute=1)

    middleware = RateLimitMiddleware(
        app=_dummy_app,
        public_policy=public_policy,
        default_policy=default_policy,
    )

    for path in ("/", "/health", "/health/live", "/health/ready"):
        request = _make_request(path)
        asyncio.run(middleware.dispatch(request, _ok_call_next))
        asyncio.run(middleware.dispatch(request, _ok_call_next))


def test_rate_limit_skips_public_stripe_webhook() -> None:
    public_policy = RateLimitPolicy(max_per_second=1, max_per_minute=1)
    default_policy = RateLimitPolicy(max_per_second=1, max_per_minute=1)

    middleware = RateLimitMiddleware(
        app=_dummy_app,
        public_policy=public_policy,
        default_policy=default_policy,
    )

    request = _make_request("/public/stripe/webhook")
    asyncio.run(middleware.dispatch(request, _ok_call_next))
    asyncio.run(middleware.dispatch(request, _ok_call_next))
