"""Stripe admin notification helpers."""
from __future__ import annotations

import html
import json
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import models
from app.services.client_service import get_admin_emails
from app.services.email_service import EmailService
from app.services.stripe.stripe_subscription_utils import (
    find_client,
    resolve_email_from_payload,
    resolve_price_id,
    to_datetime,
    retrieve_subscription,
)


def notify_admins_of_stripe_webhook_failure(
    session: Session,
    *,
    status_code: int,
    detail: object,
    payload: bytes | None,
    signature: str | None,
    event_type: str | None = None,
    exc: Exception | None = None,
) -> None:
    email_service = EmailService()
    if not email_service.is_enabled() or not email_service.is_configured():
        return

    recipients = get_admin_emails(session)
    if not recipients:
        return

    error_detail = _stringify_error_detail(detail)
    payload_preview = _format_webhook_payload_preview(payload)
    exception_label = f"{exc.__class__.__name__}: {exc}" if exc else None

    lines = [
        "Le webhook Stripe a échoué.",
        "",
        f"HTTP: {status_code}",
        f"Erreur: {error_detail}",
        f"Type événement: {event_type or '-'}",
        f"Signature présente: {'oui' if signature else 'non'}",
    ]
    if exception_label:
        lines.append(f"Exception: {exception_label}")
    lines.extend(["", "Payload:", payload_preview])

    html_lines = [
        "<p><strong>Le webhook Stripe a échoué.</strong></p>",
        "<p>",
        f"<strong>HTTP:</strong> {status_code}<br/>",
        f"<strong>Erreur:</strong> {html.escape(error_detail)}<br/>",
        f"<strong>Type événement:</strong> {html.escape(event_type or '-')}<br/>",
        f"<strong>Signature présente:</strong> {'oui' if signature else 'non'}",
    ]
    if exception_label:
        html_lines.append(f"<br/><strong>Exception:</strong> {html.escape(exception_label)}")
    html_lines.append("</p>")
    html_lines.append(f"<p><strong>Payload:</strong></p><pre>{html.escape(payload_preview)}</pre>")

    email_service.send(
        subject=f"[Stripe] Échec webhook (HTTP {status_code})",
        body="\n".join(lines),
        recipients=recipients,
        html_body="".join(html_lines),
    )


def notify_admins_of_stripe_event(
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
    client = find_client(session, customer_id=customer_id, subscription_id=subscription_id, email=None)

    subscription = None
    if event_type == "checkout.session.completed":
        subscription = retrieve_subscription(settings, subscription_id)
    elif payload.get("object") == "subscription":
        subscription = payload

    subject = _build_admin_event_subject(event_type=event_type, payload=payload, subscription=subscription)
    body = _format_stripe_event_summary(
        event_type=event_type,
        payload=payload,
        subscription=subscription,
        client=client,
    )
    html_body = _format_stripe_event_summary_html(
        event_type=event_type,
        payload=payload,
        subscription=subscription,
        client=client,
    )

    email_service.send(subject=subject, body=body, recipients=recipients, html_body=html_body)


def _format_stripe_event_summary(
    *,
    event_type: str,
    payload: dict,
    subscription: dict | None,
    client: models.Client | None,
) -> str:
    email = resolve_email_from_payload(payload, payload.get("metadata") or {})
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
        price_id = resolve_price_id(subscription)
        if price_id:
            lines.append(f"Price: {price_id}")
        plan_key = subscription.get("metadata", {}).get("plan_key")
        if plan_key:
            lines.append(f"Plan: {plan_key}")
        referrer_name = _resolve_referrer_name(payload=payload, subscription=subscription)
        if referrer_name:
            lines.append(f"Parrain: {referrer_name}")
        trial_end = to_datetime(subscription.get("trial_end"))
        current_period_end = to_datetime(subscription.get("current_period_end"))
        cancel_at = to_datetime(subscription.get("cancel_at"))
        if trial_end:
            lines.append(f"Fin d'essai: {trial_end:%Y-%m-%d %H:%M}")
        if current_period_end:
            lines.append(f"Fin de période: {current_period_end:%Y-%m-%d %H:%M}")
        if cancel_at:
            lines.append(f"Résiliation planifiée: {cancel_at:%Y-%m-%d %H:%M}")
        cancellation_details = subscription.get("cancellation_details")
        reason = _extract_cancellation_reason(cancellation_details)
        if reason:
            lines.append(f"Raison d'annulation: {reason}")

    return "\n".join(lines)


def _format_stripe_event_summary_html(
    *,
    event_type: str,
    payload: dict,
    subscription: dict | None,
    client: models.Client | None,
) -> str:
    email = resolve_email_from_payload(payload, payload.get("metadata") or {})
    if not email and client:
        email = (client.recipients[0].email if client.recipients else None)

    html_lines = [
        "<p><strong>Événement Stripe détecté.</strong></p>",
        "<p>",
        f"<strong>Type:</strong> {html.escape(event_type)}",
    ]

    if client:
        html_lines.append(
            f"<strong>Client:</strong> {html.escape(client.name)} ({html.escape(str(client.id))})"
        )
    if email:
        html_lines.append(f"<strong>Email:</strong> {html.escape(email)}")

    subscription_id = payload.get("subscription") or payload.get("id")
    if subscription_id:
        html_lines.append(f"<strong>Subscription:</strong> {html.escape(str(subscription_id))}")
    if payload.get("customer"):
        html_lines.append(f"<strong>Customer:</strong> {html.escape(str(payload.get('customer')))}")

    if subscription:
        html_lines.append(f"<strong>Statut:</strong> {html.escape(str(subscription.get('status')))}")
        price_id = resolve_price_id(subscription)
        if price_id:
            html_lines.append(f"<strong>Price:</strong> {html.escape(price_id)}")
        plan_key = subscription.get("metadata", {}).get("plan_key")
        if plan_key:
            html_lines.append(f"<strong>Plan:</strong> {html.escape(plan_key)}")
        referrer_name = _resolve_referrer_name(payload=payload, subscription=subscription)
        if referrer_name:
            html_lines.append(
                f"<strong>Parrain:</strong> <strong>{html.escape(referrer_name)}</strong>"
            )
        trial_end = to_datetime(subscription.get("trial_end"))
        current_period_end = to_datetime(subscription.get("current_period_end"))
        cancel_at = to_datetime(subscription.get("cancel_at"))
        if trial_end:
            html_lines.append(f"<strong>Fin d'essai:</strong> {trial_end:%Y-%m-%d %H:%M}")
        if current_period_end:
            html_lines.append(f"<strong>Fin de période:</strong> {current_period_end:%Y-%m-%d %H:%M}")
        if cancel_at:
            html_lines.append(f"<strong>Résiliation planifiée:</strong> {cancel_at:%Y-%m-%d %H:%M}")
        cancellation_details = subscription.get("cancellation_details")
        reason = _extract_cancellation_reason(cancellation_details)
        if reason:
            html_lines.append(f"<strong>Raison d'annulation:</strong> {html.escape(reason)}")

    html_lines.append("</p>")
    return "<br/>".join(html_lines)


def _resolve_referrer_name(*, payload: dict, subscription: dict | None) -> str | None:
    referrer = None
    if subscription:
        referrer = subscription.get("metadata", {}).get("referrer_name")
    if not referrer:
        referrer = payload.get("metadata", {}).get("referrer_name")
    if isinstance(referrer, str) and referrer.strip():
        return referrer.strip()
    return None


def _build_admin_event_subject(
    *,
    event_type: str,
    payload: dict,
    subscription: dict | None,
) -> str:
    if event_type == "checkout.session.completed":
        return "[Stripe] Checkout confirmé"
    if event_type == "customer.subscription.deleted":
        return "[Stripe] Abonnement résilié"
    if event_type == "customer.subscription.updated":
        cancel_at_period_end = payload.get("cancel_at_period_end")
        if cancel_at_period_end:
            return "[Stripe] Annulation programmée"
        return "[Stripe] Abonnement mis à jour"
    return f"[Stripe] Événement {event_type}"


def _extract_cancellation_reason(details: object) -> str | None:
    if not isinstance(details, dict):
        return None
    reason = details.get("reason")
    if isinstance(reason, str) and reason.strip():
        return reason.strip()
    comment = details.get("comment")
    if isinstance(comment, str) and comment.strip():
        return comment.strip()
    return None


def _stringify_error_detail(detail: object) -> str:
    if isinstance(detail, str):
        return detail
    try:
        return json.dumps(detail, ensure_ascii=False)
    except TypeError:
        return str(detail)


def _format_webhook_payload_preview(payload: bytes | None, *, max_chars: int = 4_000) -> str:
    if not payload:
        return "-"
    decoded = payload.decode("utf-8", errors="replace")
    if len(decoded) <= max_chars:
        return decoded
    return f"{decoded[:max_chars]}\n… payload tronqué ({len(decoded)} caractères)."
