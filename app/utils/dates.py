"""Utility helpers for parsing ISO formatted dates and computing ranges."""
from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timezone
from typing import Optional


def parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        try:
            return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            return None


def subtract_months(reference: date, months: int) -> date:
    """Return the date obtained by subtracting ``months`` from ``reference``.

    The day component is clamped to the last day of the target month when necessary
    (e.g. 31 March -> 30 September when subtracting 6 months).
    """

    if months <= 0:
        return reference

    year = reference.year
    month = reference.month - months

    while month <= 0:
        month += 12
        year -= 1

    day = min(reference.day, monthrange(year, month)[1])
    return date(year, month, day)


def utcnow() -> datetime:
    """Return a naive UTC timestamp without relying on the deprecated ``utcnow``."""

    return datetime.now(timezone.utc).replace(tzinfo=None)
