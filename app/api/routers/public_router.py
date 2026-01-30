"""Public (non-admin) endpoints.

Currently used by the marketing landing page contact form.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
import stripe
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.api.schemas import (
    PublicContactRequest,
    PublicContactResponse,
    PublicNafCategoryOut,
    PublicStripeCheckoutRequest,
    PublicStripeCheckoutResponse,
    PublicStripePortalRequest,
    PublicStripePortalResponse,
    PublicStripeUpdateRequest,
    PublicStripeUpdateResponse,
    PublicStripeSettingsOut,
)
from app.config import get_settings
from app.observability import log_event
from app.services.email_service import EmailService
from app.services.stripe.stripe_checkout_service import (
    create_checkout_session,
    list_public_categories,
    update_subscription,
)
from app.services.stripe.stripe_portal_service import send_portal_access_email
from app.services.stripe.stripe_webhook_service import handle_stripe_webhook
from app.services.stripe.stripe_settings_service import get_billing_settings

router = APIRouter(prefix="/public", tags=["public"])


def _format_contact_body(payload: PublicContactRequest) -> str:
    message = (payload.message or "").strip() or "-"
    phone = (payload.phone or "").strip() or "-"
    return "\n".join(
        [
            "Nouveau formulaire reçu via la landing page.",
            "",
            f"Nom: {payload.name}",
            f"Email: {payload.email}",
            f"Entreprise: {payload.company}",
            f"Téléphone: {phone}",
            "",
            "Message:",
            message,
        ]
    )


@router.post(
    "/contact",
    response_model=PublicContactResponse,
    summary="Soumettre le formulaire de contact de la landing page",
)
def submit_contact_form(
    request: Request,
    payload: PublicContactRequest = Body(...),
) -> PublicContactResponse:
    settings = get_settings()
    if not settings.public_contact.enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint désactivé.")

    # Honeypot: accept silently but do not send emails.
    if payload.website and payload.website.strip():
        log_event(
            "public.contact.spam_blocked",
            ip=getattr(getattr(request, "client", None), "host", None),
        )
        return PublicContactResponse(accepted=True)

    email_service = EmailService()
    if not email_service.is_enabled() or not email_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service e-mail indisponible (désactivé ou non configuré).",
        )

    inbox = (settings.public_contact.inbox_address or "").strip()
    if not inbox:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Adresse de réception (contact) non configurée.",
        )

    body = _format_contact_body(payload)
    reply_to = str(payload.email)

    email_service.send(
        subject="[Business tracker] Nouveau formulaire landing",
        body=body,
        recipients=[inbox],
        reply_to=reply_to,
    )

    log_event(
        "public.contact.submitted",
        ip=getattr(getattr(request, "client", None), "host", None),
        user_agent=request.headers.get("user-agent"),
        has_message=bool((payload.message or "").strip()),
    )

    return PublicContactResponse(accepted=True)


@router.get(
    "/naf-categories",
    response_model=list[PublicNafCategoryOut],
    summary="Lister les catégories NAF publiques",
)
def list_public_naf_categories(session: Session = Depends(get_db_session)) -> list[PublicNafCategoryOut]:
    return list_public_categories(session)


@router.post(
    "/stripe/checkout",
    response_model=PublicStripeCheckoutResponse,
    summary="Créer une session Stripe Checkout",
)
def create_stripe_checkout(
    payload: PublicStripeCheckoutRequest,
    session: Session = Depends(get_db_session),
) -> PublicStripeCheckoutResponse:
    settings = get_settings()
    url = create_checkout_session(session, settings, payload)
    return PublicStripeCheckoutResponse(url=url)


@router.post(
    "/stripe/portal",
    response_model=PublicStripePortalResponse,
    summary="Créer une session Stripe Customer Portal",
)
def create_stripe_portal(
    payload: PublicStripePortalRequest,
    session: Session = Depends(get_db_session),
) -> PublicStripePortalResponse:
    settings = get_settings()
    send_portal_access_email(session, settings, payload.email)
    return PublicStripePortalResponse(sent=True)


@router.get(
    "/stripe/settings",
    response_model=PublicStripeSettingsOut,
    summary="Récupérer la configuration Stripe publique",
)
def get_public_stripe_settings(session: Session = Depends(get_db_session)) -> PublicStripeSettingsOut:
    billing_settings = get_billing_settings(session)
    return PublicStripeSettingsOut(trial_period_days=billing_settings.trial_period_days)


@router.post(
    "/stripe/subscription-update",
    response_model=PublicStripeUpdateResponse,
    summary="Mettre à jour un abonnement Stripe",
)
def update_stripe_subscription(
    payload: PublicStripeUpdateRequest,
    session: Session = Depends(get_db_session),
) -> PublicStripeUpdateResponse:
    settings = get_settings()
    payment_url = update_subscription(session, settings, payload)
    return PublicStripeUpdateResponse(payment_url=payment_url)


@router.post(
    "/stripe/webhook",
    summary="Webhook Stripe",
)
async def stripe_webhook(request: Request, session: Session = Depends(get_db_session)) -> dict[str, bool]:
    settings = get_settings()
    if not settings.stripe.webhook_secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Webhook Stripe non configuré.")
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    if not signature:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Signature Stripe manquante.")

    try:
        event = stripe.Webhook.construct_event(payload, signature, settings.stripe.webhook_secret)
    except stripe.error.SignatureVerificationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Signature Stripe invalide.") from exc

    handle_stripe_webhook(session, settings, event)
    return {"received": True}