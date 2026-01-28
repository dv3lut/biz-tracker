"""Stripe integration helpers for public checkout and webhooks."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
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
from app.services.client_service import get_admin_emails
from app.services.stripe.stripe_settings_service import get_trial_period_days
from app.services.stripe.stripe_subscription_history import upsert_subscription_history

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
    stripe_config = _ensure_stripe_configured(settings)
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


def create_portal_session(session: Session, settings: Settings, email: str) -> str:
    stripe_config = _ensure_stripe_configured(settings)
    client = _find_client_by_email(session, email)
    if not client or not client.stripe_customer_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client Stripe introuvable.")

    stripe.api_key = stripe_config.secret_key
    portal_session = stripe.billing_portal.Session.create(
        customer=client.stripe_customer_id,
        return_url=stripe_config.portal_return_url,
        locale="fr",
    )

    if not portal_session.url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Impossible de créer la session du portail Stripe.",
        )

    log_event("stripe.portal.created", email=email.strip().lower())
    return portal_session.url


def update_subscription(session: Session, settings: Settings, payload: PublicStripeUpdateRequest) -> str | None:
    stripe_config = _ensure_stripe_configured(settings)
    plan = _resolve_plan_config(stripe_config, payload.plan_key)
    category_ids = _normalize_category_ids(payload.category_ids)
    _validate_category_selection(category_ids, plan.category_limit)
    _validate_categories_exist(session, category_ids)

    client = _find_client_by_email(session, payload.email)
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
        _apply_subscriptions_from_categories(session, client, category_ids)

    _apply_stripe_fields(client, settings, updated, updated.get("customer"), updated.get("id"), payload.plan_key)
    upsert_subscription_history(session, client=client, subscription=updated, settings=settings)

    if updated.get("cancel_at_period_end"):
        client.end_date = _resolve_end_date(updated)
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


def handle_stripe_webhook(session: Session, settings: Settings, event: stripe.Event) -> None:
    stripe_config = _ensure_stripe_configured(settings)
    stripe.api_key = stripe_config.secret_key

    event_type = event["type"]
    payload = event["data"]["object"]

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(session, settings, payload)
        _notify_admins_of_stripe_event(session, settings, event_type, payload)
        return

    if event_type == "customer.subscription.updated":
        _handle_subscription_updated(session, settings, payload)
        _notify_admins_of_stripe_event(session, settings, event_type, payload)
        return

    if event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(session, settings, payload)
        _notify_admins_of_stripe_event(session, settings, event_type, payload)
        return


def _ensure_stripe_configured(settings: Settings) -> StripeSettings:
    stripe_config = settings.stripe
    if not stripe_config.secret_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Stripe non configuré.")
    return stripe_config


def _resolve_plan_config(stripe_config: StripeSettings, plan_key: StripePlanKey) -> StripePlanConfig:
    price_id = stripe_config.price_ids.get(plan_key)
    if not price_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Plan Stripe non configuré.",
        )
    return StripePlanConfig(key=plan_key, price_id=price_id, category_limit=PLAN_CATEGORY_LIMITS[plan_key])


def _normalize_category_ids(category_ids: Iterable[UUID]) -> list[UUID]:
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


def _handle_checkout_completed(session: Session, settings: Settings, payload: dict) -> None:
    metadata = payload.get("metadata") or {}
    category_ids = _parse_category_ids(metadata.get("category_ids"))
    plan_key = metadata.get("plan_key")
    contact_name = (metadata.get("contact_name") or "").strip()
    company_name = (metadata.get("company_name") or "").strip()
    email = _resolve_email_from_payload(payload, metadata)

    customer_id = payload.get("customer")
    subscription_id = payload.get("subscription")
    subscription = _retrieve_subscription(settings, subscription_id)

    client = _find_client(session, customer_id=customer_id, subscription_id=subscription_id, email=email)
    if client is None:
        client = models.Client(
            name=_build_client_name(contact_name, company_name, email),
            start_date=_resolve_start_date(subscription),
            end_date=None,
        )
        session.add(client)

    if email:
        _ensure_recipient(client, email)

    if category_ids:
        _apply_subscriptions_from_categories(session, client, category_ids)

    _apply_stripe_fields(client, settings, subscription, customer_id, subscription_id, plan_key)
    upsert_subscription_history(
        session,
        client=client,
        subscription=subscription,
        settings=settings,
        purchased_at=_to_datetime(payload.get("created")),
    )

    session.flush()

    _send_post_purchase_email(settings, customer_id, email)

    log_event(
        "stripe.checkout.completed",
        client_id=str(client.id),
        email=email,
        subscription_id=subscription_id,
        plan_key=client.stripe_plan_key,
    )


def _send_post_purchase_email(settings: Settings, customer_id: str | None, email: str | None) -> None:
    if not email:
        return

    email_service = EmailService()
    if not email_service.is_enabled() or not email_service.is_configured():
        return

    upgrade_url = settings.stripe.upgrade_url
    portal_access_url = f"{upgrade_url}#portal" if upgrade_url else None
    portal_direct_url = None

    if customer_id and settings.stripe.secret_key:
        stripe.api_key = settings.stripe.secret_key
        try:
            portal_session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=settings.stripe.portal_return_url,
            )
            portal_direct_url = portal_session.url
        except stripe.error.StripeError:
            portal_direct_url = None

    lines = [
        "Bonjour,",
        "",
        "Votre abonnement Business Tracker est activé.",
        "",
        "Pour gérer votre abonnement :",
    ]
    if portal_direct_url:
        lines.append(f"- Portail Stripe : {portal_direct_url}")
    if portal_access_url:
        lines.append(f"- Page de gestion : {portal_access_url}")
    if not portal_direct_url and not portal_access_url:
        lines.append("- Connectez-vous au portail via la page Business Tracker.")

    lines.extend(
        [
            "",
            "Conservez cet email : il contient les liens utiles pour gérer votre abonnement.",
            "",
            "L'équipe Business Tracker",
        ]
    )

    html_body = _build_post_purchase_email_html(portal_direct_url, portal_access_url)

    email_service.send(
        subject="[Business Tracker] Votre abonnement est actif",
        body="\n".join(lines),
        html_body=html_body,
        recipients=[email],
    )


def _build_post_purchase_email_html(
    portal_direct_url: str | None,
    portal_access_url: str | None,
) -> str:
    primary_url = portal_direct_url or portal_access_url
    secondary_url = portal_access_url if portal_direct_url and portal_access_url else None
    button_label = "Accéder au portail" if portal_direct_url else "Gérer mon abonnement"

    lines = [
        "<div style=\"font-family:Arial,Helvetica,sans-serif;max-width:600px;margin:0 auto;color:#0f172a;\">",
        "<h1 style=\"font-size:22px;margin-bottom:8px;\">Votre abonnement est actif</h1>",
        "<p style=\"margin:0 0 16px;\">Bienvenue chez Business Tracker. Votre abonnement est bien activé.</p>",
    ]

    if primary_url:
        lines.extend(
            [
                "<div style=\"margin:24px 0;\">",
                f"<a href=\"{primary_url}\" style=\"background:#0f172a;color:#ffffff;text-decoration:none;padding:12px 20px;border-radius:8px;display:inline-block;\">{button_label}</a>",
                "</div>",
            ]
        )

    lines.append(
        "<p style=\"margin:0 0 8px;\">Vous pouvez y :</p>"
    )
    lines.append(
        "<ul style=\"margin:0 0 16px;padding-left:18px;\">"
        "<li>mettre à jour votre plan (proratisation immédiate)</li>"
        "<li>modifier vos catégories</li>"
        "<li>résilier en fin de période</li>"
        "</ul>"
    )

    if secondary_url:
        lines.append(
            f"<p style=\"margin:0 0 16px;\">Accès guidé : <a href=\"{secondary_url}\">{secondary_url}</a></p>"
        )

    lines.append(
        "<p style=\"margin:0 0 16px;\"><strong>Conservez cet email :</strong> il contient vos liens de gestion.</p>"
    )
    lines.append("<p style=\"margin:0;\">L'équipe Business Tracker</p>")
    lines.append("</div>")

    return "".join(lines)


def _handle_subscription_updated(session: Session, settings: Settings, payload: dict) -> None:
    subscription_id = payload.get("id")
    customer_id = payload.get("customer")
    metadata = payload.get("metadata") or {}
    category_ids = _parse_category_ids(metadata.get("category_ids"))

    client = _find_client(session, customer_id=customer_id, subscription_id=subscription_id, email=None)
    if client is None:
        return

    if category_ids:
        _apply_subscriptions_from_categories(session, client, category_ids)

    _apply_stripe_fields(client, settings, payload, customer_id, subscription_id, metadata.get("plan_key"))
    upsert_subscription_history(session, client=client, subscription=payload, settings=settings)

    if payload.get("cancel_at_period_end"):
        client.end_date = _resolve_end_date(payload)
    else:
        client.end_date = None

    session.flush()

    log_event(
        "stripe.subscription.updated",
        client_id=str(client.id),
        subscription_id=subscription_id,
        status=client.stripe_subscription_status,
        cancel_at_period_end=bool(payload.get("cancel_at_period_end")),
    )


def _handle_subscription_deleted(session: Session, settings: Settings, payload: dict) -> None:
    subscription_id = payload.get("id")
    customer_id = payload.get("customer")
    client = _find_client(session, customer_id=customer_id, subscription_id=subscription_id, email=None)
    if client is None:
        return

    _apply_stripe_fields(client, settings, payload, customer_id, subscription_id, None)
    upsert_subscription_history(session, client=client, subscription=payload, settings=settings)
    client.end_date = _resolve_end_date(payload)

    session.flush()

    log_event(
        "stripe.subscription.deleted",
        client_id=str(client.id),
        subscription_id=subscription_id,
        status=client.stripe_subscription_status,
    )


def _retrieve_subscription(settings: Settings, subscription_id: str | None) -> dict | None:
    if not subscription_id:
        return None
    stripe.api_key = settings.stripe.secret_key
    return stripe.Subscription.retrieve(subscription_id)


def _find_client(
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
        return _find_client_by_email(session, email)
    return None


def _find_client_by_email(session: Session, email: str) -> models.Client | None:
    normalized = email.strip().lower()
    stmt = (
        select(models.Client)
        .join(models.ClientRecipient)
        .where(func.lower(models.ClientRecipient.email) == normalized)
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none()


def _ensure_recipient(client: models.Client, email: str) -> None:
    normalized = email.strip().lower()
    existing = {recipient.email.lower() for recipient in client.recipients}
    if normalized in existing:
        return
    client.recipients.append(models.ClientRecipient(email=normalized))


def _apply_subscriptions_from_categories(
    session: Session,
    client: models.Client,
    category_ids: list[UUID],
) -> None:
    stmt = (
        select(models.NafSubCategory)
        .where(
            models.NafSubCategory.category_id.in_(category_ids),
            models.NafSubCategory.is_active.is_(True),
        )
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


def _apply_stripe_fields(
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
    client.stripe_current_period_end = _to_datetime(subscription.get("current_period_end"))
    client.stripe_cancel_at = _to_datetime(subscription.get("cancel_at"))

    price_id = _resolve_price_id(subscription)
    client.stripe_price_id = price_id
    if plan_key:
        client.stripe_plan_key = plan_key
    elif price_id:
        client.stripe_plan_key = _resolve_plan_key(settings, price_id)


def _resolve_price_id(subscription: dict) -> str | None:
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


def _build_client_name(contact_name: str, company_name: str, email: str | None) -> str:
    safe_contact = contact_name.strip() or "Contact"
    safe_company = company_name.strip() or "Entreprise"
    if email:
        return f"{safe_contact} / {safe_company}"
    return f"{safe_contact} / {safe_company}"


def _resolve_email_from_payload(payload: dict, metadata: dict) -> str | None:
    email = metadata.get("contact_email")
    if email:
        return str(email).strip().lower()
    customer_details = payload.get("customer_details") or {}
    email = customer_details.get("email") or payload.get("customer_email")
    if email:
        return str(email).strip().lower()
    return None


def _parse_category_ids(raw: str | None) -> list[UUID]:
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


def _resolve_start_date(subscription: dict | None) -> date:
    if not subscription:
        return date.today()
    timestamp = subscription.get("current_period_start") or subscription.get("start_date")
    dt = _to_datetime(timestamp)
    return dt.date() if dt else date.today()


def _resolve_end_date(subscription: dict | None) -> date | None:
    if not subscription:
        return None
    timestamp = subscription.get("ended_at") or subscription.get("current_period_end")
    dt = _to_datetime(timestamp)
    return dt.date() if dt else None


def _to_datetime(timestamp: int | float | None) -> datetime | None:
    if not timestamp:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(tzinfo=None)


def _notify_admins_of_stripe_event(
    session: Session,
    settings: Settings,
    event_type: str,
    payload: dict,
) -> None:
    email_service = EmailService()
    if not email_service.is_enabled() or not email_service.is_configured():
        return

    recipients = get_admin_emails(session)
    if not recipients:
        return

    subscription_id = payload.get("subscription") or payload.get("id")
    customer_id = payload.get("customer")
    client = _find_client(session, customer_id=customer_id, subscription_id=subscription_id, email=None)

    subscription = None
    if event_type == "checkout.session.completed":
        subscription = _retrieve_subscription(settings, subscription_id)
    elif payload.get("object") == "subscription":
        subscription = payload

    subject = f"[Stripe] Événement {event_type}"
    body = _format_stripe_event_summary(
        event_type=event_type,
        payload=payload,
        subscription=subscription,
        client=client,
    )

    email_service.send(subject=subject, body=body, recipients=recipients)


def _format_stripe_event_summary(
    *,
    event_type: str,
    payload: dict,
    subscription: dict | None,
    client: models.Client | None,
) -> str:
    email = _resolve_email_from_payload(payload, payload.get("metadata") or {})
    if not email and client:
        email = (client.recipients[0].email if client.recipients else None)

    lines = [
        "Événement Stripe détecté.",
        "",
        f"Type: {event_type}",
    ]

    if client:
        lines.append(f"Client: {client.name} ({client.id})")
    if email:
        lines.append(f"Email: {email}")

    subscription_id = payload.get("subscription") or payload.get("id")
    if subscription_id:
        lines.append(f"Subscription: {subscription_id}")
    if payload.get("customer"):
        lines.append(f"Customer: {payload.get('customer')}")

    if subscription:
        lines.append(f"Statut: {subscription.get('status')}")
        price_id = _resolve_price_id(subscription)
        if price_id:
            lines.append(f"Price: {price_id}")
        plan_key = subscription.get("metadata", {}).get("plan_key")
        if plan_key:
            lines.append(f"Plan: {plan_key}")
        trial_end = _to_datetime(subscription.get("trial_end"))
        current_period_end = _to_datetime(subscription.get("current_period_end"))
        cancel_at = _to_datetime(subscription.get("cancel_at"))
        if trial_end:
            lines.append(f"Fin d'essai: {trial_end:%Y-%m-%d %H:%M}")
        if current_period_end:
            lines.append(f"Fin de période: {current_period_end:%Y-%m-%d %H:%M}")
        if cancel_at:
            lines.append(f"Résiliation planifiée: {cancel_at:%Y-%m-%d %H:%M}")

    return "\n".join(lines)
