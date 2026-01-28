"""Schemas pour la configuration Stripe (admin & public)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class AdminStripeSettingsOut(BaseModel):
    trial_period_days: int


class AdminStripeSettingsUpdate(BaseModel):
    trial_period_days: int = Field(ge=0, le=60)
    apply_to_existing_trials: bool = False


class AdminStripeSettingsUpdateResponse(BaseModel):
    trial_period_days: int
    updated_trials: int = 0
    failed_trials: int = 0


class PublicStripeSettingsOut(BaseModel):
    trial_period_days: int


__all__ = [
    "AdminStripeSettingsOut",
    "AdminStripeSettingsUpdate",
    "AdminStripeSettingsUpdateResponse",
    "PublicStripeSettingsOut",
]
