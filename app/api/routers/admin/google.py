"""Google-related admin endpoints."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.api.schemas import EstablishmentOut, ManualGoogleCheckResponse
from app.config import get_settings
from app.db import models
from app.observability import log_event
from app.services.client_service import collect_client_emails, dispatch_email_to_clients, get_active_clients
from app.services.email_service import EmailService
from app.services.google_business_service import GoogleBusinessService
from app.services.export_service import build_google_places_workbook

from .common import format_establishment_summary

router = APIRouter(tags=["admin"])


@router.post(
    "/establishments/{siret}/google-check",
    response_model=ManualGoogleCheckResponse,
    summary="Vérifier un établissement via Google Places et envoyer une alerte",
)
def manual_google_check(
    siret: str,
    session: Session = Depends(get_db_session),
) -> ManualGoogleCheckResponse:
    settings = get_settings()
    google_settings = settings.google
    if not google_settings.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="L'enrichissement Google est désactivé ou la clé API est absente.",
        )

    email_service = EmailService()
    if not email_service.is_enabled():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Le service e-mail est désactivé.")
    if not email_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Configuration SMTP incomplète (hôte ou adresse expéditeur manquants).",
        )

    active_clients = get_active_clients(session)
    eligible_clients = [client for client in active_clients if any(recipient.email for recipient in client.recipients)]
    configured_recipients = collect_client_emails(eligible_clients)
    if not configured_recipients:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Aucun destinataire configuré.")

    establishment = session.get(models.Establishment, siret)
    if establishment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Établissement introuvable.")

    google_service = GoogleBusinessService(session)
    try:
        match = google_service.manual_check(establishment)
    finally:
        google_service.close()

    session.refresh(establishment)

    found = match is not None
    check_status = establishment.google_check_status
    place_url = establishment.google_place_url
    place_id = establishment.google_place_id

    email_sent = False
    partial_failure = False
    if found:
        subject = (
            f"[{settings.sync.scope_key}] Page Google détectée pour "
            f"{establishment.name or establishment.siret}"
        )
        message_lines = [
            "Une vérification manuelle Google Places vient d'être effectuée.",
            "",
            *format_establishment_summary(establishment),
            "",
            "Cette recherche a été déclenchée depuis la console d'administration Biz Tracker.",
        ]
        if not establishment.google_place_url:
            message_lines.insert(
                3,
                "  Attention : Google Places n'a pas fourni d'URL publique pour cette fiche (Place ID uniquement).",
            )
        body = "\n".join(message_lines)

        dispatch_result = dispatch_email_to_clients(email_service, eligible_clients, subject, body)
        partial_failure = bool(dispatch_result.failed)

        for client, exc in dispatch_result.failed:
            log_event(
                "manual_google.email.error",
                client_id=str(client.id),
                siret=siret,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

        if dispatch_result.delivered:
            email_sent = True
        else:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Échec de l'envoi de l'e-mail d'alerte.",
            )

    if check_status == "insufficient":
        message = "Informations insuffisantes pour lancer une recherche Google."
    elif found:
        if email_sent:
            if partial_failure:
                message = (
                    "Une page Google a été trouvée. Certains clients n'ont pas pu être notifiés, "
                    "consultez les logs pour les détails."
                )
            else:
                message = "Une page Google a été trouvée et les destinataires ont été notifiés."
        else:
            message = "Une page Google a été trouvée mais aucun e-mail n'a été envoyé."
    else:
        message = "Aucune page Google n'a été trouvée pour cet établissement."

    log_event(
        "sync.google.manual_check",
        siret=siret,
        found=found,
        email_sent=email_sent,
        partial_failure=partial_failure,
        configured_recipients=len(configured_recipients),
        place_id=place_id,
        place_url=place_url,
        check_status=check_status,
    )

    establishment_payload = EstablishmentOut.model_validate(establishment)
    return ManualGoogleCheckResponse(
        found=found,
        email_sent=email_sent,
        message=message,
        place_id=place_id,
        place_url=place_url,
        check_status=check_status,
        establishment=establishment_payload,
    )


@router.get(
    "/google/places-export",
    summary="Exporter les établissements enrichis via Google Places",
)
def export_google_places(session: Session = Depends(get_db_session)) -> StreamingResponse:
    stmt = (
        select(models.Establishment)
        .where(
            or_(
                models.Establishment.google_place_url.is_not(None),
                models.Establishment.google_place_id.is_not(None),
            )
        )
        .order_by(
            models.Establishment.google_last_found_at.desc().nullslast(),
            models.Establishment.last_seen_at.desc(),
        )
    )
    establishments = session.execute(stmt).scalars().all()
    workbook_stream = build_google_places_workbook(establishments)
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    filename = f"biz-tracker-google-places-{timestamp}.xlsx"

    log_event(
        "export.google.places",
        count=len(establishments),
        filename=filename,
    )

    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        workbook_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )
