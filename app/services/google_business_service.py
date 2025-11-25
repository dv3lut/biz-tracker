"""Google Places enrichment for establishments."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable, Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.google_places_client import GooglePlacesClient, GooglePlacesError
from app.config import get_settings
from app.db import models
from app.services.google_business import (
    build_place_query,
    compute_confidence,
    compute_listing_age_status,
    extract_listing_origin,
    extract_ratings_total,
    matches_expected_google_category,
    should_assume_recent_listing,
    tokenize_text,
)
from app.services.rate_limiter import RateLimiter
from app.services.google_retry_config import GoogleRetryRuntimeConfig, load_runtime_google_retry_config
from app.utils.business_types import is_micro_company

ProgressCallback = Callable[[int, int, int, int, int], None]
_PLACEHOLDER_TOKENS = {"ND"}
_PROGRESS_BATCH_SIZE = 10
_TYPE_MISMATCH_STATUS = "type_mismatch"
_RECENT_NO_CONTACT_STATUS = "recent_creation_missing_contact"
_PLACE_DETAILS_FIELDS = (
    "url,website,name,formatted_address,types,business_status,opening_hours,current_opening_hours,"
    "reviews,user_ratings_total,formatted_phone_number,international_phone_number"
)


_LOGGER = logging.getLogger(__name__)


@dataclass
class GoogleMatch:
    establishment: models.Establishment
    place_id: str
    place_url: str | None
    confidence: float
    category_confidence: float | None
    listing_origin_at: datetime | None
    listing_origin_source: str
    listing_age_status: str
    status_override: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    contact_website: str | None = None


@dataclass
class GoogleEnrichmentResult:
    matches: list[models.Establishment]
    queue_count: int
    eligible_count: int
    matched_count: int
    remaining_count: int
    api_call_count: int


class GoogleBusinessService:
    """Lookup Google My Business pages for establishments lacking an association."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._settings = get_settings().google
        self._retry_config: GoogleRetryRuntimeConfig = load_runtime_google_retry_config(session)
        self._category_similarity_threshold = self._settings.category_similarity_threshold
        self._neutral_google_types = {"point_of_interest", "establishment", "store", "food"}
        self._naf_keyword_map = self._load_naf_keyword_map()
        if not self._settings.enabled:
            self._client: GooglePlacesClient | None = None
            self._rate_limiter = None
        else:
            self._client = GooglePlacesClient()
            self._rate_limiter = RateLimiter(self._settings.max_calls_per_minute)
        self._api_call_count = 0

    def close(self) -> None:
        if self._client:
            self._client.close()

    def enrich(
        self,
        new_establishments: Sequence[models.Establishment],
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> GoogleEnrichmentResult:
        if not self._client or not self._rate_limiter:
            return GoogleEnrichmentResult(
                matches=[],
                queue_count=0,
                eligible_count=0,
                matched_count=0,
                remaining_count=0,
                api_call_count=0,
            )

        now = datetime.utcnow()
        self._api_call_count = 0
        unique_new = {establishment.siret: establishment for establishment in new_establishments if establishment.siret}
        new_sirets = set(unique_new)
        candidates = list(self._filter_candidates(unique_new.values(), now=now))
        backlog = self._fetch_backlog(now, exclude=new_sirets)
        queue = candidates + backlog

        newly_found: list[models.Establishment] = []
        lookup_targets = [
            est for est in queue if self._should_lookup(est, now, is_new=(est.siret in new_sirets))
        ]
        queue_count = len(lookup_targets)
        pending_count = queue_count
        eligible_count = queue_count
        matched_count = 0

        if progress_callback:
            progress_callback(queue_count, eligible_count, 0, matched_count, pending_count)

        processed_count = 0
        for establishment in lookup_targets:
            result = self._lookup(establishment, now=now)
            result = self._apply_lookup_result(
                establishment,
                result,
                now,
                newly_found=newly_found,
            )
            processed_count += 1
            matched_count = len(newly_found)
            pending_count = max(queue_count - processed_count, 0)
            if progress_callback and (
                processed_count % _PROGRESS_BATCH_SIZE == 0 or processed_count == eligible_count
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
        )

    def manual_check(self, establishment: models.Establishment) -> GoogleMatch | None:
        """Lookup a single establishment without processing the backlog."""

        if not self._client or not self._rate_limiter:
            raise GooglePlacesError("Google Places API key is not configured.")

        now = datetime.utcnow()
        if not self._has_searchable_identity(establishment):
            establishment.google_check_status = "insufficient"
            establishment.google_last_checked_at = establishment.google_last_checked_at or now
            self._session.flush()
            return None

        establishment.google_match_confidence = None
        result = self._lookup(establishment, now=now)
        result = self._apply_lookup_result(establishment, result, now)
        self._session.flush()
        return result

    def _filter_candidates(
        self,
        establishments: Iterable[models.Establishment],
        *,
        now: datetime,
    ) -> list[models.Establishment]:
        filtered: list[models.Establishment] = []
        updated = False
        for establishment in establishments:
            if establishment.google_place_url:
                continue
            if establishment.google_check_status == _TYPE_MISMATCH_STATUS:
                continue
            if not self._has_searchable_identity(establishment):
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
                models.Establishment.google_check_status != _TYPE_MISMATCH_STATUS,
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
            if establishment.google_check_status == _TYPE_MISMATCH_STATUS:
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

    def _has_searchable_identity(self, establishment: models.Establishment) -> bool:
        return bool(establishment.name and (establishment.libelle_commune or establishment.code_postal))

    def _should_lookup(self, establishment: models.Establishment, now: datetime, *, is_new: bool = False) -> bool:
        if establishment.google_place_url:
            return False
        if establishment.google_check_status == _TYPE_MISMATCH_STATUS:
            return False
        if not self._has_searchable_identity(establishment):
            return False
        if is_new:
            return True
        return self._is_retry_due(establishment, now)

    def _lookup(self, establishment: models.Establishment, *, now: datetime | None = None) -> GoogleMatch | None:
        if now is None:
            now = datetime.utcnow()
        assert self._client is not None and self._rate_limiter is not None
        query = build_place_query(establishment, _PLACEHOLDER_TOKENS)
        establishment.google_match_confidence = None
        if not query:
            establishment.google_check_status = "insufficient"
            establishment.google_last_checked_at = establishment.google_last_checked_at or datetime.utcnow()
            self._session.flush()
            return None

        try:
            self._rate_limiter.acquire()
            self._record_api_call()
            candidates = self._client.find_place(query, fields="place_id,name,formatted_address")
        except GooglePlacesError as exc:
            _LOGGER.warning("Recherche Google Places échouée pour %s: %s", establishment.siret, exc)
            return None

        best_candidate: GoogleMatch | None = None
        best_mismatch_candidate: GoogleMatch | None = None
        best_confidence: float | None = None
        best_category_confidence: float | None = None
        expected_keywords = self._resolve_expected_keywords(establishment)
        type_mismatch_detected = False
        for candidate in candidates:
            place_id = candidate.get("place_id")
            name = candidate.get("name")
            formatted_address = candidate.get("formatted_address")
            if not place_id or not name:
                continue
            confidence = self._compute_confidence(establishment, name, formatted_address)
            if best_confidence is None or confidence > best_confidence:
                best_confidence = confidence
            if confidence < self._settings.min_match_confidence:
                continue
            try:
                details = self._fetch_details(place_id)
            except GooglePlacesError as exc:
                _LOGGER.warning(
                    "Lecture des détails Google Places échouée pour %s (place=%s): %s",
                    establishment.siret,
                    place_id,
                    exc,
                )
                continue
            if not details:
                continue
            contact_phone, contact_email, contact_website = self._extract_contact_details(details)
            url = details.get("url") or contact_website
            if not url:
                _LOGGER.debug("Place %s trouvée mais sans URL exploitable.", place_id)
                url = None
            origin_at, origin_source, assumed_recent, review_dates = extract_listing_origin(details)
            listing_status = self._compute_listing_age_status(
                review_dates,
                extract_ratings_total(details),
                assumed_recent,
                now,
            )
            listing_status = self._adjust_listing_status_for_contacts(
                listing_status,
                contact_phone=contact_phone,
                contact_email=contact_email,
                contact_website=contact_website,
            )
            raw_types = details.get("types")
            google_types = raw_types if isinstance(raw_types, list) else []
            matches_category, category_similarity = self._matches_expected_google_category(google_types, expected_keywords)
            if category_similarity is not None and (
                best_category_confidence is None or category_similarity > best_category_confidence
            ):
                best_category_confidence = category_similarity
            if not matches_category:
                type_mismatch_detected = True
                _LOGGER.debug(
                    "Fiche Google %s ignorée pour %s : types %s incompatibles avec les mots-clés %s",
                    place_id,
                    establishment.siret,
                    google_types,
                    sorted(expected_keywords) if expected_keywords else [],
                )
                mismatch_match = GoogleMatch(
                    establishment,
                    place_id,
                    url,
                    confidence=confidence,
                    category_confidence=category_similarity,
                    listing_origin_at=origin_at,
                    listing_origin_source=origin_source,
                    listing_age_status=listing_status,
                    status_override=_TYPE_MISMATCH_STATUS,
                    contact_phone=contact_phone,
                    contact_email=contact_email,
                    contact_website=contact_website,
                )
                if best_mismatch_candidate is None or confidence > best_mismatch_candidate.confidence:
                    best_mismatch_candidate = mismatch_match
                continue
            match = GoogleMatch(
                establishment,
                place_id,
                url,
                confidence,
                category_confidence=category_similarity,
                listing_origin_at=origin_at,
                listing_origin_source=origin_source,
                listing_age_status=listing_status,
                contact_phone=contact_phone,
                contact_email=contact_email,
                contact_website=contact_website,
            )
            if best_candidate is None or confidence > best_candidate.confidence:
                best_candidate = match
        establishment.google_match_confidence = best_confidence if best_confidence is not None else None
        establishment.google_category_match_confidence = (
            best_category_confidence if best_category_confidence is not None else None
        )
        if best_candidate is None and best_mismatch_candidate is not None:
            best_candidate = best_mismatch_candidate
        if best_candidate is None and type_mismatch_detected:
            establishment.google_check_status = _TYPE_MISMATCH_STATUS
            return None
        if best_candidate is not None:
            if best_candidate.category_confidence is None and best_category_confidence is not None:
                best_candidate.category_confidence = best_category_confidence
        return best_candidate

    def _apply_lookup_result(
        self,
        establishment: models.Establishment,
        result: GoogleMatch | None,
        now: datetime,
        *,
        newly_found: list[models.Establishment] | None = None,
    ) -> GoogleMatch | None:
        establishment.google_last_checked_at = now
        if not result:
            if establishment.google_check_status not in {"found", _TYPE_MISMATCH_STATUS}:
                establishment.google_check_status = "not_found"
            return None

        establishment.google_place_id = result.place_id
        if result.place_url:
            establishment.google_place_url = result.place_url
            establishment.google_last_found_at = now
        else:
            _LOGGER.debug("Résultat Google Places trouvé sans URL exploitable pour %s", establishment.siret)

        new_status = result.status_override or "found"
        establishment.google_check_status = new_status
        if new_status == "found" and newly_found is not None:
            newly_found.append(establishment)

        establishment.google_listing_origin_at = result.listing_origin_at
        establishment.google_listing_origin_source = result.listing_origin_source or "unknown"
        establishment.google_listing_age_status = result.listing_age_status or "unknown"
        if result.category_confidence is not None:
            establishment.google_category_match_confidence = result.category_confidence
        establishment.google_contact_phone = result.contact_phone
        establishment.google_contact_email = result.contact_email
        establishment.google_contact_website = result.contact_website
        return result

    def _fetch_details(self, place_id: str) -> dict[str, object] | None:
        assert self._client is not None and self._rate_limiter is not None
        try:
            self._rate_limiter.acquire()
            self._record_api_call()
            details = self._client.get_place_details(place_id, fields=_PLACE_DETAILS_FIELDS)
        except GooglePlacesError:
            raise
        if not details:
            return None
        return details

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

    def _resolve_expected_keywords(self, establishment: models.Establishment) -> set[str]:
        keywords = set()
        keywords |= tokenize_text(establishment.naf_libelle)
        naf_code = self._sanitize_naf_code(establishment.naf_code)
        if naf_code:
            keywords |= self._naf_keyword_map.get(naf_code, set())
        return keywords

    def _compute_confidence(self, establishment: models.Establishment, name: str, formatted_address: str) -> float:
        return compute_confidence(establishment, name, formatted_address)

    def _matches_expected_google_category(
        self,
        google_types: Sequence[str],
        expected_keywords: set[str],
    ) -> tuple[bool, float | None]:
        return matches_expected_google_category(
            google_types,
            expected_keywords,
            neutral_types=self._neutral_google_types,
            similarity_threshold=self._category_similarity_threshold,
        )

    def _compute_listing_age_status(
        self,
        review_dates: Sequence[datetime],
        ratings_total: int | None,
        assumed_recent: bool,
        now: datetime,
    ) -> str:
        return compute_listing_age_status(
            list(review_dates),
            ratings_total=ratings_total,
            assumed_recent=assumed_recent,
            now=now,
        )

    def _should_assume_recent_listing(self, details: dict[str, object]) -> bool:
        return should_assume_recent_listing(details)

    def _extract_contact_details(self, details: dict[str, object]) -> tuple[str | None, str | None, str | None]:
        phone = details.get("formatted_phone_number")
        if isinstance(phone, str):
            phone = phone.strip() or None
        if not phone:
            alt_phone = details.get("international_phone_number")
            if isinstance(alt_phone, str):
                phone = alt_phone.strip() or None
        email = None
        for key in ("email", "business_email", "contact_email"):
            raw = details.get(key)
            if isinstance(raw, str) and raw.strip():
                email = raw.strip()
                break
        website = details.get("website")
        if isinstance(website, str) and website.strip():
            website = website.strip()
        else:
            website = None
        return phone, email, website

    def _adjust_listing_status_for_contacts(
        self,
        listing_status: str,
        *,
        contact_phone: str | None,
        contact_email: str | None,
        contact_website: str | None,
    ) -> str:
        normalized = listing_status or "unknown"
        if normalized == "recent_creation" and not any([contact_phone, contact_email, contact_website]):
            return _RECENT_NO_CONTACT_STATUS
        return normalized

    def _load_naf_keyword_map(self) -> dict[str, set[str]]:
        stmt = (
            select(
                models.NafSubCategory.naf_code,
                models.NafSubCategory.name,
                models.NafCategory.name,
                models.NafCategory.keywords,
            )
            .join(models.NafCategory, models.NafCategory.id == models.NafSubCategory.category_id)
            .where(models.NafSubCategory.is_active.is_(True))
        )
        mapping: dict[str, set[str]] = {}
        for naf_code, sub_name, category_name, category_keywords in self._session.execute(stmt):
            normalized_code = self._sanitize_naf_code(naf_code)
            if not normalized_code:
                continue
            keywords = tokenize_text(sub_name)
            keywords |= tokenize_text(category_name)
            if category_keywords:
                for keyword in category_keywords:
                    keywords |= tokenize_text(keyword)
            if keywords:
                mapping[normalized_code] = keywords
        return mapping

    def _sanitize_naf_code(self, naf_code: str | None) -> str:
        if not naf_code:
            return ""
        return "".join(ch for ch in naf_code.upper() if ch.isalnum())

