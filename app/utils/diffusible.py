"""Helpers for detecting non-diffusible (ND) names from Sirene data."""
from __future__ import annotations

import re

# Patterns indicating a non-diffusible entity
_ND_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\[ND\]", re.IGNORECASE),
    re.compile(r"NON\s+DIFFUSIBLE", re.IGNORECASE),
)


def is_non_diffusible(value: str | None) -> bool:
    """Return True if value contains a non-diffusible marker ([ND] or NON DIFFUSIBLE).

    Args:
        value: The string to check (name, first_names, last_name, etc.).

    Returns:
        True if the value is marked as non-diffusible.
    """
    if not value:
        return False
    for pattern in _ND_PATTERNS:
        if pattern.search(value):
            return True
    return False


def any_name_non_diffusible(*names: str | None) -> bool:
    """Return True if any of the provided names is non-diffusible.

    Args:
        *names: Variable number of name strings to check.

    Returns:
        True if at least one name is marked as non-diffusible.
    """
    return any(is_non_diffusible(name) for name in names)


__all__ = ["any_name_non_diffusible", "is_non_diffusible"]
