"""Stripe checkout and subscription update helpers."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
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
from app.services.email_service import EmailService
from app.services.stripe.stripe_common import ensure_stripe_configured, find_client_by_email
from app.services.stripe.stripe_settings_service import get_trial_period_days
from app.services.stripe.stripe_subscription_history import upsert_subscription_history
from app.services.stripe.stripe_subscription_utils import (
    apply_stripe_fields,
    apply_subscriptions_from_categories,
    parse_category_ids,
    resolve_end_date,
    to_datetime,
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


@dataclass(frozen=True)
class StripeSubscriptionUpdateResult:
    payment_url: str | None
    action: str
    effective_at: datetime | None


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


def update_subscription(
    session: Session,
    settings: Settings,
    payload: PublicStripeUpdateRequest,
) -> StripeSubscriptionUpdateResult:
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

    current_price_id = (items[0].get("price") or {}).get("id")
    current_amount = _get_price_amount(current_price_id)
    target_amount = _get_price_amount(plan.price_id)
    is_upgrade = _is_upgrade(current_amount=current_amount, target_amount=target_amount)

    current_metadata = subscription.get("metadata") or {}
    current_plan_key = current_metadata.get("plan_key") or getattr(client, "stripe_plan_key", None) or payload.plan_key
    current_category_ids = parse_category_ids(current_metadata.get("category_ids"))
    if not current_category_ids:
        current_category_ids = category_ids

    metadata = {
        "plan_key": payload.plan_key,
        "category_ids": json.dumps([str(identifier) for identifier in category_ids]),
    }
    effective_at = None
    if not is_upgrade:
        pending_effective_at = subscription.get("current_period_end")
        metadata = {
            "plan_key": current_plan_key,
            "category_ids": json.dumps([str(identifier) for identifier in current_category_ids]),
            "pending_plan_key": payload.plan_key,
            "pending_category_ids": json.dumps([str(identifier) for identifier in category_ids]),
        }
        if pending_effective_at:
            metadata["pending_effective_at"] = str(pending_effective_at)
            effective_at = to_datetime(pending_effective_at)

    updated = stripe.Subscription.modify(
        client.stripe_subscription_id,
        items=[{"id": items[0].get("id"), "price": plan.price_id}],
        proration_behavior="always_invoice" if is_upgrade else "none",
        metadata=metadata,
        expand=["latest_invoice"],
    )

    if category_ids and is_upgrade:
        apply_subscriptions_from_categories(session, client, category_ids)

    plan_key_for_apply = payload.plan_key if is_upgrade else current_plan_key
    apply_stripe_fields(client, settings, updated, updated.get("customer"), updated.get("id"), plan_key_for_apply)
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

    _send_subscription_update_email(
        settings=settings,
        email=payload.email,
        action="upgrade" if is_upgrade else "downgrade",
        effective_at=effective_at,
        payment_url=payment_url,
    )

    return StripeSubscriptionUpdateResult(
        payment_url=payment_url,
        action="upgrade" if is_upgrade else "downgrade",
        effective_at=effective_at,
    )


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


def _get_price_amount(price_id: str | None) -> Decimal | None:
    if not price_id:
        return None
    price = stripe.Price.retrieve(price_id)
    unit_amount = price.get("unit_amount")
    if unit_amount is not None:
        return Decimal(unit_amount)
    unit_amount_decimal = price.get("unit_amount_decimal")
    if unit_amount_decimal is None:
        return None
    try:
        return Decimal(str(unit_amount_decimal))
    except (InvalidOperation, TypeError):
        return None


def _send_subscription_update_email(
    *,
    settings: Settings,
    email: str,
    action: str,
    effective_at: datetime | None,
    payment_url: str | None,
) -> None:
    email_service = EmailService()
    if not email_service.is_enabled() or not email_service.is_configured():
        return

    safe_email = email.strip().lower()
    if not safe_email:
        return

    upgrade_url = settings.stripe.upgrade_url
    subject = "[Business Tracker] Mise à jour de votre abonnement"

    if action == "downgrade":
        effective_label = (
            effective_at.strftime("%d/%m/%Y") if isinstance(effective_at, datetime) else "la prochaine période"
        )
        lines = [
            "Bonjour,",
            "",
            "Votre demande de changement de plan a bien été prise en compte.",
            "",
            f"Le downgrade prendra effet le {effective_label}.",
            "Aucun remboursement n'est appliqué sur la période en cours : vous conservez donc votre plan actuel jusqu'à la prochaine facturation.",
        ]
        if upgrade_url:
            lines.append("")
            lines.append(f"Gérer mon abonnement : {upgrade_url}")
    else:
        lines = [
            "Bonjour,",
            "",
            "Votre changement de plan est effectif immédiatement.",
            "La différence de prix sera facturée au prorata de l'avancement dans le mois.",
        ]
        if payment_url:
            lines.append("")
            lines.append(f"Finaliser le paiement : {payment_url}")
        if upgrade_url:
            lines.append("")
            lines.append(f"Gérer mon abonnement : {upgrade_url}")

    html_lines = [
        "<div style=\"font-family:Arial,Helvetica,sans-serif;max-width:600px;margin:0 auto;color:#0f172a;\">",
        "<h1 style=\"font-size:20px;margin-bottom:12px;\">Mise à jour de votre abonnement</h1>",
    ]
    if action == "downgrade":
        effective_label = (
            effective_at.strftime("%d/%m/%Y") if isinstance(effective_at, datetime) else "la prochaine période"
        )
        html_lines.append(
            f"<p>Le downgrade prendra effet <strong>{effective_label}</strong>. Vous conservez votre plan actuel jusqu'à cette date.</p>"
        )
        html_lines.append("<p>Aucun remboursement n'est appliqué sur la période en cours.</p>")
    else:
        html_lines.append("<p>Votre changement de plan est <strong>effectif immédiatement</strong>.</p>")
        html_lines.append(
            "<p>La différence de prix sera facturée au prorata de l'avancement dans le mois.</p>"
        )
        if payment_url:
            html_lines.append(f"<p><a href=\"{payment_url}\">Finaliser le paiement</a></p>")
    if upgrade_url:
        html_lines.append(f"<p><a href=\"{upgrade_url}\">Gérer mon abonnement</a></p>")
    html_lines.append("</div>")

    email_service.send(
        subject=subject,
        body="\n".join(lines),
        html_body="".join(html_lines),
        recipients=[safe_email],
    )


def _is_upgrade(*, current_amount: Decimal | None, target_amount: Decimal | None) -> bool:
    if current_amount is None or target_amount is None:
        return True
    return target_amount > current_amount
