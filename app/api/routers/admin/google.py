"""Google-related admin endpoints."""
from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.api.schemas import (
    EstablishmentOut,
    GoogleRetryConfigOut,
    GoogleRetryConfigUpdate,
    ManualGoogleCheckResponse,
)
from app.config import get_settings
from app.db import models
from app.observability import log_event
from app.services.client_service import (
    ClientEmailPayload,
    collect_client_emails,
    dispatch_email_to_clients,
    filter_clients_for_naf_code,
    get_active_clients,
)
from app.services.email_service import EmailService
from app.services.google_business_service import GoogleBusinessService
from app.services.export_service import build_google_places_workbook
from app.services.google_retry_config import (
    ensure_google_retry_config,
    load_runtime_google_retry_config,
    serialize_google_retry_config,
    update_google_retry_config,
)

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
    establishment = session.get(models.Establishment, siret)
    if establishment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Établissement introuvable.")

    subscribed_clients, filtering_applied = filter_clients_for_naf_code(eligible_clients, establishment.naf_code)
    configured_recipients = collect_client_emails(subscribed_clients)
    if not configured_recipients:
        message = "Aucun destinataire configuré."
        if filtering_applied:
            message = "Aucun client abonné à ce code NAF n'a de destinataire configuré."
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

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

        payloads = [
            ClientEmailPayload(
                client=client,
                subject=subject,
                text_body=body,
                html_body=None,
                establishments=[establishment],
            )
            for client in subscribed_clients
        ]

        dispatch_result = dispatch_email_to_clients(email_service, payloads)
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
def export_google_places(
    start_date: date | None = None,
    end_date: date | None = None,
    session: Session = Depends(get_db_session),
) -> StreamingResponse:
    if (start_date and not end_date) or (end_date and not start_date):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Merci de fournir une date de début et une date de fin pour l'export.",
        )
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La date de début doit être antérieure ou égale à la date de fin.",
        )

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

    if start_date:
        stmt = stmt.where(models.Establishment.date_creation >= start_date)
    if end_date:
        stmt = stmt.where(models.Establishment.date_creation <= end_date)

    establishments = session.execute(stmt).scalars().all()
    workbook_stream = build_google_places_workbook(establishments)
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    filename = f"biz-tracker-google-places-{timestamp}.xlsx"

    log_event(
        "export.google.places",
        count=len(establishments),
        filename=filename,
        start_date=start_date.isoformat() if start_date else None,
        end_date=end_date.isoformat() if end_date else None,
    )

    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        workbook_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@router.get(
    "/google/retry-config",
    response_model=GoogleRetryConfigOut,
    summary="Consulter la configuration des relances Google",
)
def get_google_retry_config(session: Session = Depends(get_db_session)) -> GoogleRetryConfigOut:
    record = ensure_google_retry_config(session)
    payload = serialize_google_retry_config(record)
    runtime = load_runtime_google_retry_config(session)
    log_event(
        "google.retry_config.read",
        retry_weekdays=list(runtime.retry_weekdays),
        default_rules=len(runtime.default_rules),
        micro_rules=len(runtime.micro_rules),
    )
    return GoogleRetryConfigOut(**payload)


@router.put(
    "/google/retry-config",
    response_model=GoogleRetryConfigOut,
    summary="Mettre à jour la configuration des relances Google",
)
def update_google_retry_config_endpoint(
    payload: GoogleRetryConfigUpdate = Body(...),
    session: Session = Depends(get_db_session),
) -> GoogleRetryConfigOut:
    record = update_google_retry_config(
        session,
        retry_weekdays=payload.retry_weekdays,
        default_rules=[rule.model_dump() for rule in payload.default_rules],
        micro_rules=[rule.model_dump() for rule in payload.micro_rules],
    )
    session.flush()
    payload_dict = serialize_google_retry_config(record)
    runtime = load_runtime_google_retry_config(session)
    log_event(
        "google.retry_config.updated",
        retry_weekdays=list(runtime.retry_weekdays),
        default_rules=len(runtime.default_rules),
        micro_rules=len(runtime.micro_rules),
    )
    return GoogleRetryConfigOut(**payload_dict)
