"""LinkedIn-related admin endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.api.schemas import LinkedInCheckResponse, LinkedInDebugResponse
from app.clients.apify_client import ApifyClient, LinkedInSearchInput
from app.config import get_settings
from app.db import models
from app.observability import log_event

router = APIRouter(tags=["admin"])


def _get_company_name(establishment: models.Establishment) -> str:
    """Resolve company name from establishment."""
    return (
        establishment.name
        or establishment.enseigne1
        or establishment.legal_unit_name
        or ""
    )


@router.post(
    "/directors/{director_id}/linkedin-check",
    response_model=LinkedInCheckResponse,
    summary="Relancer une recherche de profil LinkedIn pour un dirigeant",
)
def check_director_linkedin(
    director_id: UUID,
    session: Session = Depends(get_db_session),
) -> LinkedInCheckResponse:
    """
    Recherche un profil LinkedIn pour un dirigeant physique donné.
    Met à jour les champs LinkedIn du dirigeant en base.
    """
    director = session.query(models.Director).filter(
        models.Director.id == director_id
    ).first()

    if not director:
        raise HTTPException(status_code=404, detail="Dirigeant non trouvé")

    if not director.is_physical_person:
        raise HTTPException(
            status_code=400,
            detail="La recherche LinkedIn n'est disponible que pour les personnes physiques"
        )

    establishment = director.establishment
    if not establishment:
        raise HTTPException(status_code=404, detail="Établissement associé non trouvé")

    settings = get_settings()
    if not settings.apify.api_token:
        raise HTTPException(
            status_code=503,
            detail="API Apify non configurée (APIFY__API_TOKEN manquant)"
        )

    company_name = _get_company_name(establishment)
    first_name = director.first_name_for_search
    last_name = director.last_name

    if not first_name or not last_name:
        director.linkedin_check_status = "insufficient"
        director.linkedin_last_checked_at = datetime.now(timezone.utc)
        session.commit()
        return LinkedInCheckResponse(
            director_id=director.id,
            first_names=director.first_names,
            last_name=director.last_name,
            quality=director.quality,
            company_name=company_name,
            linkedin_profile_url=None,
            linkedin_profile_data=None,
            linkedin_check_status="insufficient",
            linkedin_last_checked_at=director.linkedin_last_checked_at,
            message="Données insuffisantes pour la recherche (nom ou prénom manquant)",
        )

    client = ApifyClient(settings.apify)
    search_input = LinkedInSearchInput(
        first_name=first_name,
        last_name=last_name,
        company=company_name,
    )

    log_event(
        "linkedin.debug.search_started",
        director_id=str(director.id),
        siret=establishment.siret,
        first_name=first_name,
        last_name=last_name,
        company=company_name,
    )

    result = client.search_linkedin_profile(search_input)

    now = datetime.now(timezone.utc)

    # If not found with establishment name, retry with legal_unit_name if different
    if not result.success and establishment.legal_unit_name and establishment.legal_unit_name != company_name:
        log_event(
            "linkedin.debug.retry_with_legal_unit",
            director_id=str(director.id),
            legal_unit_name=establishment.legal_unit_name,
        )
        retry_input = LinkedInSearchInput(
            first_name=first_name,
            last_name=last_name,
            company=establishment.legal_unit_name,
        )
        result = client.search_linkedin_profile(retry_input)
        company_name = establishment.legal_unit_name

    if result.success and result.profile_url:
        director.linkedin_profile_url = result.profile_url
        director.linkedin_profile_data = result.profile_data
        director.linkedin_check_status = "found"
        message = "Profil LinkedIn trouvé"
    elif result.error:
        director.linkedin_check_status = "error"
        message = f"Erreur lors de la recherche: {result.error}"
    else:
        director.linkedin_check_status = "not_found"
        message = "Aucun profil LinkedIn trouvé"

    director.linkedin_last_checked_at = now
    session.commit()

    log_event(
        "linkedin.debug.search_completed",
        director_id=str(director.id),
        status=director.linkedin_check_status,
        profile_url=director.linkedin_profile_url,
    )

    return LinkedInCheckResponse(
        director_id=director.id,
        first_names=director.first_names,
        last_name=director.last_name,
        quality=director.quality,
        company_name=company_name,
        linkedin_profile_url=director.linkedin_profile_url,
        linkedin_profile_data=director.linkedin_profile_data,
        linkedin_check_status=director.linkedin_check_status,
        linkedin_last_checked_at=director.linkedin_last_checked_at,
        message=message,
    )


@router.get(
    "/directors/{director_id}/linkedin-debug",
    response_model=LinkedInDebugResponse,
    summary="Déboguer la recherche LinkedIn (sans mettre à jour la base)",
)
def debug_director_linkedin(
    director_id: UUID,
    session: Session = Depends(get_db_session),
) -> LinkedInDebugResponse:
    """
    Effectue une recherche LinkedIn de debug sans modifier la base.
    Retourne les détails de la requête et de la réponse Apify.
    """
    director = session.query(models.Director).filter(
        models.Director.id == director_id
    ).first()

    if not director:
        raise HTTPException(status_code=404, detail="Dirigeant non trouvé")

    if not director.is_physical_person:
        raise HTTPException(
            status_code=400,
            detail="La recherche LinkedIn n'est disponible que pour les personnes physiques"
        )

    establishment = director.establishment
    if not establishment:
        raise HTTPException(status_code=404, detail="Établissement associé non trouvé")

    settings = get_settings()
    if not settings.apify.api_token:
        raise HTTPException(
            status_code=503,
            detail="API Apify non configurée (APIFY__API_TOKEN manquant)"
        )

    company_name = _get_company_name(establishment)
    first_name = director.first_name_for_search or ""
    last_name = director.last_name or ""
    director_name = f"{first_name} {last_name}".strip()

    search_input = LinkedInSearchInput(
        first_name=first_name,
        last_name=last_name,
        company=company_name,
    )

    client = ApifyClient(settings.apify)
    result = client.search_linkedin_profile(search_input)

    retried_with_legal_unit = False

    # Retry with legal_unit_name if not found
    if not result.success and establishment.legal_unit_name and establishment.legal_unit_name != company_name:
        retry_input = LinkedInSearchInput(
            first_name=first_name,
            last_name=last_name,
            company=establishment.legal_unit_name,
        )
        result = client.search_linkedin_profile(retry_input)
        company_name = establishment.legal_unit_name
        retried_with_legal_unit = True

    status = "found" if result.success else ("error" if result.error else "not_found")

    return LinkedInDebugResponse(
        director_id=director.id,
        director_name=director_name,
        company_name=company_name,
        search_input={
            "first_name": search_input.first_name,
            "last_name": search_input.last_name,
            "company": search_input.company,
        },
        apify_response=result.profile_data,
        profile_url=result.profile_url,
        profile_data=result.profile_data,
        status=status,
        error=result.error,
        retried_with_legal_unit=retried_with_legal_unit,
    )
