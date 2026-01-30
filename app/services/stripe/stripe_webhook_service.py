"""Stripe webhook handling."""
from __future__ import annotations

from sqlalchemy.orm import Session
import stripe

from app.config import Settings
from app.db import models
from app.observability import log_event
from app.services.email_service import EmailService
from app.services.stripe.stripe_admin_notifications import notify_admins_of_stripe_event
from app.services.stripe.stripe_common import ensure_stripe_configured
from app.services.stripe.stripe_subscription_history import upsert_subscription_history
from app.services.stripe.stripe_subscription_utils import (
    apply_stripe_fields,
    apply_subscriptions_from_categories,
    build_client_name,
    ensure_recipient,
    find_client,
    parse_category_ids,
    resolve_email_from_payload,
    resolve_end_date,
    resolve_start_date,
    retrieve_subscription,
    to_datetime,
)


def handle_stripe_webhook(session: Session, settings: Settings, event: stripe.Event) -> None:
    stripe_config = ensure_stripe_configured(settings)
    stripe.api_key = stripe_config.secret_key
    event_type = event["type"]
    payload = event["data"]["object"]

    log_event(
        "stripe.webhook.received",
        event_type=event_type,
        payload=_summarize_webhook_payload(payload),
    )

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(session, settings, payload)
        notify_admins_of_stripe_event(session, settings, event_type, payload)
        return

    if event_type == "customer.subscription.updated":
        should_notify = _handle_subscription_updated(session, settings, payload)
        if should_notify:
            notify_admins_of_stripe_event(session, settings, event_type, payload)
        return

    if event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(session, settings, payload)
        notify_admins_of_stripe_event(session, settings, event_type, payload)
        return


def _handle_checkout_completed(session: Session, settings: Settings, payload: dict) -> None:
    metadata = payload.get("metadata") or {}
    category_ids = parse_category_ids(metadata.get("category_ids"))
    plan_key = metadata.get("plan_key")
    contact_name = (metadata.get("contact_name") or "").strip()
    company_name = (metadata.get("company_name") or "").strip()
    email = resolve_email_from_payload(payload, metadata)

    customer_id = payload.get("customer")
    subscription_id = payload.get("subscription")
    subscription = retrieve_subscription(settings, subscription_id)

    client = find_client(session, customer_id=customer_id, subscription_id=subscription_id, email=email)
    if client is None:
        client = models.Client(
            name=build_client_name(contact_name, company_name, email),
            start_date=resolve_start_date(subscription),
            end_date=None,
        )
        session.add(client)
        session.flush()

    if email:
        ensure_recipient(client, email)

    if category_ids:
        apply_subscriptions_from_categories(session, client, category_ids)

    apply_stripe_fields(client, settings, subscription, customer_id, subscription_id, plan_key)
    upsert_subscription_history(
        session,
        client=client,
        subscription=subscription,
        settings=settings,
        purchased_at=to_datetime(payload.get("created")),
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

    lines.append("<p style=\"margin:0 0 8px;\">Vous pouvez y :</p>")
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


def _handle_subscription_updated(session: Session, settings: Settings, payload: dict) -> bool:
    subscription_id = payload.get("id")
    customer_id = payload.get("customer")
    metadata = payload.get("metadata") or {}
    category_ids = parse_category_ids(metadata.get("category_ids"))

    client = find_client(session, customer_id=customer_id, subscription_id=subscription_id, email=None)
    if client is None:
        return False

    previous_cancel_at = client.stripe_cancel_at

    if category_ids:
        apply_subscriptions_from_categories(session, client, category_ids)

    apply_stripe_fields(client, settings, payload, customer_id, subscription_id, metadata.get("plan_key"))
    upsert_subscription_history(session, client=client, subscription=payload, settings=settings)

    if payload.get("cancel_at_period_end"):
        client.end_date = resolve_end_date(payload)
    else:
        client.end_date = None

    session.flush()

    new_cancel_at = client.stripe_cancel_at
    notify = True
    if payload.get("cancel_at_period_end"):
        if previous_cancel_at and new_cancel_at and previous_cancel_at == new_cancel_at:
            notify = False

    log_event(
        "stripe.subscription.updated",
        client_id=str(client.id),
        subscription_id=subscription_id,
        status=client.stripe_subscription_status,
        cancel_at_period_end=bool(payload.get("cancel_at_period_end")),
    )

    return notify


def _handle_subscription_deleted(session: Session, settings: Settings, payload: dict) -> None:
    subscription_id = payload.get("id")
    customer_id = payload.get("customer")
    client = find_client(session, customer_id=customer_id, subscription_id=subscription_id, email=None)
    if client is None:
        return

    apply_stripe_fields(client, settings, payload, customer_id, subscription_id, None)
    upsert_subscription_history(session, client=client, subscription=payload, settings=settings)
    client.end_date = resolve_end_date(payload)

    session.flush()

    log_event(
        "stripe.subscription.deleted",
        client_id=str(client.id),
        subscription_id=subscription_id,
        status=client.stripe_subscription_status,
    )


def _summarize_webhook_payload(payload: dict) -> dict[str, object]:
    metadata = payload.get("metadata") if isinstance(payload, dict) else None
    if not isinstance(metadata, dict):
        metadata = {}
    return {
        "id": payload.get("id"),
        "object": payload.get("object"),
        "status": payload.get("status"),
        "customer": payload.get("customer"),
        "subscription": payload.get("subscription"),
        "cancel_at_period_end": payload.get("cancel_at_period_end"),
        "cancel_at": payload.get("cancel_at"),
        "current_period_end": payload.get("current_period_end"),
        "ended_at": payload.get("ended_at"),
        "metadata": {
            "plan_key": metadata.get("plan_key"),
            "category_ids": metadata.get("category_ids"),
            "contact_email": metadata.get("contact_email"),
        },
    }
