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
from app.services.google_business.match_rules import evaluate_candidate_match, haversine_distance_m
from app.services.rate_limiter import RateLimiter
from app.utils.dates import utcnow

_LOGGER = logging.getLogger(__name__)


CategoryMatcher = Callable[[Sequence[str], set[str]], tuple[bool, float | None]]


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
        api_error_hook: Callable[[str], None] | None = None,
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
        self._api_error_hook = api_error_hook
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
            candidates = self._client.find_place(query, fields="place_id,name,formatted_address,geometry")
        except GooglePlacesError as exc:
            self._record_api_error("find_place")
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
        )

        best_candidate: GoogleMatch | None = None
        best_mismatch_candidate: GoogleMatch | None = None
        best_match_score: float | None = None
        best_category_confidence: float | None = None
        type_mismatch_detected = False

        scored_candidates: list[tuple[float, dict[str, object]]] = []

        for candidate in candidates:
            place_id = candidate.get("place_id")
            name = candidate.get("name")
            formatted_address = candidate.get("formatted_address")
            if not place_id or not name:
                continue
            candidate_payload = {
                "place_id": place_id,
                "name": name,
                "formatted_address": formatted_address,
            }

            decision = evaluate_candidate_match(establishment, name, formatted_address)
            if best_match_score is None or decision.score > best_match_score:
                best_match_score = decision.score
            log_event(
                "sync.google.find_place.candidate_scored",
                establishment=establishment_payload,
                candidate=candidate_payload,
                match_score=round(decision.score, 4),
                decision_details=decision.details,
                decision=(
                    "accepted"
                    if decision.accept
                    else "needs_distance"
                    if decision.needs_distance_check
                    else "rejected"
                ),
            )

            if decision.accept or decision.needs_distance_check:
                scored_candidates.append((decision.score, candidate))

        # On ne tente pas uniquement le 1er résultat Google: on évalue les meilleurs candidats.
        scored_candidates.sort(key=lambda item: item[0], reverse=True)
        max_candidates = 5
        shortlisted = [candidate for _score, candidate in scored_candidates[:max_candidates]]

        for candidate in shortlisted:
            place_id = candidate.get("place_id")
            name = candidate.get("name")
            formatted_address = candidate.get("formatted_address")
            if not place_id or not name:
                continue

            candidate_payload = {
                "place_id": place_id,
                "name": name,
                "formatted_address": formatted_address,
            }

            # Recalcul décision (pure) pour éviter de stocker trop d'état
            decision = evaluate_candidate_match(establishment, name, formatted_address)
            if not decision.accept and decision.needs_distance_check:
                distance_m = self._maybe_compute_distance_m(establishment, candidate)
                decision = evaluate_candidate_match(
                    establishment,
                    name,
                    formatted_address,
                    distance_m=distance_m,
                )
                log_event(
                    "sync.google.match.distance",
                    establishment=establishment_payload,
                    candidate=candidate_payload,
                    distance_m=round(distance_m, 1) if distance_m is not None else None,
                    threshold_m=decision.details.get("distance_threshold_m"),
                    accepted=decision.accept,
                )
            if not decision.accept:
                continue

            # Candidat validé par les règles: on récupère les détails + on check la catégorie.
            try:
                details = self._fetch_details(place_id)
            except GooglePlacesError as exc:
                self._record_api_error("place_details")
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
                mismatch_match = GoogleMatch(
                    establishment,
                    place_id,
                    url,
                    confidence=decision.score,
                    category_confidence=category_similarity,
                    listing_origin_at=origin_at,
                    listing_origin_source=origin_source,
                    listing_age_status=listing_status,
                    status_override=TYPE_MISMATCH_STATUS,
                    contact_phone=contact_phone,
                    contact_email=contact_email,
                    contact_website=contact_website,
                )
                if best_mismatch_candidate is None or mismatch_match.confidence > best_mismatch_candidate.confidence:
                    best_mismatch_candidate = mismatch_match
                continue

            match = GoogleMatch(
                establishment,
                place_id,
                url,
                decision.score,
                category_confidence=category_similarity,
                listing_origin_at=origin_at,
                listing_origin_source=origin_source,
                listing_age_status=listing_status,
                contact_phone=contact_phone,
                contact_email=contact_email,
                contact_website=contact_website,
            )
            if best_candidate is None or match.confidence > best_candidate.confidence:
                best_candidate = match

        establishment.google_match_confidence = best_match_score if best_match_score is not None else None
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
                best_match_score=round(best_match_score, 4) if best_match_score is not None else None,
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
            best_match_score=round(best_match_score, 4) if best_match_score is not None else None,
            best_category_confidence=(
                round(best_category_confidence, 4) if best_category_confidence is not None else None
            ),
            type_mismatch_detected=type_mismatch_detected,
            result=(
                {
                    "place_id": best_candidate.place_id,
                    "place_url": best_candidate.place_url,
                    "match_score": round(best_candidate.confidence, 4),
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

    def _maybe_compute_distance_m(
        self,
        establishment: models.Establishment,
        candidate: dict[str, object],
    ) -> float | None:
        ref_location = self._geocode_establishment_location(establishment)
        cand_location = self._extract_candidate_location(candidate)
        if not ref_location or not cand_location:
            return None
        return haversine_distance_m(ref_location[0], ref_location[1], cand_location[0], cand_location[1])

    def _geocode_establishment_location(self, establishment: models.Establishment) -> tuple[float, float] | None:
        parts = [
            establishment.numero_voie,
            establishment.indice_repetition,
            establishment.type_voie,
            establishment.libelle_voie,
            establishment.code_postal,
            establishment.libelle_commune or establishment.libelle_commune_etranger,
        ]
        query = " ".join([part for part in parts if part and str(part).strip()])
        if not query:
            return None
        try:
            self._rate_limiter.acquire()
            self._record_api_call()
            candidates = self._client.find_place(query, fields="place_id,geometry")
        except GooglePlacesError:
            self._record_api_error("geocode")
            return None
        if not candidates:
            return None
        return self._extract_candidate_location(candidates[0])

    @staticmethod
    def _extract_candidate_location(candidate: dict[str, object]) -> tuple[float, float] | None:
        geometry = candidate.get("geometry")
        if not isinstance(geometry, dict):
            return None
        location = geometry.get("location")
        if not isinstance(location, dict):
            return None
        lat = location.get("lat")
        lng = location.get("lng")
        if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
            return None
        return float(lat), float(lng)

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

    def _record_api_error(self, operation: str) -> None:
        hook = getattr(self, "_api_error_hook", None)
        if not hook:
            return
        hook(operation)

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
        payload: dict[str, object] = {
            "siret": establishment.siret,
            "name": establishment.name,
            "code_postal": establishment.code_postal,
            "libelle_commune": establishment.libelle_commune or establishment.libelle_commune_etranger,
            "naf_code": establishment.naf_code,
        }
        created_run_id = getattr(establishment, "created_run_id", None)
        last_run_id = getattr(establishment, "last_run_id", None)
        if created_run_id is not None:
            payload["created_run_id"] = str(created_run_id)
        if last_run_id is not None:
            payload["last_run_id"] = str(last_run_id)
        return payload
