import asyncio

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from app.api.middlewares.access_log_middleware import AccessLogMiddleware


def _make_request(
    path: str,
    *,
    method: str = "GET",
    client_ip: str = "127.0.0.1",
    query_string: str = "",
    x_forwarded_for: str | None = None,
    user_agent: str | None = "pytest",
    request_id: str | None = "req-123",
) -> Request:
    headers: list[tuple[bytes, bytes]] = []

    if user_agent is not None:
        headers.append((b"user-agent", user_agent.encode("utf-8")))

    if request_id is not None:
        headers.append((b"x-request-id", request_id.encode("utf-8")))

    if x_forwarded_for is not None:
        headers.append((b"x-forwarded-for", x_forwarded_for.encode("utf-8")))

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": query_string.encode("utf-8"),
        "headers": headers,
        "client": (client_ip, 12345),
        "server": ("testserver", 80),
    }
    return Request(scope)


async def _dummy_app(scope, receive, send) -> None:  # pragma: no cover
    return None


async def _ok_call_next(_request: Request) -> Response:
    return Response("ok", status_code=200)


async def _forbidden_call_next(_request: Request) -> Response:
    raise HTTPException(status_code=403, detail="forbidden")


def test_access_log_emits_api_request_event(monkeypatch) -> None:
    captured: list[tuple[tuple, dict]] = []

    def _fake_log_event(*args, **kwargs) -> None:
        captured.append((args, kwargs))

    monkeypatch.setattr("app.api.middlewares.access_log_middleware.log_event", _fake_log_event)

    middleware = AccessLogMiddleware(app=_dummy_app)

    request = _make_request("/admin/health", method="GET", query_string="a=1")

    response = asyncio.run(middleware.dispatch(request, _ok_call_next))

    assert response.status_code == 200
    assert len(captured) == 1

    (args, kwargs) = captured[0]
    assert args[0] == "api.request"
    assert kwargs["http"]["method"] == "GET"
    assert kwargs["http"]["status_code"] == 200
    assert kwargs["url"]["path"] == "/admin/health"
    assert kwargs["url"]["query"] == "a=1"
    assert kwargs["client"]["ip"] == "127.0.0.1"
    assert kwargs["outcome"] == "success"
    assert kwargs["user_agent"] == "pytest"
    assert kwargs["request_id"] == "req-123"
    assert isinstance(kwargs["duration_ms"], float)
    assert kwargs["duration_ms"] >= 0


def test_access_log_uses_x_forwarded_for_first_ip(monkeypatch) -> None:
    captured: list[tuple[tuple, dict]] = []

    def _fake_log_event(*args, **kwargs) -> None:
        captured.append((args, kwargs))

    monkeypatch.setattr("app.api.middlewares.access_log_middleware.log_event", _fake_log_event)

    middleware = AccessLogMiddleware(app=_dummy_app)

    request = _make_request(
        "/public/contact",
        method="POST",
        client_ip="10.0.0.1",
        x_forwarded_for="203.0.113.42, 10.0.0.1",
        user_agent=None,
        request_id=None,
    )

    response = asyncio.run(middleware.dispatch(request, _ok_call_next))

    assert response.status_code == 200
    assert len(captured) == 1
    (args, kwargs) = captured[0]
    assert args[0] == "api.request"
    assert kwargs["client"]["ip"] == "203.0.113.42"
    assert "user_agent" not in kwargs
    assert "request_id" not in kwargs


def test_access_log_logs_and_reraises_http_exception(monkeypatch) -> None:
    captured: list[tuple[tuple, dict]] = []

    def _fake_log_event(*args, **kwargs) -> None:
        captured.append((args, kwargs))

    monkeypatch.setattr("app.api.middlewares.access_log_middleware.log_event", _fake_log_event)

    middleware = AccessLogMiddleware(app=_dummy_app)

    request = _make_request("/admin/secret", method="GET")

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(middleware.dispatch(request, _forbidden_call_next))

    assert excinfo.value.status_code == 403
    assert len(captured) == 1
    (args, kwargs) = captured[0]
    assert args[0] == "api.request"
    assert kwargs["http"]["status_code"] == 403
    assert kwargs["outcome"] == "client_error"
