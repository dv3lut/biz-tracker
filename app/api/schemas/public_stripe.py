"""Schemas publics pour Stripe (checkout + portal)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


StripePlanKey = Literal["starter", "business"]


class PublicStripeCheckoutRequest(BaseModel):
    plan_key: StripePlanKey
    category_ids: list[UUID] = Field(default_factory=list)
    contact_name: str = Field(min_length=1, max_length=200)
    company_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    referrer_name: str | None = Field(default=None, max_length=200)


class PublicStripeCheckoutResponse(BaseModel):
    url: str


class PublicStripePortalRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class PublicStripePortalResponse(BaseModel):
    sent: bool


class PublicStripeUpdateRequest(BaseModel):
    plan_key: StripePlanKey
    category_ids: list[UUID] = Field(default_factory=list)
    email: str = Field(min_length=3, max_length=320)


class PublicStripeUpdateResponse(BaseModel):
    payment_url: str | None = None
    action: Literal["upgrade", "downgrade"]
    effective_at: datetime | None = None


__all__ = [
    "PublicStripeCheckoutRequest",
    "PublicStripeCheckoutResponse",
    "PublicStripePortalRequest",
    "PublicStripePortalResponse",
    "PublicStripeUpdateRequest",
    "PublicStripeUpdateResponse",
    "StripePlanKey",
]
