"""Schemas for public landing/contact endpoints."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


_PERSONAL_EMAIL_DOMAINS = {
    # Major consumer providers
    "gmail.com",
    "googlemail.com",
    "yahoo.com",
    "yahoo.fr",
    "ymail.com",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "msn.com",
    "aol.com",
    "icloud.com",
    "me.com",
    "mac.com",
    "proton.me",
    "protonmail.com",
    "gmx.com",
    "gmx.fr",
    "mail.com",
    "yandex.com",
    "yandex.ru",
    # Common personal ISP mail domains (FR)
    "orange.fr",
    "wanadoo.fr",
    "sfr.fr",
    "neuf.fr",
    "free.fr",
    "laposte.net",
    "bbox.fr",
    "aliceadsl.fr",
}


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

        domain_normalized = domain.lower().strip()
        if domain_normalized in _PERSONAL_EMAIL_DOMAINS:
            raise ValueError("email professionnel requis")
        return normalized


class PublicContactResponse(BaseModel):
    accepted: bool = True
