"""Helpers to persist Stripe subscription history for clients."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import models


def upsert_subscription_history(
    session: Session,
    *,
    client: models.Client,
    subscription: dict[str, Any] | None,
    settings: Settings,
    purchased_at: datetime | None = None,
) -> models.ClientStripeSubscription | None:
    if not subscription:
        return None

    subscription_id = subscription.get("id")
    if not subscription_id:
        return None

    record = session.execute(
        select(models.ClientStripeSubscription).where(
            models.ClientStripeSubscription.stripe_subscription_id == subscription_id
        )
    ).scalar_one_or_none()

    if record is None:
        record = models.ClientStripeSubscription(
            client_id=client.id,
            stripe_subscription_id=str(subscription_id),
        )
        session.add(record)

    record.client_id = client.id
    record.stripe_customer_id = subscription.get("customer") or record.stripe_customer_id
    record.status = subscription.get("status") or record.status

    price_id = _resolve_price_id(subscription)
    record.price_id = price_id or record.price_id
    plan_key = subscription.get("metadata", {}).get("plan_key")
    record.plan_key = plan_key or record.plan_key
    referrer_name = subscription.get("metadata", {}).get("referrer_name")
    if isinstance(referrer_name, str) and referrer_name.strip():
        record.referrer_name = referrer_name.strip()
    if not record.plan_key and price_id:
        record.plan_key = _resolve_plan_key(settings, price_id)

    record.purchased_at = _prefer_earlier(record.purchased_at, purchased_at or _to_datetime(subscription.get("created")))
    record.trial_start_at = _prefer_earlier(record.trial_start_at, _to_datetime(subscription.get("trial_start")))
    record.trial_end_at = _to_datetime(subscription.get("trial_end")) or record.trial_end_at
    record.current_period_start = _to_datetime(subscription.get("current_period_start")) or record.current_period_start
    record.current_period_end = _to_datetime(subscription.get("current_period_end")) or record.current_period_end
    record.cancel_at = _to_datetime(subscription.get("cancel_at")) or record.cancel_at
    record.canceled_at = _to_datetime(subscription.get("canceled_at")) or record.canceled_at
    record.ended_at = _to_datetime(subscription.get("ended_at")) or record.ended_at

    paid_start = _resolve_paid_start_at(subscription)
    record.paid_start_at = paid_start or record.paid_start_at

    session.flush()
    return record


def _resolve_paid_start_at(subscription: dict[str, Any]) -> datetime | None:
    trial_end = _to_datetime(subscription.get("trial_end"))
    if trial_end:
        return trial_end
    return _to_datetime(subscription.get("current_period_start"))


def _resolve_price_id(subscription: dict[str, Any]) -> str | None:
    items = subscription.get("items", {}).get("data", [])
    if not items:
        return None
    price = items[0].get("price")
    if isinstance(price, dict):
        return price.get("id")
    return None


def _resolve_plan_key(settings: Settings, price_id: str) -> str | None:
    for key, value in settings.stripe.price_ids.items():
        if value == price_id:
            return key
    return None


def _to_datetime(timestamp: int | float | None) -> datetime | None:
    if not timestamp:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(tzinfo=None)


def _prefer_earlier(current: datetime | None, candidate: datetime | None) -> datetime | None:
    if not candidate:
        return current
    if not current:
        return candidate
    return candidate if candidate < current else current
