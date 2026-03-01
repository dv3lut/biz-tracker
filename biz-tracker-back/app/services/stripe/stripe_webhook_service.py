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
from app.services.stripe.stripe_subscription_events import record_subscription_event
from app.services.stripe.stripe_subscription_utils import (
    apply_stripe_fields,
    apply_subscriptions_from_categories,
    build_client_name,
    ensure_recipient,
    find_client,
    parse_category_ids,
    resolve_plan_key,
    resolve_price_id,
    resolve_email_from_payload,
    resolve_end_date,
    resolve_start_date,
    retrieve_subscription,
    to_datetime,
)
from app.services.stripe.stripe_upgrade_tokens import build_upgrade_token, build_upgrade_url
from app.services.stripe.stripe_checkout_service import _resolve_recipient_email, _send_subscription_update_email


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

    if event_type == "invoice.payment_succeeded":
        _handle_invoice_payment_succeeded(session, settings, payload)
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
    if category_ids:
        client.category_ids = [str(identifier) for identifier in category_ids]

    apply_stripe_fields(client, settings, subscription, customer_id, subscription_id, plan_key)
    upsert_subscription_history(
        session,
        client=client,
        subscription=subscription,
        settings=settings,
        purchased_at=to_datetime(payload.get("created")),
    )

    session.flush()

    _send_post_purchase_email(settings, customer_id, subscription_id, email)

    log_event(
        "stripe.checkout.completed",
        client_id=str(client.id),
        email=email,
        subscription_id=subscription_id,
        plan_key=client.stripe_plan_key,
    )


def _send_post_purchase_email(
    settings: Settings,
    customer_id: str | None,
    subscription_id: str | None,
    email: str | None,
) -> None:
    if not email:
        return

    email_service = EmailService()
    if not email_service.is_enabled() or not email_service.is_configured():
        return

    access_token = build_upgrade_token(
        settings,
        customer_id=customer_id,
        subscription_id=subscription_id,
        email=email,
    )
    upgrade_url = build_upgrade_url(settings, access_token)
    portal_access_url = build_upgrade_url(settings, access_token, anchor="portal")
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
        "Gardez précieusement cet email : il contient vos liens sécurisés.",
        "",
        "Portail Stripe (factures, moyens de paiement, résiliation) :",
    ]
    if portal_direct_url:
        lines.append(f"- Accéder au portail Stripe : {portal_direct_url}")
    else:
        lines.append("- Accès via l'espace de gestion Business Tracker")

    lines.append("")
    lines.append("Changer de plan (upgrade/downgrade uniquement) :")
    if portal_access_url:
        lines.append(f"- Changer de plan : {portal_access_url}")

    lines.extend(
        [
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


def _handle_invoice_payment_succeeded(session: Session, settings: Settings, payload: dict) -> None:
    subscription_id = payload.get("subscription")
    customer_id = payload.get("customer")
    if not subscription_id:
        return

    subscription = retrieve_subscription(settings, subscription_id)
    if not subscription:
        return

    metadata = subscription.get("metadata") or {}

    email = resolve_email_from_payload(payload, metadata)
    client = find_client(session, customer_id=customer_id, subscription_id=subscription_id, email=email)
    if client is None:
        return

    if metadata.get("pending_upgrade_email") == "1":
        if email:
            ensure_recipient(client, email)

        recipient_email = _resolve_recipient_email(client, email)
        upgrade_token = build_upgrade_token(
            settings,
            customer_id=client.stripe_customer_id,
            subscription_id=client.stripe_subscription_id,
            email=recipient_email or email,
        )

        _send_subscription_update_email(
            settings=settings,
            email=recipient_email or email,
            action="upgrade",
            effective_at=None,
            payment_url=None,
            access_token=upgrade_token,
        )

        stripe.api_key = settings.stripe.secret_key
        updated_metadata = dict(metadata)
        updated_metadata["pending_upgrade_email"] = "0"
        stripe.Subscription.modify(subscription_id, metadata=updated_metadata)

    pending_plan_key = metadata.get("pending_plan_key")
    pending_category_ids = parse_category_ids(metadata.get("pending_category_ids"))
    pending_effective_at_raw = metadata.get("pending_effective_at")
    pending_effective_at = None
    if pending_effective_at_raw is not None:
        try:
            pending_effective_at = to_datetime(int(pending_effective_at_raw))
        except (TypeError, ValueError):
            pending_effective_at = None

    if pending_plan_key:
        current_period_start = to_datetime(subscription.get("current_period_start"))
        actual_price_id = resolve_price_id(subscription)
        actual_plan_key = resolve_plan_key(settings, actual_price_id) if actual_price_id else None
        should_apply_pending = False
        if pending_effective_at and current_period_start:
            should_apply_pending = pending_effective_at <= current_period_start
        if actual_plan_key and actual_plan_key == pending_plan_key:
            should_apply_pending = True

        if should_apply_pending:
            if pending_category_ids:
                apply_subscriptions_from_categories(session, client, pending_category_ids)
                client.category_ids = [str(identifier) for identifier in pending_category_ids]
            apply_stripe_fields(client, settings, subscription, customer_id, subscription_id, actual_plan_key)
            upsert_subscription_history(session, client=client, subscription=subscription, settings=settings)
            stripe.api_key = settings.stripe.secret_key
            try:
                stripe.Subscription.modify(
                    subscription_id,
                    metadata={
                        "plan_key": actual_plan_key or pending_plan_key,
                        "category_ids": metadata.get("pending_category_ids") or metadata.get("category_ids"),
                        "pending_plan_key": None,
                        "pending_category_ids": None,
                        "pending_effective_at": None,
                    },
                )
            except stripe.error.StripeError:
                pass
            session.flush()


def _build_post_purchase_email_html(
    portal_direct_url: str | None,
    portal_access_url: str | None,
) -> str:
    primary_url = portal_direct_url or portal_access_url
    secondary_url = portal_access_url if portal_direct_url and portal_access_url else None
    button_label = "Accéder au portail Stripe" if portal_direct_url else "Accéder au portail Stripe"
    change_plan_label = "Changer de plan"

    lines = [
        "<div style=\"font-family:Arial,Helvetica,sans-serif;max-width:600px;margin:0 auto;color:#0f172a;\">",
        "<h1 style=\"font-size:22px;margin-bottom:8px;\">Votre abonnement est actif</h1>",
        "<p style=\"margin:0 0 16px;\">Bienvenue chez Business Tracker. Votre abonnement est bien activé.</p>",
    ]

    if primary_url:
        lines.extend(
            [
                "<div style=\"margin:24px 0;display:flex;flex-wrap:wrap;gap:12px;\">",
                f"<a href=\"{primary_url}\" style=\"background:#0f172a;color:#ffffff;text-decoration:none;padding:12px 20px;border-radius:8px;display:inline-block;\">{button_label}</a>",
                (
                    f"<a href=\"{portal_access_url}\" style=\"background:#ffffff;color:#0f172a;text-decoration:none;padding:12px 20px;border-radius:8px;display:inline-block;border:1px solid #0f172a;\">{change_plan_label}</a>"
                    if portal_access_url
                    else ""
                ),
                "</div>",
            ]
        )
    elif portal_access_url:
        lines.extend(
            [
                "<div style=\"margin:24px 0;\">",
                f"<a href=\"{portal_access_url}\" style=\"background:#0f172a;color:#ffffff;text-decoration:none;padding:12px 20px;border-radius:8px;display:inline-block;\">{change_plan_label}</a>",
                "</div>",
            ]
        )

    lines.append("<p style=\"margin:0 0 8px;\">Depuis le portail Stripe, vous pouvez :</p>")
    lines.append(
        "<ul style=\"margin:0 0 16px;padding-left:18px;\">"
        "<li>consulter vos factures</li>"
        "<li>gérer vos moyens de paiement</li>"
        "<li>résilier votre abonnement</li>"
        "</ul>"
    )
    lines.append("<p style=\"margin:0 0 16px;\">Le bouton <strong>Changer de plan</strong> permet uniquement d'upgrade/downgrade.</p>")

    if secondary_url:
        lines.append(
            f"<p style=\"margin:0 0 16px;\">Lien sécurisé à conserver : <a href=\"{secondary_url}\">{secondary_url}</a></p>"
        )

    lines.append(
        "<p style=\"margin:0 0 16px;\"><strong>Conservez cet email :</strong> il contient vos liens sécurisés pour gérer l'abonnement.</p>"
    )
    lines.append("<p style=\"margin:0;\">L'équipe Business Tracker</p>")
    lines.append("</div>")

    return "".join(lines)


def _handle_subscription_updated(session: Session, settings: Settings, payload: dict) -> bool:
    import logging
    _logger = logging.getLogger(__name__)
    subscription_id = payload.get("id")
    customer_id = payload.get("customer")
    metadata = payload.get("metadata") or {}
    category_ids = parse_category_ids(metadata.get("category_ids"))
    pending_plan_key = metadata.get("pending_plan_key")
    pending_category_ids = parse_category_ids(metadata.get("pending_category_ids"))
    pending_effective_at_raw = metadata.get("pending_effective_at")
    pending_effective_at = None
    if pending_effective_at_raw is not None:
        try:
            pending_effective_at = to_datetime(int(pending_effective_at_raw))
        except (TypeError, ValueError):
            pending_effective_at = None

    actual_price_id = resolve_price_id(payload)
    actual_plan_key = resolve_plan_key(settings, actual_price_id) if actual_price_id else None

    client = find_client(session, customer_id=customer_id, subscription_id=subscription_id, email=None)
    if client is None:
        return False

    _logger.info(
        "stripe.webhook: sub_updated sub=%s actual_price=%s actual_plan=%s metadata_plan=%s pending_plan=%s pending_effective_at=%s",
        subscription_id,
        actual_price_id,
        actual_plan_key,
        metadata.get("plan_key"),
        pending_plan_key,
        pending_effective_at_raw,
    )

    previous_cancel_at = client.stripe_cancel_at

    current_period_start = to_datetime(payload.get("current_period_start"))
    should_apply_pending = False
    if pending_plan_key and pending_effective_at and current_period_start:
        should_apply_pending = pending_effective_at <= current_period_start
    if pending_plan_key and pending_effective_at is None and actual_plan_key and actual_plan_key == pending_plan_key:
        should_apply_pending = True

    if pending_plan_key and not should_apply_pending:
        # Downgrade planifié : éviter les écritures DB concurrentes avec la requête publique.
        _logger.info(
            "stripe.webhook: pending downgrade ignored (metadata_plan=%s pending_plan=%s)",
            metadata.get("plan_key"),
            pending_plan_key,
        )
        return False
    else:
        plan_key = metadata.get("plan_key")
        if actual_plan_key:
            plan_key = actual_plan_key
        if pending_plan_key and pending_category_ids:
            category_ids = pending_category_ids
            plan_key = pending_plan_key if not actual_plan_key else actual_plan_key
        should_apply_now = False
        if pending_plan_key and should_apply_pending:
            should_apply_now = True
        elif pending_plan_key and pending_effective_at is None and actual_plan_key == pending_plan_key:
            should_apply_now = True

        applied_pending = False
        if pending_plan_key and should_apply_now:
            try:
                stripe.api_key = settings.stripe.secret_key
                stripe.Subscription.modify(
                    subscription_id,
                    metadata={
                        "plan_key": plan_key or pending_plan_key,
                        "category_ids": metadata.get("pending_category_ids") or metadata.get("category_ids"),
                        "pending_plan_key": None,
                        "pending_category_ids": None,
                        "pending_effective_at": None,
                    },
                )
            except stripe.error.StripeError:
                pass
            applied_pending = True

        if category_ids:
            apply_subscriptions_from_categories(session, client, category_ids)
            client.category_ids = [str(identifier) for identifier in category_ids]

        apply_stripe_fields(client, settings, payload, customer_id, subscription_id, plan_key)
        _logger.info(
            "stripe.webhook: apply plan_key=%s client_plan_after=%s",
            plan_key,
            getattr(client, "stripe_plan_key", None),
        )
        if applied_pending:
            record_subscription_event(
                session,
                client=client,
                stripe_subscription_id=subscription_id,
                event_type="downgrade_applied",
                from_plan_key=metadata.get("plan_key"),
                to_plan_key=plan_key,
                from_category_ids=[str(identifier) for identifier in parse_category_ids(metadata.get("category_ids"))],
                to_category_ids=[str(identifier) for identifier in (pending_category_ids or parse_category_ids(metadata.get("category_ids")))],
                effective_at=pending_effective_at,
                source="webhook",
            )
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
