"""Schemas for LinkedIn-related endpoints."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LinkedInCheckResponse(BaseModel):
    """Response for a LinkedIn profile check on a single director."""

    model_config = ConfigDict(from_attributes=True)

    director_id: UUID
    first_names: str | None
    last_name: str | None
    quality: str | None
    company_name: str | None
    linkedin_profile_url: str | None
    linkedin_profile_data: dict | None
    linkedin_check_status: str
    linkedin_last_checked_at: datetime | None
    message: str


class LinkedInDebugResponse(BaseModel):
    """Detailed debug response for a LinkedIn profile search."""

    director_id: UUID
    director_name: str
    company_name: str
    search_input: dict
    apify_response: dict | None
    profile_url: str | None
    profile_data: dict | None
    status: str
    error: str | None
    retried_with_legal_unit: bool


__all__ = ["LinkedInCheckResponse", "LinkedInDebugResponse"]
