"""Listing metadata helpers for Google Places entries."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

from app.utils.google_listing import normalize_listing_age_status

_RECENT_REVIEW_THRESHOLD_DAYS = 14


def iter_period_dates(periods: list[object]) -> Iterable[datetime | None]:
    for period in periods:
        if not isinstance(period, dict):
            continue
        open_info = period.get("open")
        if not isinstance(open_info, dict):
            continue
        token = open_info.get("date")
        yield parse_google_period_date(token)


def parse_google_period_date(token: object) -> datetime | None:
    if not isinstance(token, str) or len(token) != 8 or not token.isdigit():
        return None
    try:
        parsed = datetime.strptime(token, "%Y%m%d")
    except ValueError:
        return None
    return parsed


def collect_review_dates(details: dict[str, object]) -> list[datetime]:
    reviews = details.get("reviews")
    review_dates: list[datetime] = []
    if isinstance(reviews, list):
        for review in reviews:
            if not isinstance(review, dict):
                continue
            timestamp = review.get("time")
            if isinstance(timestamp, (int, float)):
                dt = datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(tzinfo=None)
                review_dates.append(dt)
    review_dates.sort()
    return review_dates


def extract_ratings_total(details: dict[str, object]) -> int | None:
    value = details.get("user_ratings_total")
    if isinstance(value, (int, float)):
        return int(value)
    return None


def should_assume_recent_listing(details: dict[str, object]) -> bool:
    reviews = details.get("reviews")
    reviews_info_missing = reviews is None
    if isinstance(reviews, list):
        reviews_info_missing = False
        if len(reviews) == 0:
            return True
    ratings_total = details.get("user_ratings_total")
    if isinstance(ratings_total, (int, float)):
        return ratings_total <= 0
    if reviews_info_missing and ratings_total is None:
        return True
    return False


def compute_listing_age_status(
    review_dates: list[datetime],
    *,
    ratings_total: int | None,
    assumed_recent: bool,
    now: datetime,
) -> str:
    if review_dates:
        oldest = min(review_dates)
        if now - oldest <= timedelta(days=_RECENT_REVIEW_THRESHOLD_DAYS):
            return normalize_listing_age_status("recent_creation")
        return normalize_listing_age_status("not_recent_creation")
    if assumed_recent:
        return normalize_listing_age_status("recent_creation")
    if ratings_total is None:
        return normalize_listing_age_status("unknown")
    if ratings_total <= 0:
        return normalize_listing_age_status("recent_creation")
    return normalize_listing_age_status("not_recent_creation")


def extract_listing_origin(details: dict[str, object]) -> tuple[datetime | None, str, bool, list[datetime]]:
    origin_candidates: list[tuple[datetime, str]] = []
    for key in ("current_opening_hours", "opening_hours"):
        hours = details.get(key)
        if not isinstance(hours, dict):
            continue
        periods = hours.get("periods")
        if not isinstance(periods, list):
            continue
        for date_value in iter_period_dates(periods):
            if date_value:
                origin_candidates.append((date_value, "opening_period"))

    review_dates = collect_review_dates(details)
    if origin_candidates:
        origin_candidates.sort(key=lambda item: item[0])
        best = origin_candidates[0]
        return best[0], best[1], False, review_dates

    if review_dates:
        return review_dates[0], "review", False, review_dates

    if should_assume_recent_listing(details):
        return None, "assumed_recent", True, review_dates

    return None, "unknown", False, review_dates


__all__ = [
    "collect_review_dates",
    "compute_listing_age_status",
    "extract_listing_origin",
    "extract_ratings_total",
    "iter_period_dates",
    "parse_google_period_date",
    "should_assume_recent_listing",
]
