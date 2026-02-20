"""HTTP access logging middleware.

Emits one structured observability event per incoming request.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.observability import log_event


def _extract_client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        first = xff.split(",", 1)[0].strip()
        if first:
            return first

    ip = getattr(getattr(request, "client", None), "host", None)
    return str(ip or "unknown")


def _classify_outcome(status_code: int) -> str:
    if status_code < 400:
        return "success"
    if status_code < 500:
        return "client_error"
    return "server_error"


def _serialize_exception(exc: BaseException) -> dict[str, Any]:
    if isinstance(exc, BaseExceptionGroup):
        return {
            "type": type(exc).__name__,
            "message": str(exc),
            "causes": [_serialize_exception(item) for item in exc.exceptions],
        }
    return {"type": type(exc).__name__, "message": str(exc)}


class AccessLogMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, log_admin_requests: bool = False) -> None:
        super().__init__(app)
        self._log_admin_requests = log_admin_requests

    def _should_log_request(self, path: str) -> bool:
        if path.startswith("/admin") and not self._log_admin_requests:
            return False
        return True

    async def dispatch(self, request: Request, call_next) -> Response:
        started_at = time.perf_counter()
        method = request.method
        path = request.url.path
        query = request.url.query
        ip = _extract_client_ip(request)
        user_agent = request.headers.get("user-agent")
        request_id = request.headers.get("x-request-id")

        try:
            response = await call_next(request)
            status_code = response.status_code
        except HTTPException as exc:
            status_code = int(exc.status_code)
            duration_ms = round((time.perf_counter() - started_at) * 1000.0, 2)
            payload: dict[str, Any] = {
                "http": {"method": method, "status_code": status_code},
                "url": {"path": path, "query": query},
                "client": {"ip": ip},
                "duration_ms": duration_ms,
                "outcome": _classify_outcome(status_code),
            }
            if user_agent:
                payload["user_agent"] = user_agent
            if request_id:
                payload["request_id"] = request_id
            if self._should_log_request(path):
                log_event("api.request", **payload)
            raise
        except BaseExceptionGroup as exc:  # pragma: no cover
            duration_ms = round((time.perf_counter() - started_at) * 1000.0, 2)
            payload = {
                "http": {"method": method, "status_code": 500},
                "url": {"path": path, "query": query},
                "client": {"ip": ip},
                "duration_ms": duration_ms,
                "outcome": "server_error",
                "error": _serialize_exception(exc),
            }
            if user_agent:
                payload["user_agent"] = user_agent
            if request_id:
                payload["request_id"] = request_id
            if self._should_log_request(path):
                log_event("api.request", level=40, **payload)
            raise
        except Exception as exc:  # pragma: no cover
            duration_ms = round((time.perf_counter() - started_at) * 1000.0, 2)
            payload = {
                "http": {"method": method, "status_code": 500},
                "url": {"path": path, "query": query},
                "client": {"ip": ip},
                "duration_ms": duration_ms,
                "outcome": "server_error",
                "error": _serialize_exception(exc),
            }
            if user_agent:
                payload["user_agent"] = user_agent
            if request_id:
                payload["request_id"] = request_id
            if self._should_log_request(path):
                log_event("api.request", level=40, **payload)
            raise

        duration_ms = round((time.perf_counter() - started_at) * 1000.0, 2)
        payload = {
            "http": {"method": method, "status_code": status_code},
            "url": {"path": path, "query": query},
            "client": {"ip": ip},
            "duration_ms": duration_ms,
            "outcome": _classify_outcome(status_code),
        }
        if user_agent:
            payload["user_agent"] = user_agent
        if request_id:
            payload["request_id"] = request_id

        if self._should_log_request(path):
            log_event("api.request", **payload)
        return response
