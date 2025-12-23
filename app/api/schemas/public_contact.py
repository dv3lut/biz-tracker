"""Schemas for public landing/contact endpoints."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class PublicContactRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    company: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=50)
    message: str | None = Field(default=None, max_length=5000)

    # Honeypot anti-spam field: should remain empty.
    website: str | None = Field(default=None, max_length=500)

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_and_validate_email(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("email invalide")
        normalized = value.strip()
        if not normalized:
            raise ValueError("email requis")
        # Minimal validation to avoid extra dependency (email-validator).
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):  # noqa: PLR2004
            raise ValueError("email invalide")
        local, _, domain = normalized.partition("@")
        if not local or not domain or "." not in domain:
            raise ValueError("email invalide")
        return normalized


class PublicContactResponse(BaseModel):
    accepted: bool = True
