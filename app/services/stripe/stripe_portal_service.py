"""Stripe portal access helpers."""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
import stripe

from app.config import Settings
from app.observability import log_event
from app.services.email_service import EmailService

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


def send_portal_access_email(session: Session, settings: Settings, email: str) -> None:
    email_service = EmailService()
    if not email_service.is_enabled() or not email_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service e-mail indisponible (désactivé ou non configuré).",
        )

    portal_url = create_portal_session(session, settings, email)
    safe_email = email.strip().lower()
    subject = "[Business Tracker] Accès à votre portail Stripe"
    body = "\n".join(
        [
            "Bonjour,",
            "",
            "Voici votre lien sécurisé vers le portail Stripe :",
            portal_url,
            "",
            "Si vous n'êtes pas à l'origine de cette demande, vous pouvez ignorer cet email.",
            "",
            "L'équipe Business Tracker",
        ]
    )
    html_body = (
        "<div style=\"font-family:Arial,Helvetica,sans-serif;max-width:600px;margin:0 auto;color:#0f172a;\">"
        "<h1 style=\"font-size:20px;margin-bottom:8px;\">Accès au portail Stripe</h1>"
        "<p style=\"margin:0 0 16px;\">Voici votre lien sécurisé pour gérer votre abonnement :</p>"
        f"<p style=\"margin:0 0 24px;\"><a href=\"{portal_url}\">{portal_url}</a></p>"
        "<p style=\"margin:0;\">Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.</p>"
        "</div>"
    )

    email_service.send(subject=subject, body=body, html_body=html_body, recipients=[safe_email])
    log_event("stripe.portal.email_sent", email=safe_email)
