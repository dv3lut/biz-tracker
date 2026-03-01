"""LinkedIn enrichment service package."""
from __future__ import annotations

from app.services.linkedin.linkedin_lookup_service import (
    LinkedInEnrichmentResult,
    LinkedInLookupService,
)

__all__ = [
    "LinkedInEnrichmentResult",
    "LinkedInLookupService",
]
