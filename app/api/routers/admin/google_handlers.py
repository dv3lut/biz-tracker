"""Helper functions for the Google admin router."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from fastapi import HTTPException, status
from fastapi.params import Query as QueryInfo
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.schemas import (
    EstablishmentOut,
    ListingStatus,
    ManualGoogleCheckResponse,
)
from app.config import get_settings
from app.db import models
from app.observability import log_event
from app.services.client_service import (
    ClientEmailPayload,
    collect_client_emails,
    dispatch_email_to_clients,
    filter_clients_by_listing_status,
    filter_clients_for_naf_code,
    get_active_clients,
    get_admin_emails,
)
from app.services.email_service import EmailService
from app.services.export_service import build_google_places_workbook
from app.services.google_business_service import GoogleBusinessService
from app.utils.google_listing import normalize_listing_age_status, normalize_listing_status_filters

from .common import format_establishment_summary


def manual_google_check_action(
    *,
    siret: str,
    notify_clients: bool,
    session: Session,
) -> ManualGoogleCheckResponse:
    """Execute the manual Google check logic and optionally send notifications."""

    settings = get_settings()
    google_settings = settings.google
    if not google_settings.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="L'enrichissement Google est désactivé ou la clé API est absente.",
        )

    establishment = session.get(models.Establishment, siret)
    if establishment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Établissement introuvable.")

    subscribed_clients: list[models.Client] = []
    configured_recipients: list[str] = []
    filtering_applied = False
    email_service: EmailService | None = None
    admin_emails: list[str] = []

    if notify_clients:
        email_service = EmailService()
        if not email_service.is_enabled():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Le service e-mail est désactivé.")
        if not email_service.is_configured():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Configuration SMTP incomplète (hôte ou adresse expéditeur manquants).",
            )

        admin_emails = get_admin_emails(session)

        active_clients = get_active_clients(session)
        eligible_clients = [client for client in active_clients if any(recipient.email for recipient in client.recipients)]
        subscribed_clients, naf_filtering_applied = filter_clients_for_naf_code(eligible_clients, establishment.naf_code)
        subscribed_clients, status_filtering_applied = filter_clients_by_listing_status(
            subscribed_clients,
            establishment.google_listing_age_status,
        )
        filtering_applied = naf_filtering_applied or status_filtering_applied
        configured_recipients = collect_client_emails(subscribed_clients)

        if not configured_recipients and not admin_emails:
            if naf_filtering_applied and status_filtering_applied:
                message = (
                    "Aucun client abonné à ce code NAF et autorisé pour ce statut n'a de destinataire configuré."
                )
            elif naf_filtering_applied:
                message = "Aucun client abonné à ce code NAF n'a de destinataire configuré."
            elif status_filtering_applied:
                message = "Aucun client autorisé pour ce statut de fiche n'a de destinataire configuré."
            else:
                message = "Aucun destinataire configuré."
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
    admin_email_sent = False
    partial_failure = False

    if notify_clients and found:
        assert email_service is not None  # placate type checker
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

        if admin_emails:
            admin_subject = f"[{settings.sync.scope_key}] Check Google relancé: {establishment.name or establishment.siret}"
            admin_message_lines = [
                "Un check Google manuel a été relancé depuis l'administration.",
                "",
                f"Établissement: {establishment.name or establishment.siret} ({establishment.siret})",
                f"NAF: {establishment.naf_code or 'N/A'}",
                "",
                f"Résultat: {'Fiche trouvée' if found else 'Aucune fiche détectée'}",
            ]
            if found:
                admin_message_lines.append(f"Place ID: {establishment.google_place_id or 'N/A'}")
                if establishment.google_place_url:
                    admin_message_lines.append(f"URL: {establishment.google_place_url}")
            admin_body = "\n".join(admin_message_lines)
            try:
                email_service.send(admin_subject, admin_body, admin_emails)
                admin_email_sent = True
                log_event(
                    "manual_google.admin_email.sent",
                    siret=siret,
                    admin_count=len(admin_emails),
                )
            except Exception as exc:  # pragma: no cover - log and continue
                log_event(
                    "manual_google.admin_email.error",
                    siret=siret,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )

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
        elif configured_recipients:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Échec de l'envoi de l'e-mail d'alerte.",
            )

    if check_status == "insufficient":
        message = "Informations insuffisantes pour lancer une recherche Google."
    elif found:
        if notify_clients:
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
            message = "Une page Google a été trouvée. Aucune notification client n'a été envoyée."
    else:
        message = "Aucune page Google n'a été trouvée pour cet établissement."

    log_event(
        "sync.google.manual_check",
        siret=siret,
        found=found,
        email_sent=email_sent,
        admin_email_sent=admin_email_sent,
        partial_failure=partial_failure,
        configured_recipients=len(configured_recipients),
        admin_recipients=len(admin_emails),
        notify_clients=notify_clients,
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


def build_google_places_export_response(
    *,
    start_date: date | None,
    end_date: date | None,
    mode: Literal["admin", "client"],
    listing_statuses: list[ListingStatus] | QueryInfo | None,
    session: Session,
) -> StreamingResponse:
    """Build the Google Places export and wrap it in a streaming response."""

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

    raw_listing_statuses = listing_statuses.default if isinstance(listing_statuses, QueryInfo) else listing_statuses
    try:
        selected_statuses = normalize_listing_status_filters(raw_listing_statuses)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if not selected_statuses:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Sélectionnez au moins un statut de fiche Google.",
        )
    allowed_statuses = set(selected_statuses)

    stmt = (
        select(models.Establishment)
        .where(
            or_(
                models.Establishment.google_place_url.is_not(None),
                models.Establishment.google_place_id.is_not(None),
            ),
            models.Establishment.google_check_status == "found",
        )
        .order_by(
            models.Establishment.date_creation.asc().nullslast(),
            models.Establishment.name.asc().nullslast(),
        )
    )

    if start_date:
        stmt = stmt.where(models.Establishment.date_creation >= start_date)
    if end_date:
        stmt = stmt.where(models.Establishment.date_creation <= end_date)

    establishments = session.execute(stmt).scalars().all()
    establishments = [
        est for est in establishments if (est.google_check_status or "").lower() == "found"
    ]
    establishments = [
        est
        for est in establishments
        if normalize_listing_age_status(est.google_listing_age_status) in allowed_statuses
    ]
    subcategory_lookup = _load_subcategory_lookup(session) if mode == "client" else None
    workbook_stream = build_google_places_workbook(
        establishments,
        mode=mode,
        subcategory_lookup=subcategory_lookup,
    )
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    filename = f"biz-tracker-google-places-{mode}-{timestamp}.xlsx"

    log_event(
        "export.google.places",
        count=len(establishments),
        filename=filename,
        start_date=start_date.isoformat() if start_date else None,
        end_date=end_date.isoformat() if end_date else None,
        mode=mode,
        listing_statuses=selected_statuses,
    )

    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        workbook_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


def _load_subcategory_lookup(session: Session) -> dict[str, tuple[str | None, str | None]]:
    rows = (
        session.execute(
            select(
                models.NafSubCategory.naf_code,
                models.NafSubCategory.name,
                models.NafCategory.name,
            )
            .join(models.NafCategory, models.NafCategory.id == models.NafSubCategory.category_id)
            .where(models.NafSubCategory.is_active.is_(True))
        ).all()
    )
    lookup: dict[str, tuple[str | None, str | None]] = {}
    for naf_code, sub_name, category_name in rows:
        if not naf_code:
            continue
        token = naf_code.strip().upper()
        if not token:
            continue
        lookup[token] = (category_name, sub_name)
    return lookup
