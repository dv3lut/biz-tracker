"""Helpers for classifying establishments by legal/company categories."""
from __future__ import annotations

from typing import Iterable

_MICRO_COMPANY_CATEGORY = "ME"
_INDIVIDUAL_LEGAL_PREFIXES: tuple[str, ...] = ("1",)


def normalize_legal_category(value: str | None) -> str:
    """Return the legal category without leading zeros (empty string if missing)."""

    if not value:
        return ""
    trimmed = value.strip()
    if not trimmed:
        return ""
    normalized = trimmed.lstrip("0")
    return normalized or trimmed


def is_individual_company(legal_category: str | None) -> bool:
    """Detect entreprise individuelle / entrepreneurs individuels based on legal category."""

    normalized = normalize_legal_category(legal_category)
    if not normalized:
        return False
    return normalized.startswith(_INDIVIDUAL_LEGAL_PREFIXES)


def is_micro_company(company_category: str | None, legal_category: str | None) -> bool:
    """Detect micro / auto-entreprises using both company and legal categories."""

    if (company_category or "").strip().upper() == _MICRO_COMPANY_CATEGORY:
        return True
    return is_individual_company(legal_category)


def normalize_place_types(values: Iterable[str] | None) -> set[str]:
    """Normalize Google place types to lowercase tokens."""

    result: set[str] = set()
    if not values:
        return result
    for value in values:
        if not value:
            continue
        token = value.strip().lower()
        if token:
            result.add(token)
    return result
