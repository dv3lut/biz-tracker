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
    PublicStripePortalSessionRequest,
    PublicStripePortalSessionResponse,
    PublicStripeSubscriptionInfoRequest,
    PublicStripeSubscriptionInfoResponse,
    PublicStripeUpdateRequest,
    PublicStripeUpdateResponse,
    PublicStripeUpdatePreviewRequest,
    PublicStripeUpdatePreviewResponse,
    PublicStripeSettingsOut,
)
from app.config import get_settings
from app.observability import log_event
from app.services.email_service import EmailService
from app.services.stripe.stripe_checkout_service import (
    create_checkout_session,
    get_subscription_update_preview,
    get_subscription_info,
    list_public_categories,
    update_subscription,
)
from app.services.stripe.stripe_portal_service import (
    create_portal_session_for_access_token,
    send_portal_access_email,
)
from app.services.stripe.stripe_admin_notifications import notify_admins_of_stripe_webhook_failure
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


@router.post(
    "/stripe/portal-session",
    response_model=PublicStripePortalSessionResponse,
    summary="Créer une session Stripe Customer Portal via lien sécurisé",
)
def create_stripe_portal_session(
    payload: PublicStripePortalSessionRequest,
    session: Session = Depends(get_db_session),
) -> PublicStripePortalSessionResponse:
    settings = get_settings()
    url = create_portal_session_for_access_token(session, settings, payload.access_token)
    return PublicStripePortalSessionResponse(url=url)


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
    import logging
    _logger = logging.getLogger(__name__)
    _logger.info("update_stripe_subscription: START")
    settings = get_settings()
    result = update_subscription(session, settings, payload)
    _logger.info(
        "update_stripe_subscription: END action=%s payment_url=%s effective_at=%s",
        result.action, result.payment_url, result.effective_at
    )
    response = PublicStripeUpdateResponse(
        payment_url=result.payment_url,
        action=result.action,
        effective_at=result.effective_at,
    )
    _logger.info("update_stripe_subscription: RESPONSE_CREATED")
    return response


@router.post(
    "/stripe/subscription-update-preview",
    response_model=PublicStripeUpdatePreviewResponse,
    summary="Prévisualiser un upgrade Stripe",
)
def preview_stripe_subscription_update(
    payload: PublicStripeUpdatePreviewRequest,
    session: Session = Depends(get_db_session),
) -> PublicStripeUpdatePreviewResponse:
    settings = get_settings()
    preview = get_subscription_update_preview(session, settings, payload)
    return PublicStripeUpdatePreviewResponse(
        amount_due=preview.amount_due,
        currency=preview.currency,
        is_upgrade=preview.is_upgrade,
        is_trial=preview.is_trial,
        has_payment_method=preview.has_payment_method,
    )


@router.post(
    "/stripe/subscription-info",
    response_model=PublicStripeSubscriptionInfoResponse,
    summary="Récupérer les informations d'un abonnement Stripe",
)
def get_stripe_subscription_info(
    payload: PublicStripeSubscriptionInfoRequest,
    session: Session = Depends(get_db_session),
) -> PublicStripeSubscriptionInfoResponse:
    settings = get_settings()
    info = get_subscription_info(session, settings, payload.access_token)
    return PublicStripeSubscriptionInfoResponse(
        plan_key=info.plan_key,
        status=info.status,
        current_period_end=info.current_period_end,
        cancel_at=info.cancel_at,
        contact_name=info.contact_name,
        contact_email=info.contact_email,
        categories=info.categories,
        departments=info.departments,
        all_departments=info.all_departments,
    )


@router.post(
    "/stripe/webhook",
    summary="Webhook Stripe",
)
async def stripe_webhook(request: Request, session: Session = Depends(get_db_session)) -> dict[str, bool]:
    settings = get_settings()
    payload: bytes | None = None
    signature: str | None = None
    event_type: str | None = None

    try:
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

        if isinstance(event, dict):
            event_type = event.get("type")

        handle_stripe_webhook(session, settings, event)
        return {"received": True}

    except HTTPException as exc:
        notify_admins_of_stripe_webhook_failure(
            session,
            status_code=exc.status_code,
            detail=exc.detail,
            payload=payload,
            signature=signature,
            event_type=event_type,
            exc=exc,
        )
        raise
    except Exception as exc:
        notify_admins_of_stripe_webhook_failure(
            session,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
            payload=payload,
            signature=signature,
            event_type=event_type,
            exc=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors du traitement du webhook Stripe.",
        ) from exc