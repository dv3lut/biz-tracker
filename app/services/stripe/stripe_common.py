"""Shared helpers for Stripe services."""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, StripeSettings
from app.db import models


def ensure_stripe_configured(settings: Settings) -> StripeSettings:
    stripe_config = settings.stripe
    if not stripe_config.secret_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Stripe non configuré.")
    return stripe_config


def find_client_by_email(session: Session, email: str) -> models.Client | None:
    normalized = email.strip().lower()
    stmt = (
        select(models.Client)
        .join(models.ClientRecipient)
        .where(func.lower(models.ClientRecipient.email) == normalized)
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none()
