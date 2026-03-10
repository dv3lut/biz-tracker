"""Apify client for LinkedIn profile lookups."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import requests

from app.config import ApifySettings, get_settings

_LOGGER = logging.getLogger(__name__)

APIFY_BASE_URL = "https://api.apify.com/v2"


@dataclass
class LinkedInSearchInput:
    """Input parameters for LinkedIn profile search."""

    first_name: str
    last_name: str
    company: str


@dataclass
class LinkedInProfileResult:
    """Result of a LinkedIn profile search."""

    success: bool
    profile_url: str | None = None
    profile_data: dict[str, Any] | None = None
    error: str | None = None


class ApifyClientError(Exception):
    """Base exception for Apify client errors."""


class ApifyClient:
    """Client for interacting with Apify actors."""

    def __init__(self, settings: ApifySettings | Any | None = None) -> None:
        if settings is not None:
            self._settings = settings
        else:
            try:
                self._settings = get_settings().apify
            except Exception as exc:  # pragma: no cover - defensive fallback
                _LOGGER.debug("Falling back to disabled Apify settings: %s", exc)
                self._settings = ApifySettings()
        self._session = requests.Session()
        if self._settings.api_token:
            self._session.headers["Authorization"] = f"Bearer {self._settings.api_token}"

    @property
    def enabled(self) -> bool:
        """Return True if the Apify integration is configured."""
        return self._settings.enabled

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self._session.close()

    def search_linkedin_profile(self, search_input: LinkedInSearchInput) -> LinkedInProfileResult:
        """Run the LinkedIn finder actor and return the result.

        Args:
            search_input: The search parameters (first name, last name, company).

        Returns:
            LinkedInProfileResult with the profile URL and data if found.
        """
        if not self.enabled: 
            return LinkedInProfileResult(
                success=False,
                error="Apify integration not configured (missing API token)",
            )

        actor_id = self._settings.linkedin_actor_id
        run_url = f"{APIFY_BASE_URL}/acts/{actor_id}/runs"

        run_input = {
            "firstName": search_input.first_name,
            "lastName": search_input.last_name,
            "company": search_input.company,
        }

        try:
            # Start the actor run and wait for it to finish
            response = self._session.post(
                run_url,
                json=run_input,
                params={"waitForFinish": self._settings.request_timeout_seconds},
                timeout=self._settings.request_timeout_seconds + 10,
            )
            response.raise_for_status()
            run_data = response.json()

            run_status = run_data.get("data", {}).get("status")
            if run_status not in ("SUCCEEDED", "FINISHED"):
                status_message = run_data.get("data", {}).get("statusMessage")
                error_message = run_data.get("data", {}).get("errorMessage")
                details = status_message or error_message
                _LOGGER.warning(
                    "Apify run did not succeed: status=%s, input=%s",
                    run_status,
                    run_input,
                )
                return LinkedInProfileResult(
                    success=False,
                    error=f"Apify run status: {run_status}{f' ({details})' if details else ''}",
                )

            # Fetch results from the default dataset
            dataset_id = run_data.get("data", {}).get("defaultDatasetId")
            if not dataset_id:
                return LinkedInProfileResult(
                    success=False,
                    error="No dataset ID in Apify response",
                )

            dataset_url = f"{APIFY_BASE_URL}/datasets/{dataset_id}/items"
            dataset_response = self._session.get(
                dataset_url,
                timeout=self._settings.request_timeout_seconds,
            )
            dataset_response.raise_for_status()
            items = dataset_response.json()

            if not items:
                _LOGGER.debug("No LinkedIn profile found for %s", run_input)
                return LinkedInProfileResult(
                    success=True,
                    profile_url=None,
                    profile_data=None,
                )

            # Take the first result
            item = items[0]
            profile_url = item.get("linkedinProfileUrl")
            profile_data = item.get("profileData")

            return LinkedInProfileResult(
                success=True,
                profile_url=profile_url,
                profile_data=profile_data,
            )

        except requests.Timeout as exc:
            _LOGGER.warning("Apify request timed out for %s: %s", run_input, exc)
            return LinkedInProfileResult(
                success=False,
                error=f"Request timeout: {exc}",
            )
        except requests.RequestException as exc:
            error_detail = None
            if getattr(exc, "response", None) is not None:
                try:
                    payload = exc.response.json()
                    if isinstance(payload, dict):
                        error_detail = payload.get("message") or payload.get("error")
                        if not error_detail:
                            data_payload = payload.get("data")
                            if isinstance(data_payload, dict):
                                error_detail = data_payload.get("message")
                except ValueError:
                    error_detail = exc.response.text if exc.response is not None else None
            _LOGGER.warning("Apify request failed for %s: %s", run_input, exc)
            return LinkedInProfileResult(
                success=False,
                error=error_detail or str(exc),
            )
        except Exception as exc:
            _LOGGER.exception("Unexpected error during Apify call for %s", run_input)
            return LinkedInProfileResult(
                success=False,
                error=f"Unexpected error: {exc}",
            )

    def search_linkedin_profiles_batch(
        self,
        search_inputs: list[LinkedInSearchInput],
    ) -> list[LinkedInProfileResult]:
        """Search for multiple LinkedIn profiles.

        Note: Apify runs are executed sequentially to respect rate limits.
        The max_concurrent_runs setting can be used in the future for parallel execution.

        Args:
            search_inputs: List of search parameters.

        Returns:
            List of results in the same order as inputs.
        """
        results: list[LinkedInProfileResult] = []
        for search_input in search_inputs:
            result = self.search_linkedin_profile(search_input)
            results.append(result)
        return results


__all__ = [
    "ApifyClient",
    "ApifyClientError",
    "LinkedInProfileResult",
    "LinkedInSearchInput",
]
