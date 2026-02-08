"""LinkedIn profile lookup service for directors."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.apify_client import ApifyClient, LinkedInSearchInput
from app.config import get_settings
from app.db import models
from app.observability import log_event
from app.utils.dates import utcnow

_LOGGER = logging.getLogger(__name__)

# Statuses for LinkedIn check
LINKEDIN_STATUS_PENDING = "pending"
LINKEDIN_STATUS_FOUND = "found"
LINKEDIN_STATUS_NOT_FOUND = "not_found"
LINKEDIN_STATUS_ERROR = "error"
LINKEDIN_STATUS_INSUFFICIENT = "insufficient"


@dataclass
class LinkedInEnrichmentResult:
    """Result of LinkedIn enrichment for a batch of directors."""

    total_directors: int = 0
    eligible_directors: int = 0
    searched_count: int = 0
    found_count: int = 0
    not_found_count: int = 0
    error_count: int = 0
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
        if (
            search_result.success
            and not search_result.profile_url
            and establishment
            and establishment.legal_unit_name
            and establishment.legal_unit_name.lower() not in company_name.lower()
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
            if candidate and candidate.strip():
                return candidate.strip()

        return None

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
    ) -> LinkedInEnrichmentResult:
        """Enrich LinkedIn profiles for directors of multiple establishments.

        Args:
            establishments: Establishments whose directors to enrich.
            run_id: Optional sync run ID for logging.
            force_refresh: If True, re-search even if already checked.

        Returns:
            Aggregated LinkedInEnrichmentResult.
        """
        total_result = LinkedInEnrichmentResult()

        for establishment in establishments:
            result = self.enrich_establishment_directors(
                establishment,
                run_id=run_id,
                force_refresh=force_refresh,
            )
            total_result.total_directors += result.total_directors
            total_result.eligible_directors += result.eligible_directors
            total_result.searched_count += result.searched_count
            total_result.found_count += result.found_count
            total_result.not_found_count += result.not_found_count
            total_result.error_count += result.error_count
            total_result.api_call_count += result.api_call_count
            total_result.directors_with_profiles.extend(result.directors_with_profiles)

        return total_result


__all__ = [
    "LINKEDIN_STATUS_ERROR",
    "LINKEDIN_STATUS_FOUND",
    "LINKEDIN_STATUS_INSUFFICIENT",
    "LINKEDIN_STATUS_NOT_FOUND",
    "LINKEDIN_STATUS_PENDING",
    "LinkedInEnrichmentResult",
    "LinkedInLookupService",
]
