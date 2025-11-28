"""Google-related admin endpoints."""
from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.api.schemas import (
    GoogleRetryConfigOut,
    GoogleRetryConfigUpdate,
    ListingStatus,
    ManualGoogleCheckResponse,
)
from app.observability import log_event
from app.services.google_retry_config import (
    ensure_google_retry_config,
    load_runtime_google_retry_config,
    serialize_google_retry_config,
    update_google_retry_config,
)

from .google_handlers import (
    build_google_places_export_response,
    manual_google_check_action,
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
    session: Session = Depends(get_db_session),
) -> StreamingResponse:
    return build_google_places_export_response(
        start_date=start_date,
        end_date=end_date,
        mode=mode,
        listing_statuses=listing_statuses,
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
