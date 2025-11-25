"""Helpers to interpret Google listing age statuses."""
from __future__ import annotations

from typing import Final

LISTING_AGE_STATUS_LABELS: Final[dict[str, str]] = {
    "recent_creation": "Création récente",
    "not_recent_creation": "Création ancienne",
    "unknown": "Non déterminé",
}


def normalize_listing_age_status(value: str | None) -> str:
    """Return a sanitized status token recognized by the UI."""

    if not value:
        return "unknown"
    token = value.strip().lower()
    if token == "buyback_suspected":
        # Conserve la compatibilité avec les anciennes données persistées.
        return "not_recent_creation"
    return token if token in LISTING_AGE_STATUS_LABELS else "unknown"


def describe_listing_age_status(value: str | None) -> str:
    """Return a user-facing label for a listing age status."""

    normalized = normalize_listing_age_status(value)
    return LISTING_AGE_STATUS_LABELS.get(normalized, LISTING_AGE_STATUS_LABELS["unknown"])
