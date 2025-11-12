"""Google Places enrichment for establishments."""
from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from typing import Callable, Iterable, Sequence
ProgressCallback = Callable[[int, int, int, int, int], None]
_PLACEHOLDER_TOKENS = {"ND"}
_PROGRESS_BATCH_SIZE = 10


def _sanitize_placeholder(value: str | None) -> str:
    if not value:
        return ""
    cleaned = value.strip()
    if not cleaned:
        return ""
    normalized = "".join(ch for ch in cleaned.upper() if ch.isalnum())
    if not normalized:
        return ""
    if normalized in _PLACEHOLDER_TOKENS:
        return ""
    if len(normalized) % 2 == 0 and all(normalized[i : i + 2] == "ND" for i in range(0, len(normalized), 2)):
        return ""
    return cleaned

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.google_places_client import GooglePlacesClient, GooglePlacesError
from app.config import get_settings
from app.db import models
from app.services.rate_limiter import RateLimiter

_LOGGER = logging.getLogger(__name__)


def _normalize(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower().strip()


@dataclass
class GoogleMatch:
    establishment: models.Establishment
    place_id: str
    place_url: str | None
    confidence: float


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
            result = self._lookup(establishment)
            establishment.google_last_checked_at = now
            if not result:
                if establishment.google_check_status != "found":
                    establishment.google_check_status = "not_found"
            else:
                if not result.place_url:
                    _LOGGER.debug("Résultat Google Places sans URL exploitable pour %s", establishment.siret)
                else:
                    establishment.google_place_id = result.place_id
                    establishment.google_place_url = result.place_url
                    establishment.google_last_found_at = now
                    newly_found.append(establishment)
                establishment.google_check_status = "found"

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

        result = self._lookup(establishment)
        establishment.google_last_checked_at = now
        if not result:
            if establishment.google_check_status != "found":
                establishment.google_check_status = "not_found"
            self._session.flush()
            return None

        establishment.google_place_id = result.place_id
        if result.place_url:
            establishment.google_place_url = result.place_url
            establishment.google_last_found_at = now
            establishment.google_check_status = "found"
        else:
            _LOGGER.debug("Résultat Google Places trouvé sans URL exploitable pour %s", establishment.siret)
            establishment.google_check_status = "found"
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
        if not self._has_searchable_identity(establishment):
            return False
        if is_new:
            return True
        return self._is_retry_due(establishment, now)

    def _lookup(self, establishment: models.Establishment) -> GoogleMatch | None:
        assert self._client is not None and self._rate_limiter is not None
        query = self._build_query(establishment)
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
        for candidate in candidates:
            place_id = candidate.get("place_id")
            name = candidate.get("name")
            formatted_address = candidate.get("formatted_address")
            if not place_id or not name:
                continue
            confidence = self._compute_confidence(establishment, name, formatted_address)
            if confidence < self._settings.min_match_confidence:
                continue
            try:
                details = self._fetch_details(place_id)
            except GooglePlacesError as exc:
                _LOGGER.warning("Lecture des détails Google Places échouée pour %s (place=%s): %s", establishment.siret, place_id, exc)
                continue
            if not details:
                continue
            url = details.get("url") or details.get("website")
            if not url:
                _LOGGER.debug("Place %s trouvée mais sans URL exploitable.", place_id)
                url = None
            match = GoogleMatch(establishment, place_id, url, confidence)
            if best_candidate is None or confidence > best_candidate.confidence:
                best_candidate = match
        return best_candidate

    def _fetch_details(self, place_id: str) -> dict[str, object] | None:
        assert self._client is not None and self._rate_limiter is not None
        try:
            self._rate_limiter.acquire()
            self._record_api_call()
            details = self._client.get_place_details(place_id, fields="url,website,name,formatted_address")
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

        if now.weekday() != 0:
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

        next_monday = self._next_monday(updated_at)
        if now.weekday() != 0:
            return False
        if now < next_monday:
            return False
        if last_checked and last_checked >= next_monday:
            return False
        return True

    def _determine_retry_frequency_days(self, establishment: models.Establishment, now: datetime) -> int:
        creation = self._resolve_creation_date(establishment)
        if creation is None:
            return 30
        age_days = (now.date() - creation).days
        if age_days < 0:
            age_days = 0
        if age_days < 60:
            return 7
        if age_days < 120:
            return 14
        return 30

    def _resolve_creation_date(self, establishment: models.Establishment) -> date | None:
        if establishment.date_creation:
            return establishment.date_creation
        if establishment.first_seen_at:
            return establishment.first_seen_at.date()
        if establishment.last_seen_at:
            return establishment.last_seen_at.date()
        return None

    @staticmethod
    def _next_monday(reference: datetime) -> datetime:
        base_date = reference.date()
        days_ahead = (7 - base_date.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        next_date = base_date + timedelta(days=days_ahead)
        return datetime.combine(next_date, datetime.min.time())

    def _build_query(self, establishment: models.Establishment) -> str:
        parts = [
            _sanitize_placeholder(establishment.name),
            _sanitize_placeholder(establishment.libelle_commune),
        ]
        if not parts[-1]:
            parts[-1] = _sanitize_placeholder(establishment.libelle_commune_etranger)
        parts.append(_sanitize_placeholder(establishment.code_postal))
        filtered = [part for part in parts if part]
        return " ".join(filtered)

    def _compute_confidence(self, establishment: models.Establishment, candidate_name: str, candidate_address: str | None) -> float:
        ref_name = _normalize(establishment.name)
        cand_name = _normalize(candidate_name)
        if not ref_name or not cand_name:
            return 0.0
        name_score = SequenceMatcher(None, ref_name, cand_name).ratio()

        score = name_score
        if establishment.code_postal and candidate_address:
            if establishment.code_postal in candidate_address:
                score = min(1.0, score + 0.1)
        if establishment.libelle_commune and candidate_address:
            if _normalize(establishment.libelle_commune) in _normalize(candidate_address):
                score = min(1.0, score + 0.1)
        return score
