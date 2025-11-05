"""Client utilitaire pour les appels Google Places."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests
from requests import Response, Session

from app.config import get_settings

_LOGGER = logging.getLogger(__name__)

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_TIMEOUT_SECONDS = 10


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
        payload = self._request(self._find_place_url, params=params)
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
        payload = self._request(self._place_details_url, params=params)
        result = payload.get("result")
        if not isinstance(result, dict):
            return None
        return result

    def _request(self, url: str, *, params: Dict[str, Any]) -> Dict[str, Any]:
        last_response: Optional[Response] = None
        for attempt in range(1, _MAX_RETRIES + 1):
            response = self._session.get(url, params=params, timeout=_TIMEOUT_SECONDS)
            last_response = response
            if response.status_code < 300:
                try:
                    return response.json()
                except ValueError as exc:  # pragma: no cover - defensive fallback
                    raise GooglePlacesError("Réponse Google Places invalide") from exc

            if response.status_code not in _RETRYABLE_STATUS:
                raise GooglePlacesError(
                    f"Google Places call failed (status={response.status_code}, body={response.text[:200]})"
                )
            _LOGGER.warning(
                "Appel Google Places échoué (status=%s, tentative %s/%s).", response.status_code, attempt, _MAX_RETRIES
            )
        if last_response is not None:
            raise GooglePlacesError(
                f"Google Places call failed after retries (status={last_response.status_code}, body={last_response.text[:200]})"
            )
        raise GooglePlacesError("Google Places call failed without response")
