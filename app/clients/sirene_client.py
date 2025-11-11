"""Client for the Sirene API."""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import requests
from requests import Response, Session

from app.config import get_settings
from app.observability import log_event
from app.services.rate_limiter import RateLimiter

_LOGGER = logging.getLogger(__name__)

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MAX_RETRIES = 5
_BACKOFF_FACTOR = 2
_RESPONSE_PREVIEW_LIMIT = 400


class SireneClient:
    """HTTP client with rate limiting and retry logic for the Sirene API."""

    def __init__(self) -> None:
        settings = get_settings().sirene
        self._base_url = settings.api_base_url.rstrip("/") + "/"
        self._timeout = settings.request_timeout_seconds
        self._session: Session = requests.Session()
        self._session.headers.update(
            {
                "Accept": "application/json",
                "X-INSEE-Api-Key-Integration": settings.api_token,
            }
        )
        self._rate_limiter = RateLimiter(settings.max_calls_per_minute)

    def close(self) -> None:
        self._session.close()

    def _request(self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = urljoin(self._base_url, path.lstrip("/"))
        backoff = 1
        for attempt in range(1, _MAX_RETRIES + 1):
            self._rate_limiter.acquire()
            start_time = time.perf_counter()
            response = self._session.request(method, url, params=params, timeout=self._timeout)
            duration_ms = (time.perf_counter() - start_time) * 1000
            preview = response.text[:_RESPONSE_PREVIEW_LIMIT]
            outcome = self._classify_outcome(response.status_code, attempt)
            self._log_debug_attempt(method, url, response.status_code, duration_ms, attempt, params, preview)
            self._record_external_call(
                method=method,
                url=url,
                path=path,
                params=params,
                status_code=response.status_code,
                duration_ms=duration_ms,
                attempt=attempt,
                outcome=outcome,
                response_size=len(response.content or b""),
                response_preview=preview,
            )
            if response.status_code < 300:
                if not response.content:
                    return {}
                return response.json()

            if response.status_code == 404:
                fallback = self._handle_not_found_response(response)
                if fallback is not None:
                    _LOGGER.info("Sirene API: aucune donnée pour la requête (404).")
                    return fallback
            if response.status_code not in _RETRYABLE_STATUS:
                self._log_error(response)
                response.raise_for_status()
            retry_after = self._compute_retry_after(response, backoff)
            _LOGGER.warning(
                "Sirene API request failed (status=%s, attempt=%s/%s). Retrying in %.1fs.",
                response.status_code,
                attempt,
                _MAX_RETRIES,
                retry_after,
            )
            time.sleep(retry_after)
            backoff *= _BACKOFF_FACTOR
        self._log_error(response)
        response.raise_for_status()
        raise RuntimeError("Sirene API request failed")

    def _compute_retry_after(self, response: Response, backoff: int) -> float:
        if "Retry-After" in response.headers:
            try:
                return float(response.headers["Retry-After"])
            except ValueError:
                pass
        return float(backoff)

    def _log_error(self, response: Response) -> None:
        try:
            payload = response.json()
        except json.JSONDecodeError:
            payload = response.text
        _LOGGER.error("Sirene API error %s: %s", response.status_code, payload)

    def _log_debug_attempt(
        self,
        method: str,
        url: str,
        status_code: int,
        duration_ms: float,
        attempt: int,
        params: Optional[Dict[str, Any]],
        response_preview: str,
    ) -> None:
        if not _LOGGER.isEnabledFor(logging.DEBUG):
            return
        _LOGGER.debug(
            "Sirene API call (%s %s) status=%s duration=%.1fms attempt=%s params=%s response_preview=%s",
            method,
            url,
            status_code,
            duration_ms,
            attempt,
            params,
            response_preview,
        )

    def _record_external_call(
        self,
        *,
        method: str,
        url: str,
        path: str,
        params: Optional[Dict[str, Any]],
        status_code: int,
        duration_ms: float,
        attempt: int,
        outcome: str,
        response_size: int,
        response_preview: str,
    ) -> None:
        log_event(
            "external.call",
            external={
                "service": "sirene",
                "endpoint": path,
                "url": url,
                "attempt": attempt,
                "attempt_max": _MAX_RETRIES,
                "outcome": outcome,
            },
            http={"method": method, "status_code": status_code},
            duration_ms=round(duration_ms, 2),
            response={"bytes": response_size, "preview": response_preview},
            params=params or {},
        )

    def _classify_outcome(self, status_code: int, attempt: int) -> str:
        if status_code < 300:
            return "success"
        if status_code == 404:
            return "not_found"
        if status_code in _RETRYABLE_STATUS and attempt < _MAX_RETRIES:
            return "retry"
        return "failure"

    def get_informations(self) -> Dict[str, Any]:
        return self._request("GET", "informations")

    def search_establishments(
        self,
        *,
        query: str,
        nombre: int,
        curseur: Optional[str] = None,
        champs: Optional[str] = None,
        date: Optional[str] = None,
        tri: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"q": query, "nombre": nombre}
        if curseur is not None:
            params["curseur"] = curseur
        if champs:
            params["champs"] = champs
        if date:
            params["date"] = date
        if tri:
            params["tri"] = tri
        return self._request("GET", "siret", params=params)

    def _handle_not_found_response(self, response: Response) -> Dict[str, Any] | None:
        try:
            payload = response.json()
        except json.JSONDecodeError:
            return None

        if not isinstance(payload, dict):
            return None

        header = payload.get("header")
        message = ""
        if isinstance(header, dict):
            message = str(header.get("message") or "")

        if "Aucun élément trouvé" not in message:
            return None

        payload.setdefault("header", {})
        payload.setdefault("etablissements", [])
        return payload
