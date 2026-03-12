"""Google-related admin endpoints."""
from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.api.schemas import (
    GoogleCheckStatusListOut,
    GoogleFindPlaceDebugResponse,
    GoogleRetryConfigOut,
    GoogleRetryConfigUpdate,
    ListingStatus,
    ManualGoogleCheckResponse,
    ManualWebsiteScrapeResponse,
)
from app.db import models
from app.observability import log_event
from app.services.google.google_retry_config import (
    ensure_google_retry_config,
    load_runtime_google_retry_config,
    serialize_google_retry_config,
    update_google_retry_config,
)

from .google_handlers import (
    build_google_places_export_response,
    debug_google_find_place_action,
    manual_google_check_action,
    manual_website_scrape_action,
)

router = APIRouter(tags=["admin"])


@router.post(
    "/establishments/{siret}/google-check",
    response_model=ManualGoogleCheckResponse,
    summary="Relancer une vérification Google Places et (optionnel) notifier les clients",
)
def manual_google_check(
    siret: str,
    notify_clients: bool = Query(
        True,
        alias="notify_clients",
        description="Envoie également un e-mail aux clients abonnés lorsque la fiche est trouvée.",
    ),
    session: Session = Depends(get_db_session),
) -> ManualGoogleCheckResponse:
    return manual_google_check_action(
        siret=siret,
        notify_clients=notify_clients,
        session=session,
    )


@router.get(
    "/establishments/{siret}/google-find-place",
    response_model=GoogleFindPlaceDebugResponse,
    summary="Déboguer la requête Find Place (candidats bruts + scoring)",
)
def debug_google_find_place(
    siret: str,
    session: Session = Depends(get_db_session),
) -> GoogleFindPlaceDebugResponse:
    return debug_google_find_place_action(siret=siret, session=session)


@router.post(
    "/establishments/{siret}/website-scrape",
    response_model=ManualWebsiteScrapeResponse,
    summary="Relancer un scraping manuel du site web lié à la fiche Google",
)
def manual_website_scrape(
    siret: str,
    session: Session = Depends(get_db_session),
) -> ManualWebsiteScrapeResponse:
    return manual_website_scrape_action(siret=siret, session=session)


@router.get(
    "/google/check-statuses",
    response_model=GoogleCheckStatusListOut,
    summary="Lister les statuts Google actuellement présents en base",
)
def list_google_check_statuses(session: Session = Depends(get_db_session)) -> GoogleCheckStatusListOut:
    stmt = select(func.lower(func.trim(models.Establishment.google_check_status))).distinct()
    statuses = session.execute(stmt).scalars().all()
    cleaned = {status.strip() for status in statuses if isinstance(status, str) and status.strip()}
    cleaned.add("pending")
    return GoogleCheckStatusListOut(statuses=sorted(cleaned))


@router.get(
    "/google/places-export",
    summary="Exporter les établissements enrichis via Google Places",
)
def export_google_places(
    start_date: date | None = None,
    end_date: date | None = None,
    mode: Literal["admin", "client"] = Query("admin", alias="mode"),
    listing_statuses: list[ListingStatus] | None = Query(
        None,
        description="Liste de statuts de fiche Google à inclure dans l'export.",
    ),
    naf_codes: list[str] | None = Query(
        None,
        description="Filtrer par codes NAF (ex: 5610A). Si vide, tous les codes sont inclus.",
    ),
    session: Session = Depends(get_db_session),
) -> StreamingResponse:
    return build_google_places_export_response(
        start_date=start_date,
        end_date=end_date,
        mode=mode,
        listing_statuses=listing_statuses,
        naf_codes=naf_codes,
        session=session,
    )


@router.get(
    "/google/retry-config",
    response_model=GoogleRetryConfigOut,
    summary="Récupérer la configuration des relances Google",
)
def get_google_retry_config(session: Session = Depends(get_db_session)) -> GoogleRetryConfigOut:
    record = ensure_google_retry_config(session)
    payload_dict = serialize_google_retry_config(record)
    return GoogleRetryConfigOut(**payload_dict)


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
        retry_missing_contact_enabled=payload.retry_missing_contact_enabled,
        retry_missing_contact_frequency_days=payload.retry_missing_contact_frequency_days,
        retry_no_website_frequency_days=payload.retry_no_website_frequency_days,
    )
    session.flush()
    payload_dict = serialize_google_retry_config(record)
    runtime = load_runtime_google_retry_config(session)
    log_event(
        "google.retry_config.updated",
        retry_weekdays=list(runtime.retry_weekdays),
        default_rules=len(runtime.default_rules),
        micro_rules=len(runtime.micro_rules),
        retry_missing_contact_enabled=runtime.retry_missing_contact_enabled,
        retry_missing_contact_frequency_days=runtime.retry_missing_contact_frequency_days,
    )
    return GoogleRetryConfigOut(**payload_dict)