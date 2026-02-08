"""Client for the Recherche Entreprises API (dirigeants & legal unit name)."""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import requests
from requests import Session

from app.config import get_settings
from app.observability import log_event
from app.services.rate_limiter import RateLimiter

_LOGGER = logging.getLogger(__name__)

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_RESPONSE_PREVIEW_LIMIT = 400


@dataclass
class DirectorInfo:
    """Parsed director information from the annuaire API."""

    first_names: str | None
    last_name: str | None
    birth_month: int | None
    birth_year: int | None
    quality: str | None = None
    type_dirigeant: str = "personne physique"
    siren: str | None = None
    denomination: str | None = None
    nationality: str | None = None


@dataclass
class AnnuaireResult:
    """Enrichment data fetched for one SIREN."""

    siren: str
    legal_unit_name: str | None
    directors: list[DirectorInfo]
    success: bool
    error: str | None = None


def _parse_birth_date(date_str: str | None) -> tuple[int | None, int | None]:
    """Extract (month, year) from a date string like '1975-10' or '1975'."""
    if not date_str:
        return None, None
    parts = date_str.split("-")
    year: int | None = None
    month: int | None = None
    try:
        year = int(parts[0])
    except (ValueError, IndexError):
        pass
    if len(parts) >= 2:
        try:
            month = int(parts[1])
        except (ValueError, IndexError):
            pass
    return month, year


def _extract_directors(dirigeants: list[dict[str, Any]]) -> list[DirectorInfo]:
    """Extract all directors from the dirigeants list."""
    result: list[DirectorInfo] = []
    for d in dirigeants:
        type_dir = d.get("type_dirigeant", "")
        quality = d.get("qualite")
        nationality = d.get("nationalite")
        if type_dir == "personne physique":
            nom = d.get("nom")
            prenoms = d.get("prenoms")
            birth_month, birth_year = _parse_birth_date(d.get("date_de_naissance"))
            result.append(DirectorInfo(
                first_names=prenoms.strip() if prenoms else None,
                last_name=nom.strip() if nom else None,
                birth_month=birth_month,
                birth_year=birth_year,
                quality=quality.strip() if quality else None,
                type_dirigeant="personne physique",
                nationality=nationality.strip() if nationality else None,
            ))
        elif type_dir == "personne morale":
            result.append(DirectorInfo(
                first_names=None,
                last_name=None,
                birth_month=None,
                birth_year=None,
                quality=quality.strip() if quality else None,
                type_dirigeant="personne morale",
                siren=d.get("siren"),
                denomination=(d.get("denomination") or "").strip() or None,
                nationality=nationality.strip() if nationality else None,
            ))
    return result


class AnnuaireEntreprisesClient:
    """HTTP client for the Recherche Entreprises API with retry logic."""

    def __init__(self) -> None:
        settings = get_settings().annuaire
        self._base_url = settings.api_base_url.rstrip("/")
        self._timeout = settings.request_timeout_seconds
        self._max_retries = settings.max_retries
        self._backoff_factor = settings.backoff_factor
        self._max_workers = settings.max_workers
        self._max_calls_per_second = settings.max_calls_per_second
        self._enabled = settings.enabled
        self._rate_limiter = RateLimiter(max_calls_per_minute=self._max_calls_per_second * 60)
        self._session: Session = requests.Session()
        self._session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "biz-tracker-back/1.0",
            }
        )

    def close(self) -> None:
        self._session.close()

    @property
    def enabled(self) -> bool:
        return self._enabled

    def fetch_siren(self, siren: str, *, run_id: str | None = None) -> AnnuaireResult:
        """Fetch legal unit name and director info for a single SIREN."""
        url = f"{self._base_url}/search"
        params = {"q": siren, "page": 1, "per_page": 1}
        backoff = self._backoff_factor

        for attempt in range(1, self._max_retries + 1):
            start = time.perf_counter()
            try:
                self._rate_limiter.acquire()
                response = self._session.get(url, params=params, timeout=self._timeout)
            except requests.RequestException as exc:
                duration_ms = (time.perf_counter() - start) * 1000
                self._record_call(
                    siren=siren,
                    status_code=0,
                    duration_ms=duration_ms,
                    attempt=attempt,
                    outcome="error",
                    run_id=run_id,
                    error=str(exc),
                )
                if attempt < self._max_retries:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                return AnnuaireResult(
                    siren=siren, legal_unit_name=None, directors=[],
                    success=False, error=str(exc),
                )

            duration_ms = (time.perf_counter() - start) * 1000
            status = response.status_code

            if status < 300:
                self._record_call(
                    siren=siren,
                    status_code=status,
                    duration_ms=duration_ms,
                    attempt=attempt,
                    outcome="success",
                    run_id=run_id,
                )
                return self._parse_response(siren, response)

            if status in _RETRYABLE_STATUS and attempt < self._max_retries:
                self._record_call(
                    siren=siren,
                    status_code=status,
                    duration_ms=duration_ms,
                    attempt=attempt,
                    outcome="retry",
                    run_id=run_id,
                )
                retry_after = self._get_retry_after(response, backoff)
                time.sleep(retry_after)
                backoff *= 2
                continue

            self._record_call(
                siren=siren,
                status_code=status,
                duration_ms=duration_ms,
                attempt=attempt,
                outcome="failure",
                run_id=run_id,
            )
            return AnnuaireResult(
                siren=siren, legal_unit_name=None, directors=[],
                success=False, error=f"HTTP {status}",
            )

        return AnnuaireResult(
            siren=siren, legal_unit_name=None, directors=[],
            success=False, error="max retries exceeded",
        )

    def fetch_batch(
        self,
        sirens: Sequence[str],
        *,
        run_id: str | None = None,
    ) -> Dict[str, AnnuaireResult]:
        """Fetch annuaire data for multiple SIRENs in parallel.

        Returns a dict mapping each SIREN to its result.
        """
        if not sirens or not self._enabled:
            return {}

        unique_sirens = list(dict.fromkeys(sirens))
        results: Dict[str, AnnuaireResult] = {}
        workers = min(self._max_workers, len(unique_sirens))

        log_event(
            "annuaire.enrichment.started",
            run_id=run_id,
            total_sirens=len(unique_sirens),
            max_workers=workers,
        )

        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self.fetch_siren, siren, run_id=run_id): siren
                for siren in unique_sirens
            }
            for future in as_completed(futures):
                siren = futures[future]
                try:
                    result = future.result()
                    results[siren] = result
                except Exception as exc:
                    _LOGGER.warning("Annuaire fetch failed for SIREN %s: %s", siren, exc)
                    results[siren] = AnnuaireResult(
                        siren=siren, legal_unit_name=None, directors=[],
                        success=False, error=str(exc),
                    )

        duration = time.perf_counter() - start
        success_count = sum(1 for r in results.values() if r.success)
        fail_count = len(results) - success_count

        log_event(
            "annuaire.enrichment.completed",
            run_id=run_id,
            total_sirens=len(unique_sirens),
            success_count=success_count,
            failure_count=fail_count,
            duration_seconds=round(duration, 2),
            max_workers=workers,
        )

        return results

    def _parse_response(self, siren: str, response: requests.Response) -> AnnuaireResult:
        """Parse the API JSON response into an AnnuaireResult."""
        try:
            data = response.json()
        except ValueError:
            return AnnuaireResult(
                siren=siren, legal_unit_name=None, directors=[],
                success=False, error="invalid JSON",
            )

        results_list = data.get("results", [])
        if not results_list:
            return AnnuaireResult(
                siren=siren, legal_unit_name=None, directors=[],
                success=True, error=None,
            )

        entry = results_list[0]
        legal_unit_name = entry.get("nom_complet") or entry.get("nom_raison_sociale")
        dirigeants = entry.get("dirigeants", [])
        directors = _extract_directors(dirigeants)

        return AnnuaireResult(
            siren=siren,
            legal_unit_name=legal_unit_name.strip() if legal_unit_name else None,
            directors=directors,
            success=True,
        )

    def _get_retry_after(self, response: requests.Response, backoff: float) -> float:
        if "Retry-After" in response.headers:
            try:
                return float(response.headers["Retry-After"])
            except ValueError:
                pass
        return backoff

    def _record_call(
        self,
        *,
        siren: str,
        status_code: int,
        duration_ms: float,
        attempt: int,
        outcome: str,
        run_id: str | None = None,
        error: str | None = None,
    ) -> None:
        fields: Dict[str, Any] = {
            "external": {
                "service": "annuaire_entreprises",
                "endpoint": "/search",
                "siren": siren,
                "attempt": attempt,
                "attempt_max": self._max_retries,
                "outcome": outcome,
            },
            "http": {"method": "GET", "status_code": status_code},
            "duration_ms": round(duration_ms, 2),
        }
        if run_id:
            fields["run_id"] = run_id
        if error:
            fields["error"] = {"message": error}
        log_event("external.call", **fields)
