"""Google Places enrichment for establishments."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Callable, Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.google_places_client import GooglePlacesClient, GooglePlacesError
from app.config import get_settings
from app.db import models
from app.services.google_business import matches_expected_google_category
from app.services.google_business.constants import PROGRESS_BATCH_SIZE, TYPE_MISMATCH_STATUS
from app.services.google_business.keywords import build_naf_keyword_map
from app.services.google_business.lookup_engine import GoogleLookupEngine
from app.services.google_business.types import GoogleEnrichmentResult, GoogleMatch
from app.services.rate_limiter import RateLimiter
from app.services.google_retry_config import GoogleRetryRuntimeConfig, load_runtime_google_retry_config
from app.utils.business_types import is_micro_company
from app.utils.dates import utcnow

ProgressCallback = Callable[[int, int, int, int, int], None]


_LOGGER = logging.getLogger(__name__)

class GoogleBusinessService:
    """Lookup Google My Business pages for establishments lacking an association."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._settings = get_settings().google
        self._retry_config: GoogleRetryRuntimeConfig = load_runtime_google_retry_config(session)
        self._category_similarity_threshold = self._settings.category_similarity_threshold
        self._neutral_google_types = {"point_of_interest", "establishment", "store", "food"}
        self._naf_keyword_map = build_naf_keyword_map(self._session)
        self._lookup_engine: GoogleLookupEngine | None = None
        if not self._settings.enabled:
            self._client: GooglePlacesClient | None = None
            self._rate_limiter = None
        else:
            self._client = GooglePlacesClient()
            self._rate_limiter = RateLimiter(self._settings.max_calls_per_minute)
            self._lookup_engine = GoogleLookupEngine(
                self._session,
                self._client,
                self._rate_limiter,
                self._settings,
                naf_keyword_map=self._naf_keyword_map,
                neutral_google_types=self._neutral_google_types,
                category_similarity_threshold=self._category_similarity_threshold,
                api_call_hook=self._record_api_call,
                api_error_hook=self._record_api_error,
                category_matcher=self._matches_expected_google_category,
            )
        self._api_call_count = 0
        self._api_error_count = 0

    def _record_api_error(self, _operation: str) -> None:
        current = getattr(self, "_api_error_count", 0)
        self._api_error_count = current + 1

    def close(self) -> None:
        if self._client:
            self._client.close()

    def _get_lookup_engine(self) -> GoogleLookupEngine:
        engine = getattr(self, "_lookup_engine", None)
        if engine:
            return engine

        session = getattr(self, "_session", None)
        client = getattr(self, "_client", None)
        rate_limiter = getattr(self, "_rate_limiter", None)
        settings = getattr(self, "_settings", None)
        if not all([session, client, rate_limiter, settings]):
            raise RuntimeError("Google lookup engine is not initialised.")

        naf_keyword_map = getattr(self, "_naf_keyword_map", None) or {}
        neutral_types = getattr(self, "_neutral_google_types", {"point_of_interest", "establishment", "store", "food"})
        similarity_threshold = getattr(
            self,
            "_category_similarity_threshold",
            getattr(settings, "category_similarity_threshold", 0.72),
        )
        api_call_hook = getattr(self, "_record_api_call", lambda: None)
        api_error_hook = getattr(self, "_record_api_error", None)

        engine = GoogleLookupEngine(
            session,
            client,
            rate_limiter,
            settings,
            naf_keyword_map=naf_keyword_map,
            neutral_google_types=neutral_types,
            category_similarity_threshold=similarity_threshold,
            api_call_hook=api_call_hook,
            api_error_hook=api_error_hook,
            category_matcher=self._matches_expected_google_category,
        )
        self._lookup_engine = engine
        return engine

    def enrich(
        self,
        new_establishments: Sequence[models.Establishment],
        *,
        progress_callback: ProgressCallback | None = None,
        include_backlog: bool = True,
        reset_google_state: bool = False,
        recheck_all: bool = False,
    ) -> GoogleEnrichmentResult:
        if not self._client or not self._rate_limiter or not self._lookup_engine:
            return GoogleEnrichmentResult(
                matches=[],
                queue_count=0,
                eligible_count=0,
                matched_count=0,
                remaining_count=0,
                api_call_count=0,
                api_error_count=0,
            )

        now = utcnow()
        self._api_call_count = 0
        self._api_error_count = 0
        unique_new = {establishment.siret: establishment for establishment in new_establishments if establishment.siret}
        new_sirets = set(unique_new)
        candidates = list(
            self._filter_candidates(
                unique_new.values(),
                now=now,
                reset_google_state=reset_google_state,
                recheck_all=recheck_all,
            )
        )
        backlog = self._fetch_backlog(now, exclude=new_sirets) if include_backlog else []
        queue = candidates + backlog

        newly_found: list[models.Establishment] = []
        lookup_targets = [
            est
            for est in queue
            if self._should_lookup(
                est,
                now,
                is_new=(est.siret in new_sirets),
                reset_google_state=reset_google_state,
                recheck_all=recheck_all,
            )
        ]
        queue_count = len(lookup_targets)
        pending_count = queue_count
        eligible_count = queue_count
        matched_count = 0

        if progress_callback:
            progress_callback(queue_count, eligible_count, 0, matched_count, pending_count)

        processed_count = 0
        for establishment in lookup_targets:
            if reset_google_state:
                # Important: on purge "biz-by-biz" juste avant le lookup, afin d'éviter
                # qu'un crash au milieu de la synchro ne supprime les fiches Google d'une
                # grande partie des établissements non traités.
                self._reset_google_state(establishment)
            assert self._lookup_engine is not None
            result = self._lookup_engine.lookup(establishment, now=now)
            result = self._lookup_engine.apply_lookup_result(
                establishment,
                result,
                now,
                newly_found=newly_found,
            )
            processed_count += 1
            matched_count = len(newly_found)
            pending_count = max(queue_count - processed_count, 0)
            if progress_callback and (
                processed_count % PROGRESS_BATCH_SIZE == 0 or processed_count == eligible_count
            ):
                self._session.flush()
                progress_callback(queue_count, eligible_count, processed_count, matched_count, pending_count)

        self._session.flush()
        remaining = max(queue_count - processed_count, 0)
        return GoogleEnrichmentResult(
            matches=newly_found,
            queue_count=queue_count,
            eligible_count=eligible_count,
            matched_count=len(newly_found),
            remaining_count=remaining,
            api_call_count=self._api_call_count,
            api_error_count=self._api_error_count,
        )

    def manual_check(self, establishment: models.Establishment) -> GoogleMatch | None:
        """Lookup a single establishment without processing the backlog."""

        if not self._client or not self._rate_limiter or not self._lookup_engine:
            raise GooglePlacesError("Google Places API key is not configured.")

        now = utcnow()

        # Un recheck manuel doit refléter le résultat courant, même si une fiche Google
        # avait été trouvée auparavant. On réinitialise donc l'état avant de relancer
        # la recherche afin qu'un résultat "not_found" écrase bien les champs en base.
        self._reset_google_state(establishment)
        if not self._has_searchable_identity(establishment):
            establishment.google_check_status = "insufficient"
            establishment.google_last_checked_at = establishment.google_last_checked_at or now
            self._session.flush()
            return None

        establishment.google_match_confidence = None
        result = self._lookup_engine.lookup(establishment, now=now)
        result = self._lookup_engine.apply_lookup_result(establishment, result, now)
        self._session.flush()
        return result

    def _filter_candidates(
        self,
        establishments: Iterable[models.Establishment],
        *,
        now: datetime,
        reset_google_state: bool = False,
        recheck_all: bool = False,
    ) -> list[models.Establishment]:
        filtered: list[models.Establishment] = []
        updated = False
        for establishment in establishments:
            if not reset_google_state and not recheck_all and establishment.google_place_url:
                continue
            if not reset_google_state and not recheck_all and establishment.google_check_status == TYPE_MISMATCH_STATUS:
                continue
            if not self._has_searchable_identity(establishment):
                # Si on purge les données Google, on le fait quand même, même si on ne peut
                # pas relancer une recherche fiable (on évite ainsi de conserver une fiche obsolète).
                if reset_google_state and self._reset_google_state(establishment):
                    updated = True
                establishment.google_check_status = "insufficient"
                establishment.google_last_checked_at = establishment.google_last_checked_at or now
                updated = True
                continue
            filtered.append(establishment)
        if updated:
            self._session.flush()
        return filtered

    def _fetch_backlog(self, now: datetime, *, exclude: set[str]) -> list[models.Establishment]:
        if self._settings.daily_retry_limit <= 0:
            return []

        selection_limit = max(self._settings.daily_retry_limit * 5, self._settings.daily_retry_limit)
        stmt = (
            select(models.Establishment)
            .where(
                models.Establishment.google_place_url.is_(None),
                models.Establishment.google_check_status != "insufficient",
                models.Establishment.google_check_status != TYPE_MISMATCH_STATUS,
            )
            .order_by(
                models.Establishment.google_last_checked_at.asc().nullsfirst(),
                models.Establishment.first_seen_at.asc(),
            )
            .limit(selection_limit)
        )

        backlog: list[models.Establishment] = []
        updated = False
        for establishment in self._session.scalars(stmt):
            if establishment.siret in exclude:
                continue
            if establishment.google_check_status == TYPE_MISMATCH_STATUS:
                continue
            if not self._has_searchable_identity(establishment):
                establishment.google_check_status = "insufficient"
                establishment.google_last_checked_at = establishment.google_last_checked_at or now
                updated = True
                continue
            if not self._is_retry_due(establishment, now):
                continue
            backlog.append(establishment)
            if len(backlog) >= self._settings.daily_retry_limit:
                break
        if updated:
            self._session.flush()
        return backlog

    def _reset_google_state(self, establishment: models.Establishment) -> bool:
        updated = False

        def _set(attr: str, value: object) -> None:
            nonlocal updated
            if getattr(establishment, attr) != value:
                setattr(establishment, attr, value)
                updated = True

        _set("google_place_id", None)
        _set("google_place_url", None)
        _set("google_last_checked_at", None)
        _set("google_last_found_at", None)
        _set("google_match_confidence", None)
        _set("google_category_match_confidence", None)
        _set("google_listing_origin_at", None)
        _set("google_listing_origin_source", "unknown")
        _set("google_listing_age_status", "unknown")
        _set("google_contact_phone", None)
        _set("google_contact_email", None)
        _set("google_contact_website", None)
        _set("google_check_status", "pending")
        return updated

    def _has_searchable_identity(self, establishment: models.Establishment) -> bool:
        return bool(establishment.name and (establishment.libelle_commune or establishment.code_postal))

    def _should_lookup(
        self,
        establishment: models.Establishment,
        now: datetime,
        *,
        is_new: bool = False,
        reset_google_state: bool = False,
        recheck_all: bool = False,
    ) -> bool:
        if not reset_google_state and not recheck_all and establishment.google_place_url:
            return False
        if not reset_google_state and not recheck_all and establishment.google_check_status == TYPE_MISMATCH_STATUS:
            return False
        if not self._has_searchable_identity(establishment):
            return False
        if reset_google_state:
            return True
        if recheck_all:
            return True
        if is_new:
            return True
        return self._is_retry_due(establishment, now)

    def _record_api_call(self) -> None:
        current = getattr(self, "_api_call_count", 0)
        self._api_call_count = current + 1

    def _is_retry_due(self, establishment: models.Establishment, now: datetime) -> bool:
        if establishment.google_place_url:
            return False

        last_checked = establishment.google_last_checked_at
        if self._is_update_retry_due(establishment, now, last_checked):
            return True

        if not self._allows_weekday(now.weekday()):
            return False

        frequency_days = self._determine_retry_frequency_days(establishment, now)
        if last_checked is None:
            return True
        return now - last_checked >= timedelta(days=frequency_days)

    def _is_update_retry_due(
        self,
        establishment: models.Establishment,
        now: datetime,
        last_checked: datetime | None,
    ) -> bool:
        updated_at = establishment.updated_at
        if not updated_at or (last_checked and updated_at <= last_checked):
            return False

        next_allowed = self._next_allowed_check(updated_at)
        if not self._allows_weekday(now.weekday()):
            return False
        if now < next_allowed:
            return False
        if last_checked and last_checked >= next_allowed:
            return False
        return True

    def _determine_retry_frequency_days(self, establishment: models.Establishment, now: datetime) -> int:
        creation = self._resolve_creation_date(establishment)
        if creation is None:
            return 30
        age_days = (now.date() - creation).days
        if age_days < 0:
            age_days = 0
        rules = self._retry_config.micro_rules if self._is_micro_business(establishment) else self._retry_config.default_rules
        if not rules:
            return 30
        for rule in rules:
            if rule.max_age_days is None or age_days <= rule.max_age_days:
                return rule.frequency_days
        return rules[-1].frequency_days

    def _resolve_creation_date(self, establishment: models.Establishment) -> date | None:
        if establishment.date_creation:
            return establishment.date_creation
        if establishment.first_seen_at:
            return establishment.first_seen_at.date()
        if establishment.last_seen_at:
            return establishment.last_seen_at.date()
        return None

    def _next_allowed_check(self, reference: datetime) -> datetime:
        base_date = reference.date()
        allowed = sorted(self._retry_config.retry_weekdays)
        if not allowed:
            allowed = list(range(7))
        for offset in range(1, 8):
            candidate = base_date + timedelta(days=offset)
            if candidate.weekday() in allowed:
                return datetime.combine(candidate, datetime.min.time())
        return datetime.combine(base_date + timedelta(days=7), datetime.min.time())

    def _allows_weekday(self, weekday: int) -> bool:
        return not self._retry_config.retry_weekdays or weekday in self._retry_config.retry_weekdays

    def _is_micro_business(self, establishment: models.Establishment) -> bool:
        return is_micro_company(establishment.categorie_entreprise, establishment.categorie_juridique)

    def _matches_expected_google_category(
        self,
        google_types: Sequence[str],
        expected_keywords: set[str],
    ) -> tuple[bool, float | None]:
        neutral_types = getattr(self, "_neutral_google_types", set())
        similarity_threshold = getattr(
            self,
            "_category_similarity_threshold",
            getattr(getattr(self, "_settings", None), "category_similarity_threshold", 0.72),
        )
        return matches_expected_google_category(
            google_types,
            expected_keywords,
            neutral_types=neutral_types,
            similarity_threshold=similarity_threshold,
        )

