"""Stripe checkout and subscription update helpers."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable
from uuid import UUID

import stripe
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas import (
    PublicNafCategoryOut,
    PublicStripeCheckoutRequest,
    PublicStripeUpdateRequest,
    StripePlanKey,
)
from app.config import Settings, StripeSettings
from app.db import models
from app.observability import log_event
from app.services.stripe.stripe_common import ensure_stripe_configured, find_client_by_email
from app.services.stripe.stripe_settings_service import get_trial_period_days
from app.services.stripe.stripe_subscription_history import upsert_subscription_history
from app.services.stripe.stripe_subscription_utils import (
    apply_stripe_fields,
    apply_subscriptions_from_categories,
    resolve_end_date,
)

PLAN_CATEGORY_LIMITS: dict[StripePlanKey, int] = {
    "starter": 1,
    "business": 3,
}


@dataclass(frozen=True)
class StripePlanConfig:
    key: StripePlanKey
    price_id: str
    category_limit: int


def list_public_categories(session: Session) -> list[PublicNafCategoryOut]:
    stmt = (
        select(
            models.NafCategory,
            func.count(models.NafSubCategory.id).label("active_subcategory_count"),
        )
        .join(models.NafSubCategory)
        .where(models.NafSubCategory.is_active.is_(True))
        .group_by(models.NafCategory.id)
        .order_by(models.NafCategory.name)
    )
    rows = session.execute(stmt).all()
    return [
        PublicNafCategoryOut(
            id=category.id,
            name=category.name,
            description=category.description,
            active_subcategory_count=int(active_count),
        )
        for category, active_count in rows
    ]


def create_checkout_session(
    session: Session,
    settings: Settings,
    payload: PublicStripeCheckoutRequest,
) -> str:
    stripe_config = ensure_stripe_configured(settings)
    plan = _resolve_plan_config(stripe_config, payload.plan_key)
    category_ids = _normalize_category_ids(payload.category_ids)
    _validate_category_selection(category_ids, plan.category_limit)
    _validate_categories_exist(session, category_ids)

    metadata = {
        "plan_key": payload.plan_key,
        "category_ids": json.dumps([str(identifier) for identifier in category_ids]),
        "contact_name": payload.contact_name.strip(),
        "company_name": payload.company_name.strip(),
        "contact_email": payload.email.strip(),
    }
    referrer_name = (payload.referrer_name or "").strip()
    if referrer_name:
        metadata["referrer_name"] = referrer_name

    stripe.api_key = stripe_config.secret_key
    trial_period_days = get_trial_period_days(session)
    stripe_session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": plan.price_id, "quantity": 1}],
        customer_email=payload.email.strip(),
        success_url=stripe_config.success_url,
        cancel_url=stripe_config.cancel_url,
        locale="fr",
        subscription_data={
            "trial_period_days": trial_period_days,
            "metadata": metadata,
        },
        metadata=metadata,
    )

    if not stripe_session.url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Impossible de créer la session Stripe.",
        )

    log_event(
        "stripe.checkout.created",
        plan_key=payload.plan_key,
        category_count=len(category_ids),
        email=payload.email.strip().lower(),
    )

    return stripe_session.url


def update_subscription(session: Session, settings: Settings, payload: PublicStripeUpdateRequest) -> str | None:
    stripe_config = ensure_stripe_configured(settings)
    plan = _resolve_plan_config(stripe_config, payload.plan_key)
    category_ids = _normalize_category_ids(payload.category_ids)
    _validate_category_selection(category_ids, plan.category_limit)
    _validate_categories_exist(session, category_ids)

    client = find_client_by_email(session, payload.email)
    if not client or not client.stripe_subscription_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Abonnement Stripe introuvable.")

    stripe.api_key = stripe_config.secret_key
    subscription = stripe.Subscription.retrieve(client.stripe_subscription_id)
    items = subscription.get("items", {}).get("data", [])
    if not items:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Abonnement Stripe invalide.")

    metadata = {
        "plan_key": payload.plan_key,
        "category_ids": json.dumps([str(identifier) for identifier in category_ids]),
    }

    updated = stripe.Subscription.modify(
        client.stripe_subscription_id,
        items=[{"id": items[0].get("id"), "price": plan.price_id}],
        proration_behavior="always_invoice",
        metadata=metadata,
        expand=["latest_invoice"],
    )

    if category_ids:
        apply_subscriptions_from_categories(session, client, category_ids)

    apply_stripe_fields(client, settings, updated, updated.get("customer"), updated.get("id"), payload.plan_key)
    upsert_subscription_history(session, client=client, subscription=updated, settings=settings)

    if updated.get("cancel_at_period_end"):
        client.end_date = resolve_end_date(updated)
    else:
        client.end_date = None

    session.flush()

    latest_invoice = updated.get("latest_invoice")
    payment_url = None
    if isinstance(latest_invoice, dict):
        payment_url = latest_invoice.get("hosted_invoice_url") or latest_invoice.get("invoice_pdf")

    log_event(
        "stripe.subscription.updated.custom",
        client_id=str(client.id),
        subscription_id=client.stripe_subscription_id,
        plan_key=payload.plan_key,
    )

    return payment_url


def _resolve_plan_config(stripe_config: StripeSettings, plan_key: StripePlanKey) -> StripePlanConfig:
    price_id = stripe_config.price_ids.get(plan_key)
    if not price_id:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Stripe non configuré.")
    category_limit = PLAN_CATEGORY_LIMITS.get(plan_key)
    if category_limit is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Configuration Stripe invalide.",
        )
    return StripePlanConfig(key=plan_key, price_id=price_id, category_limit=category_limit)


def _normalize_category_ids(category_ids: Iterable[UUID] | None) -> list[UUID]:
    if not category_ids:
        return []
    unique: list[UUID] = []
    seen: set[UUID] = set()
    for identifier in category_ids:
        if identifier in seen:
            continue
        seen.add(identifier)
        unique.append(identifier)
    return unique


def _validate_category_selection(category_ids: list[UUID], limit: int) -> None:
    if len(category_ids) != limit:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Sélectionnez exactement {limit} catégorie(s).",
        )


def _validate_categories_exist(session: Session, category_ids: list[UUID]) -> None:
    if not category_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Aucune catégorie sélectionnée.")
    stmt = (
        select(models.NafCategory.id)
        .join(models.NafSubCategory)
        .where(
            models.NafCategory.id.in_(category_ids),
            models.NafSubCategory.is_active.is_(True),
        )
        .group_by(models.NafCategory.id)
    )
    found = set(session.execute(stmt).scalars().all())
    missing = [str(identifier) for identifier in category_ids if identifier not in found]
    if missing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catégorie introuvable ou inactive.")
