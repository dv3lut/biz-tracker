"""Stripe checkout and subscription update helpers."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
from app.services.stripe.stripe_common import ensure_stripe_configured
from app.services.stripe.stripe_settings_service import get_trial_period_days
from app.services.stripe.stripe_subscription_history import upsert_subscription_history
from app.services.stripe.stripe_subscription_events import record_subscription_event
from app.services.stripe.stripe_subscription_utils import (
    apply_stripe_fields,
    apply_subscriptions_from_categories,
    find_client,
    parse_category_ids,
    retrieve_subscription,
    resolve_plan_key,
    resolve_end_date,
    to_datetime,
)
from app.services.stripe.stripe_upgrade_tokens import build_upgrade_url, parse_upgrade_token

PLAN_CATEGORY_LIMITS: dict[StripePlanKey, int] = {
    "starter": 1,
    "business": 5,
}
PLAN_RANKS: dict[StripePlanKey, int] = {
    "starter": 0,
    "business": 1,
}
STRIPE_TIMEOUT_SECONDS = 20


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


@dataclass(frozen=True)
class StripeSubscriptionInfo:
    plan_key: str | None
    status: str | None
    current_period_end: datetime | None
    cancel_at: datetime | None
    contact_name: str | None
    contact_email: str | None
    categories: list[dict[str, object]]


@dataclass(frozen=True)
class StripeSubscriptionUpdatePreview:
    amount_due: int | None
    currency: str | None
    is_upgrade: bool
    is_trial: bool
    has_payment_method: bool


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
    _ensure_stripe_http_client()
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


def get_subscription_update_preview(
    session: Session,
    settings: Settings,
    payload: PublicStripeUpdateRequest,
) -> StripeSubscriptionUpdatePreview:
    stripe_config = ensure_stripe_configured(settings)
    access = parse_upgrade_token(settings, payload.access_token)
    plan = _resolve_plan_config(stripe_config, payload.plan_key)
    category_ids = _normalize_category_ids(payload.category_ids)
    _validate_category_selection(category_ids, plan.category_limit)
    _validate_categories_exist(session, category_ids)

    client = find_client(
        session,
        customer_id=access.customer_id,
        subscription_id=access.subscription_id,
        email=access.email,
    )
    if not client or not client.stripe_subscription_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Abonnement Stripe introuvable.")

    stripe.api_key = stripe_config.secret_key
    _ensure_stripe_http_client()
    subscription = stripe.Subscription.retrieve(client.stripe_subscription_id)
    items = subscription.get("items", {}).get("data", [])
    if not items:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Abonnement Stripe invalide.")

    current_metadata = subscription.get("metadata") or {}
    current_price_id = (items[0].get("price") or {}).get("id")
    current_amount = _get_price_amount(current_price_id)
    target_amount = _get_price_amount(plan.price_id)
    is_plan_change = current_price_id != plan.price_id
    is_upgrade = _is_upgrade(current_amount=current_amount, target_amount=target_amount) if is_plan_change else False
    current_plan_key = current_metadata.get("plan_key") or resolve_plan_key(settings, current_price_id)
    pending_plan_key = current_metadata.get("pending_plan_key")
    is_canceling_pending_downgrade = (
        bool(pending_plan_key)
        and pending_plan_key != payload.plan_key
        and current_plan_key == payload.plan_key
        and current_price_id == plan.price_id
    )

    trial_end = to_datetime(subscription.get("trial_end"))
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    is_trial_active = trial_end is not None and trial_end > now_utc

    # Vérifier si un moyen de paiement est disponible
    has_payment_method = False
    if client.stripe_customer_id:
        customer = stripe.Customer.retrieve(client.stripe_customer_id)
        invoice_settings = customer.get("invoice_settings") or {}
        default_payment_method = (
            subscription.get("default_payment_method")
            or invoice_settings.get("default_payment_method")
        )
        has_payment_method = bool(default_payment_method)

    if is_canceling_pending_downgrade:
        return StripeSubscriptionUpdatePreview(
            amount_due=0,
            currency=(subscription.get("currency") or None),
            is_upgrade=False,
            is_trial=False,
            has_payment_method=has_payment_method,
        )

    if not is_plan_change or not is_upgrade or is_trial_active:
        return StripeSubscriptionUpdatePreview(
            amount_due=0,
            currency=(subscription.get("currency") or None),
            is_upgrade=is_upgrade and is_plan_change,
            is_trial=is_trial_active,
            has_payment_method=has_payment_method,
        )

    upcoming = stripe.Invoice.upcoming(
        customer=client.stripe_customer_id,
        subscription=client.stripe_subscription_id,
        subscription_items=[{"id": items[0].get("id"), "price": plan.price_id}],
        subscription_proration_behavior="create_prorations",
        subscription_proration_date=int(datetime.now(timezone.utc).timestamp()),
    )
    # Calculer uniquement le montant du prorata (pas la facture périodique complète)
    proration_amount = 0
    for line in upcoming.get("lines", {}).get("data", []):
        if line.get("proration"):
            proration_amount += line.get("amount", 0)
    currency = upcoming.get("currency")
    return StripeSubscriptionUpdatePreview(
        amount_due=proration_amount if proration_amount >= 0 else 0,
        currency=currency if isinstance(currency, str) else None,
        is_upgrade=True,
        is_trial=False,
        has_payment_method=has_payment_method,
    )


def update_subscription(
    session: Session,
    settings: Settings,
    payload: PublicStripeUpdateRequest,
) -> StripeSubscriptionUpdateResult:
    import logging
    _logger = logging.getLogger(__name__)
    stripe_config = ensure_stripe_configured(settings)
    access = parse_upgrade_token(settings, payload.access_token)
    _logger.info(
        "stripe.update: start access customer=%s subscription=%s plan=%s",
        access.customer_id,
        access.subscription_id,
        payload.plan_key,
    )
    plan = _resolve_plan_config(stripe_config, payload.plan_key)
    category_ids = _normalize_category_ids(payload.category_ids)
    _validate_category_selection(category_ids, plan.category_limit)
    _validate_categories_exist(session, category_ids)

    client = find_client(
        session,
        customer_id=access.customer_id,
        subscription_id=access.subscription_id,
        email=access.email,
    )
    if not client or not client.stripe_subscription_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Abonnement Stripe introuvable.")

    stripe.api_key = stripe_config.secret_key
    _ensure_stripe_http_client()
    subscription = stripe.Subscription.retrieve(client.stripe_subscription_id)
    items = subscription.get("items", {}).get("data", [])
    if not items:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Abonnement Stripe invalide.")

    current_metadata = subscription.get("metadata") or {}
    trial_end = to_datetime(subscription.get("trial_end"))
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    is_trial_active = trial_end is not None and trial_end > now_utc
    current_price_id = (items[0].get("price") or {}).get("id")
    inferred_plan_key = resolve_plan_key(settings, current_price_id) if current_price_id else None
    current_plan_key = (
        current_metadata.get("plan_key")
        or getattr(client, "stripe_plan_key", None)
        or inferred_plan_key
        or payload.plan_key
    )
    _logger.info(
        "stripe.update: current price_id=%s inferred_plan=%s metadata_plan=%s client_plan=%s",
        current_price_id,
        inferred_plan_key,
        current_metadata.get("plan_key"),
        getattr(client, "stripe_plan_key", None),
    )
    current_amount = _get_price_amount(current_price_id)
    target_amount = _get_price_amount(plan.price_id)
    pending_plan_key = current_metadata.get("pending_plan_key")
    is_canceling_pending_downgrade = (
        bool(pending_plan_key)
        and pending_plan_key != payload.plan_key
        and current_plan_key == payload.plan_key
        and current_price_id == plan.price_id
    )
    is_plan_change = (current_price_id != plan.price_id) or (current_plan_key != payload.plan_key)
    if is_canceling_pending_downgrade:
        is_plan_change = False
    if is_plan_change:
        if current_amount is not None and target_amount is not None:
            is_upgrade = _is_upgrade(current_amount=current_amount, target_amount=target_amount)
        else:
            is_upgrade = _is_upgrade_by_plan_key(current_plan_key, payload.plan_key)
    else:
        is_upgrade = True
    _logger.info(
        "stripe.update: target price_id=%s is_plan_change=%s is_upgrade=%s",
        plan.price_id,
        is_plan_change,
        is_upgrade,
    )
    current_category_ids = parse_category_ids(current_metadata.get("category_ids"))
    if not current_category_ids:
        current_category_ids = category_ids

    is_category_change = set(category_ids) != set(current_category_ids)
    last_update_raw = current_metadata.get("last_category_update_at")
    last_update = None
    if last_update_raw:
        try:
            last_update = datetime.fromtimestamp(float(last_update_raw), tz=timezone.utc).replace(tzinfo=None)
        except (TypeError, ValueError):
            last_update = None
    if not is_plan_change and payload.plan_key == current_plan_key and is_category_change and last_update:
        if datetime.now(timezone.utc).replace(tzinfo=None) - last_update < timedelta(days=30):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Vous ne pouvez changer de catégories qu'une fois par mois.",
            )

    metadata = {
        "plan_key": payload.plan_key,
        "category_ids": json.dumps([str(identifier) for identifier in category_ids]),
    }
    if is_category_change:
        metadata["last_category_update_at"] = str(datetime.now(timezone.utc).timestamp())
    effective_at = None
    if is_plan_change and not is_upgrade:
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
        _logger.info(
            "stripe.update: downgrade pending_plan=%s pending_effective_at=%s",
            payload.plan_key,
            metadata.get("pending_effective_at"),
        )

    modify_payload = {
        # always_invoice crée et finalise une facture immédiate pour le prorata
        "proration_behavior": (
            "none" if is_trial_active else "always_invoice"
        )
        if is_upgrade and is_plan_change
        else "none",
        "metadata": metadata,
    }
    if is_plan_change and is_upgrade and not is_trial_active:
        modify_payload["expand"] = ["latest_invoice"]
    if is_plan_change:
        modify_payload["items"] = [{"id": items[0].get("id"), "price": plan.price_id}]

    updated = stripe.Subscription.modify(
        client.stripe_subscription_id,
        **modify_payload,
    )
    latest_invoice = updated.get("latest_invoice")
    invoice_id = None
    invoice_status = None
    if isinstance(latest_invoice, dict):
        invoice_id = latest_invoice.get("id")
        invoice_status = latest_invoice.get("status")
    elif isinstance(latest_invoice, str):
        invoice_id = latest_invoice
    _logger.info(
        "stripe.update: stripe.modify done latest_invoice_id=%s latest_invoice_status=%s cancel_at_period_end=%s",
        invoice_id,
        invoice_status,
        updated.get("cancel_at_period_end"),
    )

    if category_ids and (is_upgrade or not is_plan_change):
        apply_subscriptions_from_categories(session, client, category_ids)

    plan_key_for_apply = payload.plan_key if is_upgrade or not is_plan_change else current_plan_key
    apply_stripe_fields(client, settings, updated, updated.get("customer"), updated.get("id"), plan_key_for_apply)
    _logger.info(
        "stripe.update: apply_stripe_fields plan_key_for_apply=%s client_plan_after=%s",
        plan_key_for_apply,
        getattr(client, "stripe_plan_key", None),
    )
    event_type = None
    if is_plan_change:
        event_type = "upgrade" if is_upgrade else "downgrade_requested"
    elif is_category_change:
        event_type = "categories_updated"
    if event_type:
        record_subscription_event(
            session,
            client=client,
            stripe_subscription_id=client.stripe_subscription_id,
            event_type=event_type,
            from_plan_key=current_plan_key,
            to_plan_key=payload.plan_key if is_plan_change else current_plan_key,
            from_category_ids=[str(identifier) for identifier in current_category_ids],
            to_category_ids=[str(identifier) for identifier in category_ids],
            effective_at=effective_at,
            source="api",
        )
    upsert_subscription_history(session, client=client, subscription=updated, settings=settings)

    if updated.get("cancel_at_period_end"):
        client.end_date = resolve_end_date(updated)
    else:
        client.end_date = None

    session.flush()

    latest_invoice_status = None
    payment_url = None
    if is_plan_change and is_upgrade:
        updated_trial_end = to_datetime(updated.get("trial_end"))
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        is_trial_active = is_trial_active or (
            updated_trial_end is not None and updated_trial_end > now_utc
        )
        if not is_trial_active:
            # Récupérer l'invoice générée automatiquement par Stripe lors du modify
            latest_invoice = updated.get("latest_invoice")
            if isinstance(latest_invoice, str):
                latest_invoice = stripe.Invoice.retrieve(latest_invoice)
            
            if latest_invoice and latest_invoice.get("status") == "open":
                # L'invoice existe et est ouverte, essayer de la payer
                customer = stripe.Customer.retrieve(client.stripe_customer_id)
                invoice_settings = customer.get("invoice_settings") or {}
                default_payment_method = (
                    updated.get("default_payment_method")
                    or subscription.get("default_payment_method")
                    or invoice_settings.get("default_payment_method")
                )
                
                if not default_payment_method:
                    # Pas de moyen de paiement : retourner l'URL de paiement de l'invoice
                    payment_url = latest_invoice.get("hosted_invoice_url")
                    latest_invoice_status = latest_invoice.get("status")
                    # Marquer la subscription pour envoyer l'email après paiement
                    pending_metadata = dict(updated.get("metadata") or metadata)
                    pending_metadata["pending_upgrade_email"] = "1"
                    stripe.Subscription.modify(
                        client.stripe_subscription_id,
                        metadata=pending_metadata,
                    )
                else:
                    try:
                        paid_invoice = stripe.Invoice.pay(
                            latest_invoice.get("id"),
                            payment_method=default_payment_method,
                        )
                        latest_invoice_status = paid_invoice.get("status")
                    except stripe.error.CardError as exc:
                        raise HTTPException(
                            status_code=status.HTTP_402_PAYMENT_REQUIRED,
                            detail="Le paiement de l'upgrade a été refusé. Merci de vérifier votre moyen de paiement.",
                        ) from exc
                    except stripe.error.StripeError as exc:
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail="Impossible de finaliser le paiement Stripe pour l'upgrade.",
                        ) from exc
                    if latest_invoice_status not in {"paid", "closed"}:
                        raise HTTPException(
                            status_code=status.HTTP_402_PAYMENT_REQUIRED,
                            detail="Le paiement de l'upgrade n'a pas pu être confirmé.",
                        )
            elif latest_invoice and latest_invoice.get("status") == "paid":
                # Déjà payé (pas de prorata ou montant nul)
                latest_invoice_status = "paid"

    log_event(
        "stripe.subscription.updated.custom",
        client_id=str(client.id),
        subscription_id=client.stripe_subscription_id,
        plan_key=payload.plan_key,
    )

    action = "upgrade" if is_upgrade and is_plan_change else "downgrade" if is_plan_change else "update"

    # Ne pas envoyer l'email si upgrade avec paiement en attente (sera envoyé après paiement via webhook)
    is_upgrade_payment_pending = action == "upgrade" and payment_url and latest_invoice_status not in {"paid", "void"}
    if not is_upgrade_payment_pending:
        _send_subscription_update_email(
            settings=settings,
            email=_resolve_recipient_email(client, access.email),
            action=action,
            effective_at=effective_at,
            payment_url=payment_url,
            access_token=payload.access_token,
        )

    return StripeSubscriptionUpdateResult(
        payment_url=payment_url,
        action=action,
        effective_at=effective_at,
    )


def get_subscription_info(
    session: Session,
    settings: Settings,
    access_token: str,
) -> StripeSubscriptionInfo:
    access = parse_upgrade_token(settings, access_token)
    client = find_client(
        session,
        customer_id=access.customer_id,
        subscription_id=access.subscription_id,
        email=access.email,
    )
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Abonnement Stripe introuvable.")

    categories: list[dict[str, object]] = []
    seen: set[str] = set()
    for subscription in client.subscriptions:
        category = getattr(subscription.subcategory, "category", None)
        if not category or not category.id:
            continue
        category_id = str(category.id)
        if category_id in seen:
            continue
        seen.add(category_id)
        categories.append({"id": category.id, "name": category.name})

    categories.sort(key=lambda entry: str(entry.get("name") or ""))

    current_period_end = client.stripe_current_period_end
    cancel_at = client.stripe_cancel_at
    contact_email = (access.email or "").strip() or None
    contact_name = None
    should_fetch_subscription = (
        not current_period_end
        or not cancel_at
        or not contact_name
        or not contact_email
    )
    subscription = None
    if should_fetch_subscription and client.stripe_subscription_id:
        subscription = retrieve_subscription(settings, client.stripe_subscription_id)
        if subscription:
            current_period_end = current_period_end or to_datetime(subscription.get("current_period_end"))
            cancel_at = cancel_at or to_datetime(subscription.get("cancel_at"))
            metadata = subscription.get("metadata") or {}
            contact_name = contact_name or (metadata.get("contact_name") or "").strip() or None
            contact_email = contact_email or (metadata.get("contact_email") or "").strip() or None

    return StripeSubscriptionInfo(
        plan_key=client.stripe_plan_key,
        status=client.stripe_subscription_status,
        current_period_end=current_period_end,
        cancel_at=cancel_at,
        contact_name=contact_name,
        contact_email=contact_email,
        categories=categories,
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


def _ensure_stripe_http_client() -> None:
    current_client = stripe.default_http_client
    current_timeout = getattr(current_client, "_timeout", None) if current_client else None
    if current_client is None or current_timeout != STRIPE_TIMEOUT_SECONDS:
        stripe.default_http_client = stripe.new_default_http_client(
            timeout=STRIPE_TIMEOUT_SECONDS,
        )


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
    email: str | None,
    action: str,
    effective_at: datetime | None,
    payment_url: str | None,
    access_token: str | None,
) -> None:
    email_service = EmailService()
    if not email_service.is_enabled() or not email_service.is_configured():
        return

    if not email:
        return
    safe_email = email.strip().lower()
    if not safe_email:
        return

    upgrade_url = build_upgrade_url(settings, access_token)
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
            "Le passage au plan inférieur se fera automatiquement à cette date.",
        ]
        if upgrade_url:
            lines.append("")
            lines.append(f"Gérer mon abonnement : {upgrade_url}")
    elif action == "upgrade":
        lines = [
            "Bonjour,",
            "",
            "Votre changement de plan est effectif immédiatement.",
        ]
        if upgrade_url:
            lines.append("")
            lines.append(f"Gérer mon abonnement : {upgrade_url}")
    else:
        lines = [
            "Bonjour,",
            "",
            "Vos catégories ont été mises à jour.",
        ]
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
            f"<p>Le downgrade prendra effet le <strong>{effective_label}</strong>. Vous conservez votre plan actuel jusqu'à cette date.</p>"
        )
        html_lines.append("<p>Aucun remboursement n'est appliqué sur la période en cours.</p>")
        html_lines.append("<p>Le passage au plan inférieur se fera automatiquement à cette date.</p>")
    elif action == "upgrade":
        html_lines.append("<p>Votre changement de plan est <strong>effectif immédiatement</strong>.</p>")
    else:
        html_lines.append("<p>Vos catégories ont été mises à jour.</p>")
    if upgrade_url:
        html_lines.append(f"<p><a href=\"{upgrade_url}\">Gérer mon abonnement</a></p>")
    html_lines.append("</div>")

    email_service.send(
        subject=subject,
        body="\n".join(lines),
        html_body="".join(html_lines),
        recipients=[safe_email],
    )


def _resolve_recipient_email(client: models.Client, fallback: str | None) -> str | None:
    if fallback:
        safe_fallback = fallback.strip().lower()
        if safe_fallback:
            return safe_fallback
    recipients = getattr(client, "recipients", None) or []
    for recipient in recipients:
        email = getattr(recipient, "email", None)
        if email:
            safe_email = str(email).strip().lower()
            if safe_email:
                return safe_email
    return None


def _is_upgrade(*, current_amount: Decimal | None, target_amount: Decimal | None) -> bool:
    if current_amount is None or target_amount is None:
        return True
    return target_amount > current_amount


def _is_upgrade_by_plan_key(current_plan_key: StripePlanKey | None, target_plan_key: StripePlanKey) -> bool:
    if not current_plan_key:
        return True
    return PLAN_RANKS.get(target_plan_key, 0) > PLAN_RANKS.get(current_plan_key, 0)
