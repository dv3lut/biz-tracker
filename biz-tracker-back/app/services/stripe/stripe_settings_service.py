"""Stripe billing settings persisted in database."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

import stripe
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import models
from app.observability import log_event
from app.services.stripe.stripe_subscription_history import upsert_subscription_history

DEFAULT_TRIAL_PERIOD_DAYS = 14


def get_billing_settings(session: Session) -> models.StripeBillingSettings:
    settings = session.execute(select(models.StripeBillingSettings)).scalar_one_or_none()
    if settings is None:
        settings = models.StripeBillingSettings(trial_period_days=DEFAULT_TRIAL_PERIOD_DAYS)
        session.add(settings)
        session.flush()
    return settings


def get_trial_period_days(session: Session) -> int:
    settings = get_billing_settings(session)
    return settings.trial_period_days


def update_trial_period_days(session: Session, trial_period_days: int) -> models.StripeBillingSettings:
    settings = get_billing_settings(session)
    settings.trial_period_days = trial_period_days
    session.flush()
    return settings


def apply_trial_period_to_existing_trials(
    session: Session,
    app_settings: Settings,
    trial_period_days: int,
) -> tuple[int, int]:
    stripe.api_key = app_settings.stripe.secret_key
    now_ts = int(datetime.now(timezone.utc).timestamp())
    target_trial_end = now_ts + int(trial_period_days) * 24 * 3600

    stmt = select(models.Client).where(
        models.Client.stripe_subscription_status == "trialing",
        models.Client.stripe_subscription_id.is_not(None),
    )
    clients = session.execute(stmt).scalars().all()

    updated = 0
    failed = 0
    for client in clients:
        try:
            subscription = stripe.Subscription.modify(
                client.stripe_subscription_id,
                trial_end=target_trial_end,
                proration_behavior="none",
            )
            _apply_trial_subscription_update(client, subscription, app_settings)
            upsert_subscription_history(session, client=client, subscription=subscription, settings=app_settings)
            updated += 1
        except stripe.error.StripeError:
            failed += 1
            continue

    session.flush()
    log_event(
        "stripe.trial_period.updated",
        updated=updated,
        failed=failed,
        trial_period_days=trial_period_days,
    )
    return updated, failed


def _apply_trial_subscription_update(
    client: models.Client,
    subscription: dict,
    app_settings: Settings,
) -> None:
    client.stripe_subscription_status = subscription.get("status")
    client.stripe_current_period_end = _to_datetime(subscription.get("current_period_end"))
    client.stripe_cancel_at = _to_datetime(subscription.get("cancel_at"))

    price_id = _resolve_price_id(subscription)
    if price_id:
        client.stripe_price_id = price_id
        client.stripe_plan_key = _resolve_plan_key(app_settings, price_id)


def _resolve_price_id(subscription: dict) -> str | None:
    items = subscription.get("items", {}).get("data", [])
    if not items:
        return None
    price = items[0].get("price")
    if isinstance(price, dict):
        return price.get("id")
    return None


def _resolve_plan_key(app_settings: Settings, price_id: str) -> str | None:
    for key, value in app_settings.stripe.price_ids.items():
        if value == price_id:
            return key
    return None


def _to_datetime(timestamp: int | float | None) -> datetime | None:
    if not timestamp:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(tzinfo=None)
