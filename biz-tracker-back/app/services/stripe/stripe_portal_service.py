"""Stripe portal access helpers."""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
import stripe

from app.config import Settings
from app.observability import log_event
from app.services.email_service import EmailService
from app.services.stripe.stripe_subscription_utils import find_client
from app.services.stripe.stripe_upgrade_tokens import (
    build_upgrade_token,
    build_upgrade_url,
    parse_upgrade_token,
)

from .stripe_common import ensure_stripe_configured, find_client_by_email


def create_portal_session(session: Session, settings: Settings, email: str) -> str:
    stripe_config = ensure_stripe_configured(settings)
    client = find_client_by_email(session, email)
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


def create_portal_session_for_access_token(
    session: Session,
    settings: Settings,
    access_token: str,
) -> str:
    stripe_config = ensure_stripe_configured(settings)
    access = parse_upgrade_token(settings, access_token)
    client = find_client(
        session,
        customer_id=access.customer_id,
        subscription_id=access.subscription_id,
        email=access.email,
    )
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

    safe_email = (access.email or "").strip().lower()
    log_event("stripe.portal.created", email=safe_email)
    return portal_session.url


def send_portal_access_email(session: Session, settings: Settings, email: str) -> None:
    email_service = EmailService()
    if not email_service.is_enabled() or not email_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service e-mail indisponible (désactivé ou non configuré).",
        )

    safe_email = email.strip().lower()
    client = find_client_by_email(session, email)
    if not client or not client.stripe_customer_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client Stripe introuvable.")

    portal_url = create_portal_session(session, settings, email)
    upgrade_token = build_upgrade_token(
        settings,
        customer_id=client.stripe_customer_id,
        subscription_id=client.stripe_subscription_id,
        email=safe_email,
    )
    upgrade_url = build_upgrade_url(settings, upgrade_token)
    business_tracker_url = "https://business-tracker.fr"
    subject = "[Business Tracker] Accès à votre portail Stripe"
    lines = [
        "Bonjour,",
        "",
        "Voici vos liens sécurisés :",
        f"- Accéder au portail Stripe : {portal_url}",
    ]
    if upgrade_url:
        lines.append(f"- Changer de plan : {upgrade_url}")
    lines.append(f"- Page Business Tracker : {business_tracker_url}")
    lines.extend(
        [
            "",
            "Conservez cet email : il contient vos liens utiles.",
            "",
            "Si vous n'êtes pas à l'origine de cette demande, vous pouvez ignorer cet email.",
            "",
            "L'équipe Business Tracker",
        ]
    )
    body = "\n".join(lines)
    html_lines = [
        "<div style=\"font-family:Arial,Helvetica,sans-serif;max-width:600px;margin:0 auto;color:#0f172a;\">",
        "<h1 style=\"font-size:20px;margin-bottom:8px;\">Accès au portail Stripe</h1>",
        "<p style=\"margin:0 0 16px;\">Voici vos liens sécurisés :</p>",
        f"<p style=\"margin:0 0 8px;\"><a href=\"{portal_url}\">Accéder au portail Stripe</a></p>",
    ]
    if upgrade_url:
        html_lines.append(
            f"<p style=\"margin:0 0 8px;\"><a href=\"{upgrade_url}\">Changer de plan</a></p>"
        )
    html_lines.extend(
        [
            f"<p style=\"margin:0 0 16px;\"><a href=\"{business_tracker_url}\">Page Business Tracker</a></p>",
            "<p style=\"margin:0 0 16px;\"><strong>Conservez cet email :</strong> il contient vos liens utiles.</p>",
            "<p style=\"margin:0;\">Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.</p>",
            "</div>",
        ]
    )
    html_body = "".join(html_lines)

    email_service.send(subject=subject, body=body, html_body=html_body, recipients=[safe_email])
    log_event("stripe.portal.email_sent", email=safe_email)
