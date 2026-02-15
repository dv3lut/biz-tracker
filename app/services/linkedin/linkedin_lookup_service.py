"""LinkedIn profile lookup service for directors."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.apify_client import ApifyClient, LinkedInSearchInput
from app.config import get_settings
from app.db import models
from app.observability import log_event
from app.utils.dates import utcnow
from app.utils.diffusible import any_name_non_diffusible

_LOGGER = logging.getLogger(__name__)

# Statuses for LinkedIn check
LINKEDIN_STATUS_PENDING = "pending"
LINKEDIN_STATUS_FOUND = "found"
LINKEDIN_STATUS_NOT_FOUND = "not_found"
LINKEDIN_STATUS_ERROR = "error"
LINKEDIN_STATUS_INSUFFICIENT = "insufficient"
LINKEDIN_STATUS_SKIPPED_ND = "skipped_nd"

# Maximum number of concurrent LinkedIn runs
MAX_CONCURRENT_LINKEDIN_RUNS = 30

# Progress callback type: (total, searched, found, not_found, error)
ProgressCallback = Callable[[int, int, int, int, int], None]


@dataclass
class LinkedInEnrichmentResult:
    """Result of LinkedIn enrichment for a batch of directors."""

    total_directors: int = 0
    eligible_directors: int = 0
    searched_count: int = 0
    found_count: int = 0
    not_found_count: int = 0
    error_count: int = 0
    skipped_nd_count: int = 0
    api_call_count: int = 0
    directors_with_profiles: list[models.Director] = field(default_factory=list)


class LinkedInLookupService:
    """Service for looking up LinkedIn profiles for directors."""

    def __init__(self, session: Session) -> None:
        self._session = session
        settings = get_settings()
        self._settings = getattr(settings, "apify", None)
        self._client: ApifyClient | None = None
        if self._settings and self._settings.enabled:
            self._client = ApifyClient()
        self._api_call_count = 0

    @property
    def enabled(self) -> bool:
        """Return True if LinkedIn lookups are enabled."""
        return self._settings is not None and self._settings.enabled

    def close(self) -> None:
        """Close resources."""
        if self._client:
            self._client.close()

    def enrich_establishment_directors(
        self,
        establishment: models.Establishment,
        *,
        run_id: UUID | None = None,
        force_refresh: bool = False,
    ) -> LinkedInEnrichmentResult:
        """Enrich directors of a single establishment with LinkedIn profiles.

        Args:
            establishment: The establishment whose directors to enrich.
            run_id: Optional sync run ID for logging.
            force_refresh: If True, re-search even if already checked.

        Returns:
            LinkedInEnrichmentResult with statistics.
        """
        return self.enrich_directors(
            establishment.directors,
            establishment=establishment,
            run_id=run_id,
            force_refresh=force_refresh,
        )

    def enrich_directors(
        self,
        directors: Sequence[models.Director],
        *,
        establishment: models.Establishment | None = None,
        run_id: UUID | None = None,
        force_refresh: bool = False,
    ) -> LinkedInEnrichmentResult:
        """Enrich a list of directors with LinkedIn profiles.

        Args:
            directors: Directors to enrich.
            establishment: Optional parent establishment (for logging and company name).
            run_id: Optional sync run ID for logging.
            force_refresh: If True, re-search even if already checked.

        Returns:
            LinkedInEnrichmentResult with statistics.
        """
        result = LinkedInEnrichmentResult(total_directors=len(directors))

        if not self._client:
            _LOGGER.debug("LinkedIn enrichment disabled (no Apify token)")
            return result

        # Filter to physical persons only
        physical_directors = [d for d in directors if d.is_physical_person]
        result.eligible_directors = len(physical_directors)

        if not physical_directors:
            log_event(
                "sync.linkedin.enrichment.skipped",
                run_id=str(run_id) if run_id else None,
                establishment_siret=establishment.siret if establishment else None,
                reason="no_physical_directors",
                total_directors=len(directors),
            )
            return result

        # Filter to those needing search
        to_search = [
            d for d in physical_directors
            if force_refresh or d.linkedin_check_status == LINKEDIN_STATUS_PENDING
        ]

        if not to_search:
            log_event(
                "sync.linkedin.enrichment.skipped",
                run_id=str(run_id) if run_id else None,
                establishment_siret=establishment.siret if establishment else None,
                reason="all_already_checked",
                eligible_directors=len(physical_directors),
            )
            return result

        log_event(
            "sync.linkedin.enrichment.started",
            run_id=str(run_id) if run_id else None,
            establishment_siret=establishment.siret if establishment else None,
            directors_to_search=len(to_search),
            force_refresh=force_refresh,
        )

        now = utcnow()

        for director in to_search:
            self._search_and_update_director(
                director,
                establishment=establishment,
                run_id=run_id,
                now=now,
                result=result,
            )

        self._session.flush()

        log_event(
            "sync.linkedin.enrichment.completed",
            run_id=str(run_id) if run_id else None,
            establishment_siret=establishment.siret if establishment else None,
            searched_count=result.searched_count,
            found_count=result.found_count,
            not_found_count=result.not_found_count,
            error_count=result.error_count,
            api_call_count=result.api_call_count,
        )

        return result

    def _search_and_update_director(
        self,
        director: models.Director,
        *,
        establishment: models.Establishment | None,
        run_id: UUID | None,
        now: datetime,
        result: LinkedInEnrichmentResult,
    ) -> None:
        """Search LinkedIn for a single director and update the record."""
        first_name = director.first_name_for_search
        last_name = director.last_name

        # Skip non-diffusible names (contains [ND] or NON DIFFUSIBLE)
        if any_name_non_diffusible(first_name, last_name, director.first_names):
            director.linkedin_check_status = LINKEDIN_STATUS_INSUFFICIENT
            director.linkedin_last_checked_at = now
            result.skipped_nd_count += 1
            log_event(
                "sync.linkedin.director.skipped",
                run_id=str(run_id) if run_id else None,
                director_id=str(director.id),
                establishment_siret=establishment.siret if establishment else None,
                reason="non_diffusible",
                first_name=first_name,
                last_name=last_name,
            )
            return

        if not first_name or not last_name:
            director.linkedin_check_status = LINKEDIN_STATUS_INSUFFICIENT
            director.linkedin_last_checked_at = now
            log_event(
                "sync.linkedin.director.skipped",
                run_id=str(run_id) if run_id else None,
                director_id=str(director.id),
                establishment_siret=establishment.siret if establishment else None,
                reason="missing_name",
                first_name=first_name,
                last_name=last_name,
            )
            return

        # Determine company name (establishment name first, then legal unit name)
        # Note: _resolve_company_name already filters out non-diffusible names
        company_name = self._resolve_company_name(director, establishment)
        if not company_name:
            director.linkedin_check_status = LINKEDIN_STATUS_INSUFFICIENT
            director.linkedin_last_checked_at = now
            log_event(
                "sync.linkedin.director.skipped",
                run_id=str(run_id) if run_id else None,
                director_id=str(director.id),
                establishment_siret=establishment.siret if establishment else None,
                reason="missing_company",
            )
            return

        # First attempt with establishment name
        search_input = LinkedInSearchInput(
            first_name=first_name,
            last_name=last_name,
            company=company_name,
        )

        log_event(
            "sync.linkedin.director.search.started",
            run_id=str(run_id) if run_id else None,
            director_id=str(director.id),
            establishment_siret=establishment.siret if establishment else None,
            search_input={
                "first_name": first_name,
                "last_name": last_name,
                "company": company_name,
            },
        )

        assert self._client is not None
        search_result = self._client.search_linkedin_profile(search_input)
        result.api_call_count += 1
        result.searched_count += 1

        # If not found and legal unit name is different, retry with legal unit name
        # BUT only if establishment name is NOT contained in legal unit name
        # (e.g., don't retry "LES CO'PAINS" with "BOULANGERIE DES CO'PAINS DE MALAK (LES CO'PAINS)")
        if (
            search_result.success
            and not search_result.profile_url
            and establishment
            and establishment.legal_unit_name
            and self._should_retry_with_legal_unit(company_name, establishment.legal_unit_name)
        ):
            legal_company = establishment.legal_unit_name
            log_event(
                "sync.linkedin.director.search.retry",
                run_id=str(run_id) if run_id else None,
                director_id=str(director.id),
                establishment_siret=establishment.siret,
                original_company=company_name,
                retry_company=legal_company,
                reason="not_found_with_establishment_name",
            )
            retry_input = LinkedInSearchInput(
                first_name=first_name,
                last_name=last_name,
                company=legal_company,
            )
            search_result = self._client.search_linkedin_profile(retry_input)
            result.api_call_count += 1

        # Update director record
        director.linkedin_last_checked_at = now

        if not search_result.success:
            director.linkedin_check_status = LINKEDIN_STATUS_ERROR
            director.linkedin_profile_url = None
            director.linkedin_profile_data = {
                "error": search_result.error,
                "message": search_result.error or "Erreur lors de la recherche",
            }
            result.error_count += 1
            log_event(
                "sync.linkedin.director.search.error",
                run_id=str(run_id) if run_id else None,
                director_id=str(director.id),
                establishment_siret=establishment.siret if establishment else None,
                error=search_result.error,
            )
            return

        if search_result.profile_url:
            director.linkedin_check_status = LINKEDIN_STATUS_FOUND
            director.linkedin_profile_url = search_result.profile_url
            director.linkedin_profile_data = search_result.profile_data
            result.found_count += 1
            result.directors_with_profiles.append(director)
            log_event(
                "sync.linkedin.director.search.found",
                run_id=str(run_id) if run_id else None,
                director_id=str(director.id),
                establishment_siret=establishment.siret if establishment else None,
                profile_url=search_result.profile_url,
                profile_data=search_result.profile_data,
            )
        else:
            director.linkedin_check_status = LINKEDIN_STATUS_NOT_FOUND
            result.not_found_count += 1
            log_event(
                "sync.linkedin.director.search.not_found",
                run_id=str(run_id) if run_id else None,
                director_id=str(director.id),
                establishment_siret=establishment.siret if establishment else None,
            )

    def _resolve_company_name(
        self,
        director: models.Director,
        establishment: models.Establishment | None,
    ) -> str | None:
        """Resolve the company name to use for LinkedIn search.

        Priority:
        1. Establishment name (name field)
        2. Enseigne
        3. Denomination usuelle
        4. Legal unit name

        Non-diffusible names ([ND], NON DIFFUSIBLE) are skipped.
        """
        if not establishment:
            return None

        candidates = [
            establishment.name,
            establishment.enseigne1,
            establishment.denomination_usuelle_etablissement,
            establishment.legal_unit_name,
            establishment.denomination_unite_legale,
        ]

        for candidate in candidates:
            if candidate and candidate.strip() and not any_name_non_diffusible(candidate):
                return candidate.strip()

        return None

    def _should_retry_with_legal_unit(
        self,
        establishment_name: str,
        legal_unit_name: str,
    ) -> bool:
        """Determine if we should retry LinkedIn search with legal unit name.

        Returns False if:
        - Names are the same (case-insensitive)
        - Establishment name is contained within legal unit name
        - Legal unit name is contained within establishment name
        - Either name is non-diffusible

        This prevents useless retries like:
        - "LES CO'PAINS" -> "BOULANGERIE DES CO'PAINS DE MALAK (LES CO'PAINS)"
        """
        if any_name_non_diffusible(legal_unit_name):
            return False

        est_lower = establishment_name.lower().strip()
        legal_lower = legal_unit_name.lower().strip()

        # Same name
        if est_lower == legal_lower:
            return False

        # Establishment name is contained in legal unit name
        if est_lower in legal_lower:
            return False

        # Legal unit name is contained in establishment name
        if legal_lower in est_lower:
            return False

        return True

    def _search_director_parallel(
        self,
        director: models.Director,
        establishment: models.Establishment,
        run_id: UUID | None,
        now: datetime,
    ) -> dict:
        """Execute LinkedIn search for a director (thread-safe, HTTP only).

        This method is designed to be called from a ThreadPoolExecutor.
        It only makes HTTP calls and returns a dict with results.
        DB updates are done in the main thread via _apply_search_result.

        Returns:
            Dict with keys: status, profile_url, profile_data, api_calls, reason
        """
        first_name = director.first_name_for_search
        last_name = director.last_name

        # Skip non-diffusible names
        if any_name_non_diffusible(first_name, last_name, director.first_names):
            return {
                "status": LINKEDIN_STATUS_INSUFFICIENT,
                "reason": "non_diffusible",
                "api_calls": 0,
            }

        if not first_name or not last_name:
            return {
                "status": LINKEDIN_STATUS_INSUFFICIENT,
                "reason": "missing_name",
                "api_calls": 0,
            }

        # Determine company name
        company_name = self._resolve_company_name(director, establishment)
        if not company_name:
            return {
                "status": LINKEDIN_STATUS_INSUFFICIENT,
                "reason": "missing_company",
                "api_calls": 0,
            }

        # Skip non-diffusible company names
        if any_name_non_diffusible(company_name):
            return {
                "status": LINKEDIN_STATUS_INSUFFICIENT,
                "reason": "non_diffusible_company",
                "api_calls": 0,
            }

        # Perform search
        search_input = LinkedInSearchInput(
            first_name=first_name,
            last_name=last_name,
            company=company_name,
        )

        assert self._client is not None
        search_result = self._client.search_linkedin_profile(search_input)
        api_calls = 1

        # Retry with legal unit name if appropriate
        if (
            search_result.success
            and not search_result.profile_url
            and establishment.legal_unit_name
            and self._should_retry_with_legal_unit(company_name, establishment.legal_unit_name)
        ):
            retry_input = LinkedInSearchInput(
                first_name=first_name,
                last_name=last_name,
                company=establishment.legal_unit_name,
            )
            search_result = self._client.search_linkedin_profile(retry_input)
            api_calls += 1

        if not search_result.success:
            return {
                "status": LINKEDIN_STATUS_ERROR,
                "error": search_result.error,
                "api_calls": api_calls,
            }

        if search_result.profile_url:
            return {
                "status": LINKEDIN_STATUS_FOUND,
                "profile_url": search_result.profile_url,
                "profile_data": search_result.profile_data,
                "api_calls": api_calls,
            }

        return {
            "status": LINKEDIN_STATUS_NOT_FOUND,
            "api_calls": api_calls,
        }

    def _apply_search_result(
        self,
        director: models.Director,
        establishment: models.Establishment,
        outcome: dict,
        run_id: UUID | None,
        now: datetime,
        result: LinkedInEnrichmentResult,
    ) -> None:
        """Apply search result to director and update aggregated result.

        Must be called from the main thread (handles DB updates).
        """
        status = outcome.get("status")
        api_calls = outcome.get("api_calls", 0)

        director.linkedin_last_checked_at = now
        director.linkedin_check_status = status
        result.api_call_count += api_calls

        if status == LINKEDIN_STATUS_SKIPPED_ND:
            result.skipped_nd_count += 1
            log_event(
                "sync.linkedin.director.skipped",
                run_id=str(run_id) if run_id else None,
                director_id=str(director.id),
                establishment_siret=establishment.siret,
                reason=outcome.get("reason", "non_diffusible"),
            )
        elif status == LINKEDIN_STATUS_INSUFFICIENT:
            reason = outcome.get("reason", "insufficient")
            if reason in {"non_diffusible", "non_diffusible_company"}:
                result.skipped_nd_count += 1
            log_event(
                "sync.linkedin.director.skipped",
                run_id=str(run_id) if run_id else None,
                director_id=str(director.id),
                establishment_siret=establishment.siret,
                reason=reason,
            )
        elif status == LINKEDIN_STATUS_ERROR:
            result.error_count += 1
            result.searched_count += 1
            log_event(
                "sync.linkedin.director.search.error",
                run_id=str(run_id) if run_id else None,
                director_id=str(director.id),
                establishment_siret=establishment.siret,
                error=outcome.get("error"),
            )
        elif status == LINKEDIN_STATUS_FOUND:
            result.found_count += 1
            result.searched_count += 1
            director.linkedin_profile_url = outcome.get("profile_url")
            director.linkedin_profile_data = outcome.get("profile_data")
            result.directors_with_profiles.append(director)
            log_event(
                "sync.linkedin.director.search.found",
                run_id=str(run_id) if run_id else None,
                director_id=str(director.id),
                establishment_siret=establishment.siret,
                profile_url=outcome.get("profile_url"),
            )
        elif status == LINKEDIN_STATUS_NOT_FOUND:
            result.not_found_count += 1
            result.searched_count += 1
            log_event(
                "sync.linkedin.director.search.not_found",
                run_id=str(run_id) if run_id else None,
                director_id=str(director.id),
                establishment_siret=establishment.siret,
            )

    def lookup_single_director(
        self,
        director: models.Director,
        *,
        force_refresh: bool = True,
    ) -> LinkedInEnrichmentResult:
        """Lookup LinkedIn profile for a single director (for debug/manual trigger).

        Args:
            director: The director to look up.
            force_refresh: If True, re-search even if already checked.

        Returns:
            LinkedInEnrichmentResult with the lookup result.
        """
        establishment = director.establishment
        return self.enrich_directors(
            [director],
            establishment=establishment,
            force_refresh=force_refresh,
        )

    def fetch_pending_directors(
        self,
        *,
        naf_codes: list[str] | None = None,
        limit: int = 1000,
    ) -> list[models.Director]:
        """Fetch directors pending LinkedIn enrichment.

        Args:
            naf_codes: Optional filter by establishment NAF codes.
            limit: Maximum number of directors to return.

        Returns:
            List of Director objects needing LinkedIn lookup.
        """
        stmt = (
            select(models.Director)
            .join(models.Establishment)
            .where(models.Director.type_dirigeant == "personne physique")
            .where(models.Director.linkedin_check_status == LINKEDIN_STATUS_PENDING)
        )

        if naf_codes:
            stmt = stmt.where(models.Establishment.naf_code.in_(naf_codes))

        stmt = stmt.limit(limit)

        return list(self._session.execute(stmt).scalars().all())

    def enrich_batch(
        self,
        establishments: Sequence[models.Establishment],
        *,
        run_id: UUID | None = None,
        force_refresh: bool = False,
        progress_callback: ProgressCallback | None = None,
    ) -> LinkedInEnrichmentResult:
        """Enrich LinkedIn profiles for directors of multiple establishments.

        Uses parallel execution with up to MAX_CONCURRENT_LINKEDIN_RUNS concurrent API calls.

        Args:
            establishments: Establishments whose directors to enrich.
            run_id: Optional sync run ID for logging.
            force_refresh: If True, re-search even if already checked.
            progress_callback: Optional callback for progress updates.

        Returns:
            Aggregated LinkedInEnrichmentResult.
        """
        total_result = LinkedInEnrichmentResult()

        if not self._client:
            _LOGGER.debug("LinkedIn enrichment disabled (no Apify token)")
            return total_result

        # Collect all directors to search across all establishments
        directors_to_search: list[tuple[models.Director, models.Establishment]] = []
        for establishment in establishments:
            physical_directors = [d for d in establishment.directors if d.is_physical_person]
            total_result.total_directors += len(establishment.directors)
            total_result.eligible_directors += len(physical_directors)

            for director in physical_directors:
                if force_refresh or director.linkedin_check_status == LINKEDIN_STATUS_PENDING:
                    directors_to_search.append((director, establishment))

        if not directors_to_search:
            log_event(
                "sync.linkedin.batch.skipped",
                run_id=str(run_id) if run_id else None,
                reason="no_directors_to_search",
                total_establishments=len(establishments),
                total_directors=total_result.total_directors,
            )
            return total_result

        log_event(
            "sync.linkedin.batch.started",
            run_id=str(run_id) if run_id else None,
            total_establishments=len(establishments),
            directors_to_search=len(directors_to_search),
            max_concurrent=MAX_CONCURRENT_LINKEDIN_RUNS,
        )

        # Initial progress callback
        if progress_callback:
            progress_callback(
                len(directors_to_search),
                total_result.searched_count,
                total_result.found_count,
                total_result.not_found_count,
                total_result.error_count,
            )

        now = utcnow()

        # Execute searches in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_LINKEDIN_RUNS) as executor:
            futures = {}
            for director, establishment in directors_to_search:
                future = executor.submit(
                    self._search_director_parallel,
                    director,
                    establishment,
                    run_id,
                    now,
                )
                futures[future] = (director, establishment)

            # Process results as they complete
            for future in as_completed(futures):
                director, establishment = futures[future]
                try:
                    search_outcome = future.result()
                    self._apply_search_result(
                        director,
                        establishment,
                        search_outcome,
                        run_id,
                        now,
                        total_result,
                    )
                except Exception as exc:
                    _LOGGER.exception(
                        "LinkedIn search failed for director %s: %s",
                        director.id,
                        exc,
                    )
                    director.linkedin_check_status = LINKEDIN_STATUS_ERROR
                    director.linkedin_last_checked_at = now
                    total_result.error_count += 1
                    log_event(
                        "sync.linkedin.director.search.error",
                        run_id=str(run_id) if run_id else None,
                        director_id=str(director.id),
                        establishment_siret=establishment.siret,
                        error=str(exc),
                    )

                # Update progress callback
                if progress_callback:
                    progress_callback(
                        len(directors_to_search),
                        total_result.searched_count,
                        total_result.found_count,
                        total_result.not_found_count,
                        total_result.error_count,
                    )

        self._session.flush()

        log_event(
            "sync.linkedin.batch.completed",
            run_id=str(run_id) if run_id else None,
            total_establishments=len(establishments),
            directors_searched=len(directors_to_search),
            searched_count=total_result.searched_count,
            found_count=total_result.found_count,
            not_found_count=total_result.not_found_count,
            error_count=total_result.error_count,
            skipped_nd_count=total_result.skipped_nd_count,
            api_call_count=total_result.api_call_count,
        )

        return total_result


__all__ = [
    "LINKEDIN_STATUS_ERROR",
    "LINKEDIN_STATUS_FOUND",
    "LINKEDIN_STATUS_INSUFFICIENT",
    "LINKEDIN_STATUS_NOT_FOUND",
    "LINKEDIN_STATUS_PENDING",
    "LINKEDIN_STATUS_SKIPPED_ND",
    "LinkedInEnrichmentResult",
    "LinkedInLookupService",
    "MAX_CONCURRENT_LINKEDIN_RUNS",
    "ProgressCallback",
]
