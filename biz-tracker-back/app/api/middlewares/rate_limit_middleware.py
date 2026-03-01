"""HTTP rate limiting middleware.

Goal: prevent spam / abusive traffic with a small, dependency-free limiter.

Notes:
- This is an inbound limiter (rejects with 429), not an outbound throttler.
- Limits are applied per client IP, with separate buckets for public endpoints.

Important:
- The outbound throttler lives in `app/services/rate_limiter.py` as `RateLimiter` (sleep/backpressure)
  and is used by external clients (ex: Sirene / Google) to respect provider quotas.
- This middleware uses `SlidingWindowRateLimiter` (also in `app/services/rate_limiter.py`) to protect
  incoming HTTP routes.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.observability import log_event
from app.services.rate_limiter import SlidingWindowRateLimiter


@dataclass(frozen=True)
class RateLimitPolicy:
    max_per_second: int
    max_per_minute: int


def _extract_client_ip(request: Request) -> str:
    # If running behind a proxy/load balancer, X-Forwarded-For is the most common.
    # We keep a simple strategy: first IP in the list.
    xff = request.headers.get("x-forwarded-for")
    if xff:
        first = xff.split(",", 1)[0].strip()
        if first:
            return first

    ip = getattr(getattr(request, "client", None), "host", None)
    return str(ip or "unknown")


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        default_policy: RateLimitPolicy,
        public_policy: RateLimitPolicy,
        excluded_prefixes: tuple[str, ...] = ("/docs", "/redoc", "/openapi.json"),
    ) -> None:
        super().__init__(app)
        self._default_policy = default_policy
        self._public_policy = public_policy
        self._excluded_prefixes = excluded_prefixes

        self._default_limiter = SlidingWindowRateLimiter(
            max_per_second=default_policy.max_per_second,
            max_per_minute=default_policy.max_per_minute,
        )
        self._public_limiter = SlidingWindowRateLimiter(
            max_per_second=public_policy.max_per_second,
            max_per_minute=public_policy.max_per_minute,
        )

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if path == "/" or path.startswith("/health"):
            return await call_next(request)
        if path == "/public/stripe/webhook":
            return await call_next(request)
        if any(path.startswith(prefix) for prefix in self._excluded_prefixes):
            return await call_next(request)

        ip = _extract_client_ip(request)

        limiter = self._public_limiter if path.startswith("/public") else self._default_limiter
        if not limiter.allow(ip):
            log_event("api.rate_limited", ip=ip, path=path)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Trop de requêtes. Veuillez réessayer plus tard.",
                headers={"Retry-After": "1"},
            )

        return await call_next(request)
