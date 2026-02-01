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
from app.observability import log_event
from app.services.google_business.google_constants import (
    PLACE_DETAILS_FIELDS,
    PROGRESS_BATCH_SIZE,
    RECENT_NO_CONTACT_STATUS,
    TYPE_MISMATCH_STATUS,
)
from app.services.google_business.google_keywords import build_naf_keyword_map
from app.services.google_business.google_lookup_engine import GoogleLookupEngine
from app.services.google_business.google_matching import matches_expected_google_category
from app.services.google_business.google_types import GoogleEnrichmentResult, GoogleMatch
from app.services.google.google_retry_config import GoogleRetryRuntimeConfig, load_runtime_google_retry_config
from app.services.rate_limiter import RateLimiter
from app.utils.business_types import is_micro_company
from app.utils.dates import utcnow
from app.utils.google_listing import normalize_listing_age_status

ProgressCallback = Callable[[int, int, int, int, int], None]
AgeBuckets = dict[str, int]


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
                missing_contact_checked_count=0,
                missing_contact_updated_count=0,
                retry_backlog_count=0,
                retry_backlog_age_buckets=None,
                missing_contact_age_buckets=None,
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
        missing_contact_checked = 0
        missing_contact_updated = 0
        missing_contact_age_buckets: AgeBuckets | None = None
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
        retry_backlog_targets = [est for est in lookup_targets if est.siret not in new_sirets]
        retry_backlog_age_buckets = self._bucket_age_days(retry_backlog_targets, now)
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
        if include_backlog:
            (
                missing_contact_checked,
                missing_contact_updated,
                missing_contact_age_buckets,
            ) = self._refresh_missing_contact_listings(now)
        remaining = max(queue_count - processed_count, 0)
        return GoogleEnrichmentResult(
            matches=newly_found,
            queue_count=queue_count,
            eligible_count=eligible_count,
            matched_count=len(newly_found),
            remaining_count=remaining,
            api_call_count=self._api_call_count,
            api_error_count=self._api_error_count,
            missing_contact_checked_count=missing_contact_checked,
            missing_contact_updated_count=missing_contact_updated,
            retry_backlog_count=len(retry_backlog_targets),
            retry_backlog_age_buckets=retry_backlog_age_buckets,
            missing_contact_age_buckets=missing_contact_age_buckets,
        )

    def manual_check(self, establishment: models.Establishment) -> GoogleMatch | None:
        """Lookup a single establishment without processing the backlog."""

        if not self._client or not self._rate_limiter:
            return None
        settings = getattr(self, "_settings", None)
        if settings is not None and not settings.enabled:
            return None

        self._reset_google_state(establishment)
        now = utcnow()
        engine = self._get_lookup_engine()
        result = engine.lookup(establishment, now=now)
        engine.apply_lookup_result(establishment, result, now)
        self._session.flush()
        return result

    def _filter_candidates(
        self,
        establishments: Iterable[models.Establishment],
        *,
        now: datetime,
        reset_google_state: bool,
        recheck_all: bool,
    ) -> Iterable[models.Establishment]:
        for establishment in establishments:
            if not establishment.siret:
                continue
            if reset_google_state:
                yield establishment
                continue
            if establishment.google_check_status in {"found", TYPE_MISMATCH_STATUS}:
                continue
            if recheck_all:
                yield establishment
                continue
            if self._should_lookup(establishment, now, is_new=True, reset_google_state=False, recheck_all=False):
                yield establishment

    def _fetch_backlog(self, now: datetime, *, exclude: set[str]) -> list[models.Establishment]:
        retry_config = self._retry_config
        if now.weekday() not in retry_config.retry_weekdays:
            return []

        stmt = (
            select(models.Establishment)
            .where(models.Establishment.google_check_status != "found")
            .where(models.Establishment.google_check_status != TYPE_MISMATCH_STATUS)
            .where(models.Establishment.siret.not_in(exclude))
            .order_by(models.Establishment.google_last_checked_at.asc().nullsfirst())
        )
        candidates = self._session.execute(stmt).scalars().all()
        eligible: list[models.Establishment] = []
        for establishment in candidates:
            if self._should_lookup(establishment, now, is_new=False, reset_google_state=False, recheck_all=False):
                eligible.append(establishment)
            if len(eligible) >= self._settings.daily_retry_limit:
                break
        return eligible

    def _refresh_missing_contact_listings(self, now: datetime) -> tuple[int, int, AgeBuckets]:
        retry_config = self._retry_config
        if not retry_config.retry_missing_contact_enabled:
            return 0, 0, {}
        if now.weekday() not in retry_config.retry_weekdays:
            return 0, 0, {}
        if not self._client or not self._rate_limiter:
            return 0, 0, {}

        stmt = (
            select(models.Establishment)
            .where(models.Establishment.google_listing_age_status == RECENT_NO_CONTACT_STATUS)
            .where(models.Establishment.google_check_status == "found")
            .where(models.Establishment.google_place_id.is_not(None))
            .order_by(models.Establishment.google_last_checked_at.asc().nullsfirst())
        )
        candidates = self._session.execute(stmt).scalars().all()
        checked_count = 0
        updated_count = 0
        age_buckets: AgeBuckets = {}

        for establishment in candidates:
            if establishment.google_last_checked_at:
                age_days = (now - establishment.google_last_checked_at).days
                if age_days < retry_config.retry_missing_contact_frequency_days:
                    continue
            place_id = establishment.google_place_id
            if not place_id:
                continue
            checked_count += 1
            self._increment_bucket(age_buckets, establishment.google_last_checked_at, now)
            try:
                details = self._fetch_place_details(place_id)
            except GooglePlacesError as exc:
                self._record_api_error("place_details")
                _LOGGER.warning(
                    "Lecture des contacts Google Places échouée pour %s (place=%s): %s",
                    establishment.siret,
                    place_id,
                    exc,
                )
                continue
            contact_phone, contact_email, contact_website = self._extract_contact_details(details)
            establishment.google_last_checked_at = now
            if not any([contact_phone, contact_email, contact_website]):
                continue
            establishment.google_contact_phone = contact_phone
            establishment.google_contact_email = contact_email
            establishment.google_contact_website = contact_website
            if normalize_listing_age_status(establishment.google_listing_age_status) == RECENT_NO_CONTACT_STATUS:
                establishment.google_listing_age_status = "recent_creation"
            place_url = details.get("url") or contact_website
            if isinstance(place_url, str) and place_url:
                if not establishment.google_place_url:
                    establishment.google_place_url = place_url
                if establishment.google_last_found_at is None:
                    establishment.google_last_found_at = now
            updated_count += 1

        if checked_count:
            self._session.flush()

        return checked_count, updated_count, age_buckets

    @staticmethod
    def _increment_bucket(buckets: AgeBuckets, last_checked_at: datetime | None, now: datetime) -> None:
        if last_checked_at is None:
            buckets["never_checked"] = buckets.get("never_checked", 0) + 1
            return
        age_days = (now - last_checked_at).days
        if age_days < 0:
            age_days = 0
        if age_days <= 7:
            key = "0_7"
        elif age_days <= 14:
            key = "8_14"
        elif age_days <= 30:
            key = "15_30"
        elif age_days <= 60:
            key = "31_60"
        elif age_days <= 120:
            key = "61_120"
        else:
            key = "121_plus"
        buckets[key] = buckets.get(key, 0) + 1

    def _bucket_age_days(self, establishments: Sequence[models.Establishment], now: datetime) -> AgeBuckets:
        buckets: AgeBuckets = {}
        for establishment in establishments:
            self._increment_bucket(buckets, establishment.google_last_checked_at, now)
        return buckets

    def _fetch_place_details(self, place_id: str) -> dict[str, object]:
        if not self._client or not self._rate_limiter:
            raise RuntimeError("Google Places client is not initialised.")
        self._rate_limiter.acquire()
        self._record_api_call()
        details_fetcher = getattr(self._client, "place_details", None)
        if details_fetcher is None:
            details_fetcher = getattr(self._client, "get_place_details", None)
        if details_fetcher is None:
            raise AttributeError("Google Places client lacks a place details method")
        return details_fetcher(place_id, fields=PLACE_DETAILS_FIELDS)

    @staticmethod
    def _extract_contact_details(details: dict[str, object]) -> tuple[str | None, str | None, str | None]:
        phone = details.get("formatted_phone_number") or details.get("international_phone_number")
        if phone and not isinstance(phone, str):
            phone = None
        website = details.get("website")
        if website and not isinstance(website, str):
            website = None
        email = None
        return phone, email, website

    def _should_lookup(
        self,
        establishment: models.Establishment,
        now: datetime,
        *,
        is_new: bool,
        reset_google_state: bool,
        recheck_all: bool,
    ) -> bool:
        if reset_google_state:
            return True
        if recheck_all:
            return True
        if not self._settings.enabled:
            return False
        if establishment.google_check_status == "found":
            return False
        if establishment.google_check_status == TYPE_MISMATCH_STATUS:
            return False
        if is_new:
            return True
        if not establishment.google_last_checked_at:
            return True

        age_days = (now - establishment.google_last_checked_at).days
        if age_days < 0:
            return True

        # Micro-entreprises: on fait une rotation moins fréquente.
        rules = self._retry_config.micro_rules if is_micro_company(establishment) else self._retry_config.default_rules
        for rule in rules:
            if rule.max_age_days is None or age_days <= rule.max_age_days:
                return age_days >= rule.frequency_days
        return False

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

    def _reset_google_state(self, establishment: models.Establishment) -> None:
        establishment.google_place_id = None
        establishment.google_place_url = None
        establishment.google_last_checked_at = None
        establishment.google_last_found_at = None
        establishment.google_check_status = "pending"
        establishment.google_match_confidence = None
        establishment.google_category_match_confidence = None
        establishment.google_listing_origin_at = None
        establishment.google_listing_origin_source = "unknown"
        establishment.google_listing_age_status = "unknown"
        establishment.google_contact_phone = None
        establishment.google_contact_email = None
        establishment.google_contact_website = None

    def _record_api_call(self) -> None:
        current = getattr(self, "_api_call_count", 0)
        self._api_call_count = current + 1

    def _serialize_google_match(self, match: GoogleMatch) -> dict[str, object]:
        return {
            "place_id": match.place_id,
            "place_url": match.place_url,
            "match_confidence": match.confidence,
            "category_confidence": match.category_confidence,
            "listing_origin_at": match.listing_origin_at.isoformat() if match.listing_origin_at else None,
            "listing_origin_source": match.listing_origin_source,
            "listing_age_status": match.listing_age_status,
            "contact_phone": match.contact_phone,
            "contact_email": match.contact_email,
            "contact_website": match.contact_website,
        }

    def _format_progress(
        self,
        total: int,
        eligible_count: int,
        processed_count: int,
        matched_count: int,
        remaining_count: int,
    ) -> dict[str, int]:
        return {
            "queue_count": total,
            "eligible_count": eligible_count,
            "processed_count": processed_count,
            "matched_count": matched_count,
            "remaining_count": remaining_count,
        }

    def _ensure_progress_defaults(self, progress: dict[str, int] | None) -> dict[str, int]:
        if progress is None:
            return {
                "queue_count": 0,
                "eligible_count": 0,
                "processed_count": 0,
                "matched_count": 0,
                "remaining_count": 0,
            }
        return {
            "queue_count": int(progress.get("queue_count", 0)),
            "eligible_count": int(progress.get("eligible_count", 0)),
            "processed_count": int(progress.get("processed_count", 0)),
            "matched_count": int(progress.get("matched_count", 0)),
            "remaining_count": int(progress.get("remaining_count", 0)),
        }

    def _format_progress_log(
        self,
        progress: dict[str, int],
        *,
        for_logging: bool = False,
    ) -> dict[str, int]:
        suffix = "_log" if for_logging else ""
        return {
            f"queue_count{suffix}": int(progress.get("queue_count", 0)),
            f"eligible_count{suffix}": int(progress.get("eligible_count", 0)),
            f"processed_count{suffix}": int(progress.get("processed_count", 0)),
            f"matched_count{suffix}": int(progress.get("matched_count", 0)),
            f"pending_count{suffix}": int(progress.get("remaining_count", 0)),
        }

    def _persist_progress(self, run: models.SyncRun, progress: dict[str, int]) -> None:
        run.google_queue_count = progress.get("queue_count", 0)
        run.google_eligible_count = progress.get("eligible_count", 0)
        run.google_matched_count = progress.get("matched_count", 0)
        run.google_pending_count = progress.get("remaining_count", 0)
        self._session.flush()

    def _update_run_google_counters(
        self,
        run: models.SyncRun,
        progress: dict[str, int],
    ) -> None:
        run.google_queue_count = progress.get("queue_count", 0)
        run.google_eligible_count = progress.get("eligible_count", 0)
        run.google_matched_count = progress.get("matched_count", 0)
        run.google_pending_count = progress.get("remaining_count", 0)
        run.google_api_call_count = self._api_call_count
        run.google_api_error_count = self._api_error_count

    def _log_enrichment_progress(
        self,
        run: models.SyncRun,
        progress: dict[str, int] | None,
    ) -> None:
        data = self._ensure_progress_defaults(progress)
        log_payload = self._format_progress_log(data, for_logging=True)
        log_event(
            "sync.google.enrichment.progress",
            run_id=str(run.id),
            scope_key=run.scope_key,
            api_call_count=self._api_call_count,
            api_error_count=self._api_error_count,
            **log_payload,
        )

    def _log_google_match(self, run: models.SyncRun, match: GoogleMatch) -> None:
        log_event(
            "sync.google.match",
            run_id=str(run.id),
            scope_key=run.scope_key,
            establishment=self._serialize_establishment(match.establishment),
            match=self._serialize_google_match(match),
        )

    def _log_result(self, run: models.SyncRun, results: GoogleEnrichmentResult) -> None:
        log_event(
            "sync.google.enrichment.summary",
            run_id=str(run.id),
            scope_key=run.scope_key,
            api_call_count=self._api_call_count,
            api_error_count=self._api_error_count,
            queue_count=results.queue_count,
            eligible_count=results.eligible_count,
            matched_count=results.matched_count,
            pending_count=results.remaining_count,
        )

    def _apply_results_to_run(
        self,
        run: models.SyncRun,
        results: GoogleEnrichmentResult,
    ) -> None:
        run.google_queue_count = results.queue_count
        run.google_eligible_count = results.eligible_count
        run.google_matched_count = results.matched_count
        run.google_pending_count = results.remaining_count
        run.google_api_call_count = self._api_call_count
        run.google_api_error_count = self._api_error_count

    def _mark_matches(self, run: models.SyncRun, matches: Sequence[models.Establishment]) -> None:
        immediate = 0
        late = 0
        for match in matches:
            if match.created_run_id == run.id:
                immediate += 1
            else:
                late += 1
        run.google_immediate_matched_count = immediate
        run.google_late_matched_count = late

    def _select_alert_targets(
        self,
        matches: Sequence[models.Establishment],
    ) -> list[models.Establishment]:
        return [
            item
            for item in matches
            if (item.google_check_status or "").lower() == "found"
        ]

    def _filter_candidates_for_manual_check(
        self,
        establishment: models.Establishment,
        candidates: list[models.Establishment],
    ) -> list[models.Establishment]:
        return [item for item in candidates if item.siret == establishment.siret]

    def _filter_retry_candidates(
        self,
        candidates: list[models.Establishment],
        *,
        now: datetime,
    ) -> list[models.Establishment]:
        eligible: list[models.Establishment] = []
        for item in candidates:
            if self._should_lookup(item, now, is_new=False, reset_google_state=False, recheck_all=False):
                eligible.append(item)
        return eligible

    def _log_google_state(self, establishment: models.Establishment) -> None:
        log_event(
            "sync.google.state",
            establishment=self._serialize_establishment(establishment),
            status=establishment.google_check_status,
            place_id=establishment.google_place_id,
            place_url=establishment.google_place_url,
            match_confidence=establishment.google_match_confidence,
            category_confidence=establishment.google_category_match_confidence,
            listing_age_status=establishment.google_listing_age_status,
            listing_origin_source=establishment.google_listing_origin_source,
        )

    def _refresh_google_run_counters(self, run: models.SyncRun) -> None:
        run.google_api_call_count = self._api_call_count
        run.google_api_error_count = self._api_error_count

    def _log_manual_check(self, run: models.SyncRun, establishment: models.Establishment, result: GoogleMatch | None) -> None:
        log_event(
            "sync.google.manual_check",
            run_id=str(run.id),
            scope_key=run.scope_key,
            establishment=self._serialize_establishment(establishment),
            result=self._serialize_google_match(result) if result else None,
        )

    def _log_candidates(self, run: models.SyncRun, candidates: Sequence[models.Establishment]) -> None:
        log_event(
            "sync.google.candidates",
            run_id=str(run.id),
            scope_key=run.scope_key,
            candidate_count=len(candidates),
        )

    def _log_skipped(self, run: models.SyncRun, reason: str) -> None:
        log_event(
            "sync.google.skipped",
            run_id=str(run.id),
            scope_key=run.scope_key,
            reason=reason,
        )

    def _log_retry_rule_applied(self, run: models.SyncRun, rule: dict[str, object]) -> None:
        log_event(
            "sync.google.retry_rule",
            run_id=str(run.id),
            scope_key=run.scope_key,
            rule=rule,
        )

    def _record_google_match(self, establishment: models.Establishment, match: GoogleMatch) -> None:
        log_event(
            "sync.google.match",
            establishment=self._serialize_establishment(establishment),
            match=self._serialize_google_match(match),
        )

    def _log_mismatch(self, establishment: models.Establishment, match: GoogleMatch) -> None:
        log_event(
            "sync.google.mismatch",
            establishment=self._serialize_establishment(establishment),
            match=self._serialize_google_match(match),
        )

    def _log_error(self, establishment: models.Establishment, error: Exception) -> None:
        log_event(
            "sync.google.error",
            establishment=self._serialize_establishment(establishment),
            error={"type": type(error).__name__, "message": str(error)},
        )

    def _log_retry_schedule(self, run: models.SyncRun, schedule: dict[str, object]) -> None:
        log_event(
            "sync.google.retry_schedule",
            run_id=str(run.id),
            scope_key=run.scope_key,
            schedule=schedule,
        )

    def _persist_last_run_date(self, run: models.SyncRun, date_value: date | None) -> None:
        if date_value is None:
            return
        run.last_google_run_date = date_value
        self._session.flush()

    def _log_debug(self, message: str, **kwargs: object) -> None:
        _LOGGER.debug(message, **kwargs)
