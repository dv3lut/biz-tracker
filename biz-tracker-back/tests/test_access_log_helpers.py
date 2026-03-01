from __future__ import annotations

from types import SimpleNamespace

from app.api.middlewares.access_log_middleware import (
    _classify_outcome,
    _extract_client_ip,
    _serialize_exception,
)


def _make_request(headers: dict[str, str] | None = None, client_host: str | None = None):
    return SimpleNamespace(
        headers=headers or {},
        client=SimpleNamespace(host=client_host) if client_host is not None else None,
    )


def test_extract_client_ip_from_xff() -> None:
    request = _make_request(headers={"x-forwarded-for": "1.2.3.4, 5.6.7.8"})
    assert _extract_client_ip(request) == "1.2.3.4"


def test_extract_client_ip_from_client_host() -> None:
    request = _make_request(client_host="9.9.9.9")
    assert _extract_client_ip(request) == "9.9.9.9"


def test_extract_client_ip_unknown() -> None:
    request = _make_request()
    assert _extract_client_ip(request) == "unknown"


def test_classify_outcome() -> None:
    assert _classify_outcome(200) == "success"
    assert _classify_outcome(404) == "client_error"
    assert _classify_outcome(503) == "server_error"


def test_serialize_exception_group() -> None:
    exc = BaseExceptionGroup("boom", [ValueError("bad"), RuntimeError("worse")])
    payload = _serialize_exception(exc)
    assert payload["type"] in {"BaseExceptionGroup", "ExceptionGroup"}
    assert payload["message"].startswith("boom")
    assert len(payload["causes"]) == 2
