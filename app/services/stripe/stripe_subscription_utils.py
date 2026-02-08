"""Helpers for Stripe subscription persistence."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from uuid import UUID

import stripe
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import models
from app.services.stripe.stripe_common import find_client_by_email


def retrieve_subscription(settings: Settings, subscription_id: str | None) -> dict | None:
    if not subscription_id:
        return None
    stripe.api_key = settings.stripe.secret_key
    return stripe.Subscription.retrieve(subscription_id)


def find_client(
    session: Session,
    *,
    customer_id: str | None,
    subscription_id: str | None,
    email: str | None,
) -> models.Client | None:
    if subscription_id:
        stmt = select(models.Client).where(models.Client.stripe_subscription_id == subscription_id)
        client = session.execute(stmt).scalar_one_or_none()
        if client:
            return client
    if customer_id:
        stmt = select(models.Client).where(models.Client.stripe_customer_id == customer_id)
        client = session.execute(stmt).scalar_one_or_none()
        if client:
            return client
    if email:
        return find_client_by_email(session, email)
    return None


def ensure_recipient(client: models.Client, email: str) -> None:
    normalized = email.strip().lower()
    existing = {recipient.email.lower() for recipient in client.recipients}
    if normalized in existing:
        return
    client.recipients.append(models.ClientRecipient(email=normalized))


def apply_subscriptions_from_categories(
    session: Session,
    client: models.Client,
    category_ids: list[UUID],
) -> None:
    stmt = (
        select(models.NafSubCategory)
        .join(
            models.NafCategorySubCategory,
            models.NafCategorySubCategory.subcategory_id == models.NafSubCategory.id,
        )
        .where(
            models.NafCategorySubCategory.category_id.in_(category_ids),
            models.NafSubCategory.is_active.is_(True),
        )
        .distinct(models.NafSubCategory.id)
        .order_by(models.NafSubCategory.naf_code)
    )
    subcategories = session.execute(stmt).scalars().all()
    updated: list[models.ClientSubscription] = []
    current = {sub.subcategory_id: sub for sub in client.subscriptions}
    for subcategory in subcategories:
        existing = current.get(subcategory.id)
        if existing is not None:
            updated.append(existing)
        else:
            updated.append(models.ClientSubscription(subcategory_id=subcategory.id, subcategory=subcategory))
    client.subscriptions = updated


def apply_stripe_fields(
    client: models.Client,
    settings: Settings,
    subscription: dict | None,
    customer_id: str | None,
    subscription_id: str | None,
    plan_key: str | None,
) -> None:
    client.stripe_customer_id = customer_id or client.stripe_customer_id
    client.stripe_subscription_id = subscription_id or client.stripe_subscription_id

    if subscription is None:
        return

    client.stripe_subscription_status = subscription.get("status")
    client.stripe_current_period_end = to_datetime(subscription.get("current_period_end"))
    client.stripe_cancel_at = to_datetime(subscription.get("cancel_at"))

    price_id = resolve_price_id(subscription)
    client.stripe_price_id = price_id
    if plan_key:
        client.stripe_plan_key = plan_key
    elif price_id:
        client.stripe_plan_key = resolve_plan_key(settings, price_id)


def resolve_price_id(subscription: dict) -> str | None:
    items = subscription.get("items", {}).get("data", [])
    if not items:
        return None
    price = items[0].get("price")
    if isinstance(price, dict):
        return price.get("id")
    return None


def resolve_plan_key(settings: Settings, price_id: str) -> str | None:
    for key, value in settings.stripe.price_ids.items():
        if value == price_id:
            return key
    return None


def build_client_name(contact_name: str, company_name: str, email: str | None) -> str:
    safe_contact = contact_name.strip() or "Contact"
    safe_company = company_name.strip() or "Entreprise"
    if email:
        return f"{safe_contact} / {safe_company}"
    return f"{safe_contact} / {safe_company}"


def resolve_email_from_payload(payload: dict, metadata: dict) -> str | None:
    email = metadata.get("contact_email")
    if email:
        return str(email).strip().lower()
    customer_details = payload.get("customer_details") or {}
    email = customer_details.get("email") or payload.get("customer_email")
    if email:
        return str(email).strip().lower()
    return None


def parse_category_ids(raw: str | None) -> list[UUID]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    ids: list[UUID] = []
    for item in data:
        try:
            ids.append(UUID(str(item)))
        except ValueError:
            continue
    return ids


def resolve_start_date(subscription: dict | None) -> date:
    if not subscription:
        return date.today()
    timestamp = subscription.get("current_period_start") or subscription.get("start_date")
    dt = to_datetime(timestamp)
    return dt.date() if dt else date.today()


def resolve_end_date(subscription: dict | None) -> date | None:
    if not subscription:
        return None
    timestamp = subscription.get("ended_at") or subscription.get("current_period_end") or subscription.get("cancel_at")
    dt = to_datetime(timestamp)
    return dt.date() if dt else None


def to_datetime(timestamp: int | float | None) -> datetime | None:
    if not timestamp:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(tzinfo=None)
