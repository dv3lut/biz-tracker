"""E-mail related admin endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.api.schemas import AdminEmailConfig, AdminEmailConfigUpdate, EmailTestRequest, EmailTestResponse
from app.config import get_settings
from app.db import models
from app.observability import log_event
from app.services.alerts.alert_email_settings import get_alert_email_settings, update_alert_email_settings
from app.services.client_service import collect_client_emails, get_active_clients, get_admin_emails
from app.services.email_service import EmailService

from .common import normalize_emails

router = APIRouter(tags=["admin"])


@router.post(
    "/email/test",
    response_model=EmailTestResponse,
    summary="Envoyer un e-mail de test",
)
def send_test_email(
    payload: EmailTestRequest = Body(default_factory=EmailTestRequest),
    session: Session = Depends(get_db_session),
) -> EmailTestResponse:
    settings = get_settings().email
    email_service = EmailService()

    if not email_service.is_enabled():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Le service e-mail est désactivé.")

    if not email_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Configuration SMTP incomplète (hôte ou adresse expéditeur manquants).",
        )

    if payload.recipients:
        recipients = normalize_emails(payload.recipients)
    else:
        recipients = normalize_emails(get_admin_emails(session))
        if not recipients:
            recipients = collect_client_emails(get_active_clients(session))
    if not recipients:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Aucun destinataire configuré.")

    provider = settings.provider or "SMTP"
    subject = payload.subject or f"[{provider}] Test Business tracker"
    body = payload.body or (
        "Ce message confirme que la configuration SMTP de Business tracker fonctionne.\n"
        "Vous recevez cet e-mail car l'endpoint /admin/email/test a été appelé."
    )

    email_service.send(subject, body, recipients)
    log_event(
        "email.test_sent",
        provider=provider,
        recipients=recipients,
    )
    return EmailTestResponse(sent=True, provider=provider, subject=subject, recipients=recipients)


@router.get(
    "/email/admin-recipients",
    response_model=AdminEmailConfig,
    summary="Lister les destinataires administrateurs du résumé",
)
def get_admin_email_recipients(session: Session = Depends(get_db_session)) -> AdminEmailConfig:
    recipients = get_admin_emails(session)
    settings = get_alert_email_settings(session, create_if_missing=True)
    return AdminEmailConfig(
        recipients=recipients,
        include_previous_month_day_alerts=settings.include_previous_month_day_alerts,
    )


@router.put(
    "/email/admin-recipients",
    response_model=AdminEmailConfig,
    summary="Mettre à jour les destinataires administrateurs du résumé",
)
def update_admin_email_recipients(
    payload: AdminEmailConfigUpdate,
    session: Session = Depends(get_db_session),
) -> AdminEmailConfig:
    normalized = normalize_emails(payload.recipients)
    existing_recipients = session.execute(select(models.AdminRecipient)).scalars().all()
    existing_by_email = {recipient.email: recipient for recipient in existing_recipients}

    updated: list[models.AdminRecipient] = []
    for email in normalized:
        recipient = existing_by_email.pop(email, None)
        if recipient is None:
            recipient = models.AdminRecipient(email=email)
            session.add(recipient)
        updated.append(recipient)

    for recipient in existing_by_email.values():
        session.delete(recipient)

    session.flush()

    event_name = "admin.email.recipients.cleared" if not updated else "admin.email.recipients.updated"
    log_event(event_name, count=len(updated))

    settings = update_alert_email_settings(
        session,
        include_previous_month_day_alerts=payload.include_previous_month_day_alerts,
    )
    log_event(
        "admin.email.settings.updated",
        include_previous_month_day_alerts=settings.include_previous_month_day_alerts,
    )

    return AdminEmailConfig(
        recipients=[recipient.email for recipient in updated],
        include_previous_month_day_alerts=settings.include_previous_month_day_alerts,
    )