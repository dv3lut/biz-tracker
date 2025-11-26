from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.db import models


@dataclass
class GoogleMatch:
    establishment: models.Establishment
    place_id: str
    place_url: str | None
    confidence: float
    category_confidence: float | None
    listing_origin_at: datetime | None
    listing_origin_source: str
    listing_age_status: str
    status_override: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    contact_website: str | None = None


@dataclass
class GoogleEnrichmentResult:
    matches: list[models.Establishment]
    queue_count: int
    eligible_count: int
    matched_count: int
    remaining_count: int
    api_call_count: int
