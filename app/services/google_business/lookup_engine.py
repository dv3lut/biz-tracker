from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable, Sequence

from sqlalchemy.orm import Session

from app.clients.google_places_client import GooglePlacesClient, GooglePlacesError
from app.db import models
from app.observability import log_event
from app.services.google_business import (
    adjust_listing_status_for_contacts,
    build_place_query,
    compute_confidence,
    compute_confidence_details,
    compute_listing_age_status,
    extract_listing_origin,
    extract_ratings_total,
    matches_expected_google_category,
)
from app.services.google_business.constants import (
    PLACE_DETAILS_FIELDS,
    PLACEHOLDER_TOKENS,
    TYPE_MISMATCH_STATUS,
)
from app.services.google_business.keywords import resolve_expected_keywords
from app.services.google_business.types import GoogleMatch
from app.services.rate_limiter import RateLimiter
from app.utils.dates import utcnow

_LOGGER = logging.getLogger(__name__)


CategoryMatcher = Callable[[Sequence[str], set[str]], tuple[bool, float | None]]
ConfidenceCalculator = Callable[[models.Establishment, str, str], float]


class GoogleLookupEngine:
    """Encapsule la logique de recherche et de mise à jour des fiches Google."""

    def __init__(
        self,
        session: Session,
        client: GooglePlacesClient,
        rate_limiter: RateLimiter,
        settings,
        *,
        naf_keyword_map: dict[str, set[str]],
        neutral_google_types: set[str],
        category_similarity_threshold: float,
        api_call_hook: Callable[[], None],
        compute_confidence_func: ConfidenceCalculator | None = None,
        category_matcher: CategoryMatcher | None = None,
    ) -> None:
        self._session = session
        self._client = client
        self._rate_limiter = rate_limiter
        self._settings = settings
        self._naf_keyword_map = naf_keyword_map
        self._neutral_google_types = neutral_google_types
        self._category_similarity_threshold = category_similarity_threshold
        self._api_call_hook = api_call_hook
        self._compute_confidence_func = compute_confidence_func or compute_confidence
        self._category_matcher: CategoryMatcher = category_matcher or self._default_category_matcher

    def lookup(self, establishment: models.Establishment, *, now: datetime | None = None) -> GoogleMatch | None:
        if now is None:
            now = utcnow()
        establishment_payload = self._serialize_establishment(establishment)
        expected_keywords = resolve_expected_keywords(self._naf_keyword_map, establishment)
        query = build_place_query(establishment, PLACEHOLDER_TOKENS)
        establishment.google_match_confidence = None
        if not query:
            log_event(
                "sync.google.lookup.skipped",
                establishment=establishment_payload,
                reason="insufficient_query",
            )
            establishment.google_check_status = "insufficient"
            establishment.google_last_checked_at = establishment.google_last_checked_at or utcnow()
            self._session.flush()
            return None

        try:
            self._rate_limiter.acquire()
            self._record_api_call()
            candidates = self._client.find_place(query, fields="place_id,name,formatted_address")
        except GooglePlacesError as exc:
            _LOGGER.warning("Recherche Google Places échouée pour %s: %s", establishment.siret, exc)
            log_event(
                "sync.google.find_place.error",
                establishment=establishment_payload,
                query=query,
                error={"type": type(exc).__name__, "message": str(exc)},
            )
            return None

        log_event(
            "sync.google.find_place.query",
            establishment=establishment_payload,
            query=query,
            candidate_count=len(candidates),
            expected_keywords=sorted(expected_keywords) if expected_keywords else [],
            min_match_confidence=self._settings.min_match_confidence,
        )

        best_candidate: GoogleMatch | None = None
        best_mismatch_candidate: GoogleMatch | None = None
        best_confidence: float | None = None
        best_category_confidence: float | None = None
        type_mismatch_detected = False

        for candidate in candidates:
            place_id = candidate.get("place_id")
            name = candidate.get("name")
            formatted_address = candidate.get("formatted_address")
            if not place_id or not name:
                continue
            confidence = self._compute_confidence_func(establishment, name, formatted_address)
            computed_confidence, confidence_details = compute_confidence_details(
                establishment,
                name,
                formatted_address,
            )
            if abs(confidence - computed_confidence) > 1e-6:
                confidence_details = {
                    "final_score": round(confidence, 4),
                    "source": "custom_confidence",
                }
            else:
                confidence_details["final_score"] = round(confidence, 4)
            candidate_payload = {
                "place_id": place_id,
                "name": name,
                "formatted_address": formatted_address,
            }
            decision = "accepted" if confidence >= self._settings.min_match_confidence else "below_threshold"
            log_event(
                "sync.google.find_place.candidate_scored",
                establishment=establishment_payload,
                candidate=candidate_payload,
                confidence=round(confidence, 4),
                confidence_details=confidence_details,
                min_match_confidence=self._settings.min_match_confidence,
                decision=decision,
            )
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
                log_event(
                    "sync.google.place_details.error",
                    establishment=establishment_payload,
                    candidate=candidate_payload,
                    error={"type": type(exc).__name__, "message": str(exc)},
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
            listing_status = compute_listing_age_status(
                list(review_dates),
                ratings_total=extract_ratings_total(details),
                assumed_recent=assumed_recent,
                now=now,
            )
            listing_status = adjust_listing_status_for_contacts(
                listing_status,
                contact_phone=contact_phone,
                contact_email=contact_email,
                contact_website=contact_website,
            )
            raw_types = details.get("types")
            google_types = raw_types if isinstance(raw_types, list) else []
            matches_category, category_similarity = self._category_matcher(google_types, expected_keywords)
            log_event(
                "sync.google.category.evaluated",
                establishment=establishment_payload,
                candidate=candidate_payload,
                category={
                    "matched": matches_category,
                    "similarity": round(category_similarity, 4) if category_similarity is not None else None,
                    "threshold": self._category_similarity_threshold,
                    "expected_keywords": sorted(expected_keywords) if expected_keywords else [],
                    "google_types": google_types,
                },
            )
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
                    status_override=TYPE_MISMATCH_STATUS,
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
            establishment.google_check_status = TYPE_MISMATCH_STATUS
            log_event(
                "sync.google.lookup.result",
                establishment=establishment_payload,
                status=TYPE_MISMATCH_STATUS,
                candidate_count=len(candidates),
                best_confidence=round(best_confidence, 4) if best_confidence is not None else None,
                best_category_confidence=(
                    round(best_category_confidence, 4) if best_category_confidence is not None else None
                ),
                type_mismatch_detected=type_mismatch_detected,
            )
            return None
        if best_candidate is not None and best_candidate.category_confidence is None and best_category_confidence is not None:
            best_candidate.category_confidence = best_category_confidence
        log_event(
            "sync.google.lookup.result",
            establishment=establishment_payload,
            status="found" if best_candidate else "not_found",
            candidate_count=len(candidates),
            best_confidence=round(best_confidence, 4) if best_confidence is not None else None,
            best_category_confidence=(
                round(best_category_confidence, 4) if best_category_confidence is not None else None
            ),
            type_mismatch_detected=type_mismatch_detected,
            result=(
                {
                    "place_id": best_candidate.place_id,
                    "place_url": best_candidate.place_url,
                    "confidence": round(best_candidate.confidence, 4),
                    "category_confidence": (
                        round(best_candidate.category_confidence, 4)
                        if best_candidate.category_confidence is not None
                        else None
                    ),
                    "listing_age_status": best_candidate.listing_age_status,
                    "listing_origin_source": best_candidate.listing_origin_source,
                }
                if best_candidate
                else None
            ),
        )
        return best_candidate

    def apply_lookup_result(
        self,
        establishment: models.Establishment,
        result: GoogleMatch | None,
        now: datetime,
        *,
        newly_found: list[models.Establishment] | None = None,
    ) -> GoogleMatch | None:
        establishment.google_last_checked_at = now
        if not result:
            if establishment.google_check_status not in {"found", TYPE_MISMATCH_STATUS}:
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
        try:
            self._rate_limiter.acquire()
            self._record_api_call()
            details = self._client.get_place_details(place_id, fields=PLACE_DETAILS_FIELDS)
        except GooglePlacesError:
            raise
        if not details:
            return None
        return details

    def _record_api_call(self) -> None:
        self._api_call_hook()

    def _default_category_matcher(
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

    @staticmethod
    def _extract_contact_details(details: dict[str, object]) -> tuple[str | None, str | None, str | None]:
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

    @staticmethod
    def _serialize_establishment(establishment: models.Establishment) -> dict[str, object]:
        return {
            "siret": establishment.siret,
            "name": establishment.name,
            "code_postal": establishment.code_postal,
            "libelle_commune": establishment.libelle_commune or establishment.libelle_commune_etranger,
            "naf_code": establishment.naf_code,
        }
