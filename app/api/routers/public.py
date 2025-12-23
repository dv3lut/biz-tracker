"""Public (non-admin) endpoints.

Currently used by the marketing landing page contact form.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.api.schemas import PublicContactRequest, PublicContactResponse
from app.config import get_settings
from app.observability import log_event
from app.services.client_service import get_admin_emails
from app.services.email_service import EmailService

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
    session: Session = Depends(get_db_session),
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
    admins = [email for email in get_admin_emails(session) if email]

    # Avoid duplicate deliveries to the inbox.
    admins = [email for email in admins if email.lower() != inbox.lower()]
    if not admins and inbox:
        admins = [inbox]

    body = _format_contact_body(payload)
    reply_to = str(payload.email)

    # Notify admins.
    email_service.send(
        subject="[Business tracker] Nouveau formulaire landing",
        body="Un nouveau formulaire a été soumis.\n\n" + body,
        recipients=admins,
        reply_to=reply_to,
    )

    # Send the form content to the contact inbox.
    if inbox:
        email_service.send(
            subject="[Business tracker] Données formulaire landing",
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
