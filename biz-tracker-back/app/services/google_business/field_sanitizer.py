"""Shared guards for bounded VARCHAR fields written by Google enrichment/scraping."""
from __future__ import annotations

MAX_PLACE_ID_LENGTH = 128
MAX_PHONE_LENGTH = 64
MAX_EMAIL_LENGTH = 255
MAX_URL_LENGTH = 512
MAX_SCRAPED_CONTACT_VALUE_LENGTH = 512


def clamp_optional_varchar(value: str | None, max_length: int) -> str | None:
    """Return a trimmed string capped to *max_length*, or ``None``.

    This helper prevents DB ``VARCHAR`` overflow on external/untrusted payloads.
    """

    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) <= max_length:
        return cleaned
    return cleaned[:max_length]
