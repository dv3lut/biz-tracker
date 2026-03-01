"""Admin endpoints for Stripe billing settings."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.api.schemas import (
    AdminStripeSettingsOut,
    AdminStripeSettingsUpdate,
    AdminStripeSettingsUpdateResponse,
)
from app.config import get_settings
from app.services.stripe.stripe_settings_service import (
    apply_trial_period_to_existing_trials,
    get_billing_settings,
    update_trial_period_days,
)

router = APIRouter(tags=["admin"])


@router.get("/stripe/settings", response_model=AdminStripeSettingsOut, summary="Lire la configuration Stripe")
def get_stripe_settings(session: Session = Depends(get_db_session)) -> AdminStripeSettingsOut:
    settings = get_billing_settings(session)
    return AdminStripeSettingsOut(trial_period_days=settings.trial_period_days)


@router.put(
    "/stripe/settings",
    response_model=AdminStripeSettingsUpdateResponse,
    summary="Mettre à jour la configuration Stripe",
)
def update_stripe_settings(
    payload: AdminStripeSettingsUpdate,
    session: Session = Depends(get_db_session),
) -> AdminStripeSettingsUpdateResponse:
    settings = update_trial_period_days(session, payload.trial_period_days)
    updated_trials = 0
    failed_trials = 0

    if payload.apply_to_existing_trials:
        updated_trials, failed_trials = apply_trial_period_to_existing_trials(
            session,
            get_settings(),
            payload.trial_period_days,
        )

    return AdminStripeSettingsUpdateResponse(
        trial_period_days=settings.trial_period_days,
        updated_trials=updated_trials,
        failed_trials=failed_trials,
    )