"""Google Places enrichment for establishments."""
from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Iterable, Sequence

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
        self._recheck_delta = timedelta(hours=self._settings.recheck_hours)

    def close(self) -> None:
        if self._client:
            self._client.close()

    def enrich(self, new_establishments: Sequence[models.Establishment]) -> list[models.Establishment]:
        if not self._client or not self._rate_limiter:
            return []

        now = datetime.utcnow()
        unique_new = {establishment.siret: establishment for establishment in new_establishments if establishment.siret}
        candidates = list(self._filter_candidates(unique_new.values(), now=now))
        backlog = self._fetch_backlog(now, exclude=set(unique_new))
        queue = candidates + backlog

        newly_found: list[models.Establishment] = []
        for establishment in queue:
            if not self._should_lookup(establishment, now):
                continue
            result = self._lookup(establishment)
            establishment.google_last_checked_at = now
            if not result:
                if establishment.google_check_status != "found":
                    establishment.google_check_status = "not_found"
                continue
            if not result.place_url:
                _LOGGER.debug("Résultat Google Places sans URL exploitable pour %s", establishment.siret)
                continue
            establishment.google_place_id = result.place_id
            establishment.google_place_url = result.place_url
            establishment.google_last_found_at = now
            establishment.google_check_status = "found"
            newly_found.append(establishment)
        self._session.flush()
        return newly_found

    def _filter_candidates(
        self,
        establishments: Iterable[models.Establishment],
        *,
        now: datetime,
    ) -> list[models.Establishment]:
        filtered: list[models.Establishment] = []
        for establishment in establishments:
            if establishment.google_place_url:
                continue
            if not self._has_searchable_identity(establishment):
                establishment.google_check_status = "insufficient"
                establishment.google_last_checked_at = establishment.google_last_checked_at or now
                continue
            filtered.append(establishment)
        return filtered

    def _fetch_backlog(self, now: datetime, *, exclude: set[str]) -> list[models.Establishment]:
        if self._settings.daily_retry_limit <= 0:
            return []
        cutoff = now - self._recheck_delta
        stmt = (
            select(models.Establishment)
            .where(
                models.Establishment.google_place_url.is_(None),
                models.Establishment.google_check_status != "insufficient",
                (models.Establishment.google_last_checked_at.is_(None))
                | (models.Establishment.google_last_checked_at <= cutoff),
            )
            .limit(self._settings.daily_retry_limit)
        )
        backlog: list[models.Establishment] = []
        for establishment in self._session.scalars(stmt):
            if establishment.siret in exclude:
                continue
            if self._has_searchable_identity(establishment):
                backlog.append(establishment)
            else:
                establishment.google_check_status = "insufficient"
                establishment.google_last_checked_at = establishment.google_last_checked_at or now
        return backlog

    def _has_searchable_identity(self, establishment: models.Establishment) -> bool:
        return bool(establishment.name and (establishment.libelle_commune or establishment.code_postal))

    def _should_lookup(self, establishment: models.Establishment, now: datetime) -> bool:
        if establishment.google_place_url:
            return False
        if not self._has_searchable_identity(establishment):
            return False
        if not establishment.google_last_checked_at:
            return True
        return establishment.google_last_checked_at <= now - self._recheck_delta

    def _lookup(self, establishment: models.Establishment) -> GoogleMatch | None:
        assert self._client is not None and self._rate_limiter is not None
        query = self._build_query(establishment)
        if not query:
            return None

        try:
            self._rate_limiter.acquire()
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
            details = self._client.get_place_details(place_id, fields="url,website,name,formatted_address")
        except GooglePlacesError:
            raise
        if not details:
            return None
        return details

    def _build_query(self, establishment: models.Establishment) -> str:
        parts = [establishment.name or ""]
        if establishment.libelle_commune:
            parts.append(establishment.libelle_commune)
        elif establishment.libelle_commune_etranger:
            parts.append(establishment.libelle_commune_etranger)
        if establishment.code_postal:
            parts.append(establishment.code_postal)
        return " ".join(part for part in parts if part).strip()

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
