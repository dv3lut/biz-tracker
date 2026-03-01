"""Helpers to interpret Google listing age statuses."""
from __future__ import annotations

from typing import Final, Sequence

LISTING_AGE_STATUS_LABELS: Final[dict[str, str]] = {
    "recent_creation": "Création récente",
    "recent_creation_missing_contact": "Création récente (contact manquant)",
    "not_recent_creation": "Création ancienne",
    "unknown": "Non déterminé",
}

FILTERABLE_LISTING_STATUSES: Final[tuple[str, ...]] = (
    "recent_creation",
    "recent_creation_missing_contact",
    "not_recent_creation",
)


def default_listing_statuses() -> list[str]:
    """Return the default ordered list of selectable listing statuses."""

    return list(FILTERABLE_LISTING_STATUSES)


def normalize_listing_status_filters(values: Sequence[str] | None) -> list[str]:
    """Validate and normalize listing status filters preserving display order."""

    if values is None:
        return default_listing_statuses()
    seen: set[str] = set()
    normalized: list[str] = []
    for value in values:
        token = (value or "").strip().lower()
        if token not in FILTERABLE_LISTING_STATUSES:
            raise ValueError(f"Statut de fiche Google inconnu: {value!r}")
        if token in seen:
            continue
        seen.add(token)
    for token in FILTERABLE_LISTING_STATUSES:
        if token in seen:
            normalized.append(token)
    return normalized


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
