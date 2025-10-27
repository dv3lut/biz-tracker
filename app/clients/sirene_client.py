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
from app.services.rate_limiter import RateLimiter

_LOGGER = logging.getLogger(__name__)

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MAX_RETRIES = 5
_BACKOFF_FACTOR = 2


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
                "Authorization": f"Bearer {settings.api_token}",
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
            response = self._session.request(method, url, params=params, timeout=self._timeout)
            if response.status_code < 300:
                if not response.content:
                    return {}
                return response.json()
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

    def get_informations(self) -> Dict[str, Any]:
        return self._request("GET", "informations")

    def search_establishments(
        self,
        *,
        query: str,
        nombre: int,
        curseur: Optional[str] = None,
        champs: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"q": query, "nombre": nombre}
        if curseur is not None:
            params["curseur"] = curseur
        if champs:
            params["champs"] = champs
        return self._request("GET", "siret", params=params)
