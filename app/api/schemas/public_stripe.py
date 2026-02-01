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


class PublicStripePortalSessionRequest(BaseModel):
    access_token: str = Field(min_length=10, max_length=2048)


class PublicStripePortalSessionResponse(BaseModel):
    url: str


class PublicStripeSubscriptionInfoRequest(BaseModel):
    access_token: str = Field(min_length=10, max_length=2048)


class PublicStripeSubscriptionCategoryOut(BaseModel):
    id: UUID
    name: str


class PublicStripeSubscriptionInfoResponse(BaseModel):
    plan_key: str | None = None
    status: str | None = None
    current_period_end: datetime | None = None
    cancel_at: datetime | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    categories: list[PublicStripeSubscriptionCategoryOut] = Field(default_factory=list)


class PublicStripeUpdateRequest(BaseModel):
    plan_key: StripePlanKey
    category_ids: list[UUID] = Field(default_factory=list)
    access_token: str = Field(min_length=10, max_length=2048)


class PublicStripeUpdateResponse(BaseModel):
    payment_url: str | None = None
    action: Literal["upgrade", "downgrade", "update"]
    effective_at: datetime | None = None


class PublicStripeUpdatePreviewRequest(BaseModel):
    plan_key: StripePlanKey
    category_ids: list[UUID] = Field(default_factory=list)
    access_token: str = Field(min_length=10, max_length=2048)


class PublicStripeUpdatePreviewResponse(BaseModel):
    amount_due: int | None = None
    currency: str | None = None
    is_upgrade: bool
    is_trial: bool
    has_payment_method: bool


__all__ = [
    "PublicStripeCheckoutRequest",
    "PublicStripeCheckoutResponse",
    "PublicStripePortalRequest",
    "PublicStripePortalResponse",
    "PublicStripePortalSessionRequest",
    "PublicStripePortalSessionResponse",
    "PublicStripeSubscriptionInfoRequest",
    "PublicStripeSubscriptionCategoryOut",
    "PublicStripeSubscriptionInfoResponse",
    "PublicStripeUpdateRequest",
    "PublicStripeUpdateResponse",
    "PublicStripeUpdatePreviewRequest",
    "PublicStripeUpdatePreviewResponse",
    "StripePlanKey",
]
