"""Client utilitaire pour les appels Google Places."""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import requests
from requests import Response, Session

from app.config import get_settings
from app.observability import log_event

_LOGGER = logging.getLogger(__name__)

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_TIMEOUT_SECONDS = 10
_RESPONSE_PREVIEW_LIMIT = 400


class GooglePlacesError(RuntimeError):
    """Erreur levée lors d'un appel Google Places."""


class GooglePlacesClient:
    """Client minimaliste pour interroger Google Places (Find Place + Details)."""

    def __init__(self) -> None:
        settings = get_settings().google
        if not settings.enabled:
            raise GooglePlacesError("Google Places API key is not configured.")

        self._find_place_url = settings.find_place_url
        self._place_details_url = settings.place_details_url
        self._language = settings.language
        self._api_key = settings.api_key or ""
        self._session: Session = requests.Session()
        self._session.headers.update({"Accept": "application/json"})

    def close(self) -> None:
        self._session.close()

    def find_place(self, query: str, *, fields: Optional[str] = None) -> list[dict[str, Any]]:
        params: Dict[str, Any] = {
            "input": query,
            "inputtype": "textquery",
            "language": self._language,
            "key": self._api_key,
        }
        if fields:
            params["fields"] = fields
        payload = self._request(self._find_place_url, params=params, operation="find_place")
        candidates = payload.get("candidates")
        if not isinstance(candidates, list):
            return []
        return [candidate for candidate in candidates if isinstance(candidate, dict)]

    def get_place_details(self, place_id: str, *, fields: Optional[str] = None) -> dict[str, Any] | None:
        params: Dict[str, Any] = {
            "place_id": place_id,
            "language": self._language,
            "key": self._api_key,
        }
        if fields:
            params["fields"] = fields
        payload = self._request(self._place_details_url, params=params, operation="place_details")
        result = payload.get("result")
        if not isinstance(result, dict):
            return None
        return result

    def _request(self, url: str, *, params: Dict[str, Any], operation: str) -> Dict[str, Any]:
        last_response: Optional[Response] = None
        for attempt in range(1, _MAX_RETRIES + 1):
                start_time = time.perf_counter()
                response = self._session.get(url, params=params, timeout=_TIMEOUT_SECONDS)
                duration_ms = (time.perf_counter() - start_time) * 1000
                preview = response.text[:_RESPONSE_PREVIEW_LIMIT]
                sanitized_params = self._sanitize_params(params)
                response_size = len(response.content or b"")
                last_response = response

                self._log_debug_attempt(operation, url, sanitized_params, response.status_code, duration_ms, attempt, preview)

                if response.status_code < 300:
                    try:
                        payload = response.json()
                    except ValueError as exc:  # pragma: no cover - defensive fallback
                        self._record_external_call(
                            operation=operation,
                            url=url,
                            params=sanitized_params,
                            status_code=response.status_code,
                            duration_ms=duration_ms,
                            attempt=attempt,
                            outcome="invalid_json",
                            response_size=response_size,
                            response_preview=preview,
                        )
                        raise GooglePlacesError("Réponse Google Places invalide") from exc

                    self._record_external_call(
                        operation=operation,
                        url=url,
                        params=sanitized_params,
                        status_code=response.status_code,
                        duration_ms=duration_ms,
                        attempt=attempt,
                        outcome="success",
                        response_size=response_size,
                        response_preview=preview,
                    )
                    return payload

                if response.status_code not in _RETRYABLE_STATUS:
                    self._record_external_call(
                        operation=operation,
                        url=url,
                        params=sanitized_params,
                        status_code=response.status_code,
                        duration_ms=duration_ms,
                        attempt=attempt,
                        outcome="failure",
                        response_size=response_size,
                        response_preview=preview,
                    )
                    raise GooglePlacesError(
                        f"Google Places call failed (status={response.status_code}, body={response.text[:200]})"
                    )

                if attempt == _MAX_RETRIES:
                    self._record_external_call(
                        operation=operation,
                        url=url,
                        params=sanitized_params,
                        status_code=response.status_code,
                        duration_ms=duration_ms,
                        attempt=attempt,
                        outcome="failure",
                        response_size=response_size,
                        response_preview=preview,
                    )
                    break

                self._record_external_call(
                    operation=operation,
                    url=url,
                    params=sanitized_params,
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                    attempt=attempt,
                    outcome="retry",
                    response_size=response_size,
                    response_preview=preview,
                )
                _LOGGER.warning(
                    "Appel Google Places échoué (status=%s, tentative %s/%s).",
                    response.status_code,
                    attempt,
                    _MAX_RETRIES,
                )

        if last_response is not None:
            raise GooglePlacesError(
                f"Google Places call failed after retries (status={last_response.status_code}, body={last_response.text[:200]})"
            )
        raise GooglePlacesError("Google Places call failed without response")

    def _sanitize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        sanitized = dict(params)
        api_key = sanitized.get("key")
        if isinstance(api_key, str):
            sanitized["key"] = self._mask_api_key(api_key)
        return sanitized

    def _mask_api_key(self, value: str) -> str:
        if len(value) <= 8:
            return "***"
        return f"{value[:4]}...{value[-4:]}"

    def _log_debug_attempt(
        self,
        operation: str,
        url: str,
        params: Dict[str, Any],
        status_code: int,
        duration_ms: float,
        attempt: int,
        response_preview: str,
    ) -> None:
        if not _LOGGER.isEnabledFor(logging.DEBUG):
            return
        _LOGGER.debug(
            "Google Places %s call status=%s duration=%.1fms attempt=%s url=%s params=%s response_preview=%s",
            operation,
            status_code,
            duration_ms,
            attempt,
            url,
            params,
            response_preview,
        )

    def _record_external_call(
        self,
        *,
        operation: str,
        url: str,
        params: Dict[str, Any],
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
                "service": "google_places",
                "operation": operation,
                "url": url,
                "attempt": attempt,
                "attempt_max": _MAX_RETRIES,
                "outcome": outcome,
            },
            http={"method": "GET", "status_code": status_code},
            duration_ms=round(duration_ms, 2),
            response={"bytes": response_size, "preview": response_preview},
            params=params,
        )
