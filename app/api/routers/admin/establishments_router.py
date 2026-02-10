"""Establishment endpoints for the admin API."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.params import Query as QueryParam
from sqlalchemy import exists, func, not_, or_
from sqlalchemy.orm import Query as SAQuery, Session, selectinload

from app.api.dependencies import get_db_session
from app.api.schemas import EstablishmentDetailOut, EstablishmentListOut, EstablishmentOut
from app.db import models
from app.utils.regions import get_department_codes_for_region_codes, normalize_department_codes

router = APIRouter(tags=["admin"])


def _build_establishments_query(
    session: Session,
    *,
    search: str | None,
    naf_code: str | None,
    naf_codes: list[str] | None,
    department_codes: list[str] | None,
    region_codes: list[str] | None,
    added_from: date | None,
    added_to: date | None,
    google_check_status: str | None,
    is_individual: bool | None,
    has_linkedin: bool | None,
    linkedin_statuses: list[str] | None,
) -> SAQuery:
    if isinstance(region_codes, QueryParam):
        region_codes = None
    if isinstance(department_codes, QueryParam):
        department_codes = None
    if isinstance(linkedin_statuses, QueryParam):
        linkedin_statuses = None

    query = session.query(models.Establishment).filter(models.Establishment.etat_administratif == "A")

    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                models.Establishment.siret.ilike(pattern),
                models.Establishment.name.ilike(pattern),
                models.Establishment.code_postal.ilike(pattern),
            )
        )

    cleaned_naf_codes: list[str] = []
    if naf_code:
        cleaned = naf_code.strip().replace(" ", "").replace(".", "").upper()
        if cleaned:
            cleaned_naf_codes.append(cleaned)
    if naf_codes:
        for code in naf_codes:
            cleaned = code.strip().replace(" ", "").replace(".", "").upper()
            if cleaned:
                cleaned_naf_codes.append(cleaned)
    if cleaned_naf_codes:
        normalized_db_naf = func.replace(
            func.replace(func.upper(func.trim(models.Establishment.naf_code)), ".", ""),
            " ",
            "",
        )
        query = query.filter(normalized_db_naf.in_(cleaned_naf_codes))

    cleaned_departments: list[str] = []
    if region_codes:
        cleaned_departments.extend(get_department_codes_for_region_codes(region_codes))
    if department_codes:
        cleaned_departments.extend(department_codes)
    if cleaned_departments:
        region_filters = []
        for dept in normalize_department_codes(cleaned_departments):
            token = dept.strip().upper()
            if not token:
                continue
            if token in {"2A", "2B"}:
                region_filters.append(models.Establishment.code_commune.ilike(f"{token}%"))
                region_filters.append(models.Establishment.code_postal.ilike("20%"))
            elif len(token) == 3 and token.isdigit():
                region_filters.append(models.Establishment.code_commune.ilike(f"{token}%"))
                region_filters.append(models.Establishment.code_postal.ilike(f"{token}%"))
            elif len(token) == 2 and token.isdigit():
                region_filters.append(models.Establishment.code_commune.ilike(f"{token}%"))
                region_filters.append(models.Establishment.code_postal.ilike(f"{token}%"))
        if region_filters:
            query = query.filter(or_(*region_filters))

    if added_from is not None:
        start = datetime.combine(added_from, time.min)
        query = query.filter(models.Establishment.first_seen_at >= start)
    if added_to is not None:
        end_exclusive = datetime.combine(added_to, time.min) + timedelta(days=1)
        query = query.filter(models.Establishment.first_seen_at < end_exclusive)

    if google_check_status:
        cleaned_status = google_check_status.strip().lower()
        normalized_status = func.lower(func.trim(models.Establishment.google_check_status))
        if cleaned_status == "other":
            query = query.filter(
                or_(
                    models.Establishment.google_check_status.is_(None),
                    normalized_status.notin_(["found", "not_found", "insufficient", "pending"]),
                )
            )
        elif cleaned_status == "pending":
            query = query.filter(
                or_(
                    models.Establishment.google_check_status.is_(None),
                    normalized_status == "pending",
                )
            )
        else:
            query = query.filter(normalized_status == cleaned_status)

    if is_individual is not None:
        normalized_filter = models.Establishment.categorie_juridique.ilike("1%")
        if is_individual:
            query = query.filter(normalized_filter)
        else:
            query = query.filter(or_(models.Establishment.categorie_juridique.is_(None), not_(normalized_filter)))

    if has_linkedin is True:
        linkedin_exists = exists().where(
            models.Director.establishment_siret == models.Establishment.siret,
            models.Director.linkedin_check_status == "found",
        )
        query = query.filter(linkedin_exists)
    elif has_linkedin is False:
        linkedin_exists = exists().where(
            models.Director.establishment_siret == models.Establishment.siret,
            models.Director.linkedin_check_status == "found",
        )
        query = query.filter(not_(linkedin_exists))

    if linkedin_statuses:
        allowed_statuses = {"pending", "found", "not_found", "error", "insufficient", "skipped_nd"}
        cleaned_statuses = [status.strip().lower() for status in linkedin_statuses if status and status.strip()]
        selected_statuses = [status for status in cleaned_statuses if status in allowed_statuses]
        if selected_statuses:
            status_conditions = []
            normalized_status = func.lower(func.trim(models.Director.linkedin_check_status))
            if "pending" in selected_statuses:
                status_conditions.append(or_(models.Director.linkedin_check_status.is_(None), normalized_status == "pending"))
            other_statuses = sorted({status for status in selected_statuses if status != "pending"})
            if other_statuses:
                status_conditions.append(normalized_status.in_(other_statuses))
            if status_conditions:
                linkedin_exists = exists().where(
                    models.Director.establishment_siret == models.Establishment.siret,
                    or_(*status_conditions),
                )
                query = query.filter(linkedin_exists)

    return query


@router.get(
    "/establishments",
    response_model=EstablishmentListOut,
    summary="Lister les établissements actifs",
)
def list_establishments(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: str | None = Query(None, alias="q", description="Filtre sur SIRET, nom ou code postal"),
    naf_code: str | None = Query(None, description="Filtrer sur un code NAF (ex: 56.10A)."),
    naf_codes: list[str] | None = Query(
        None,
        description="Filtrer sur plusieurs codes NAF (répéter le paramètre, ex: naf_codes=56.10A&naf_codes=47.11D).",
    ),
    department_codes: list[str] | None = Query(
        None,
        description="Filtrer sur des départements (ex: department_codes=75&department_codes=33).",
    ),
    region_codes: list[str] | None = Query(
        None,
        description="Filtrer sur des régions (ex: region_codes=IDF&region_codes=NAQ).",
    ),
    added_from: date | None = Query(
        None,
        description=(
            "Filtrer sur la date d'ajout (première vue) à partir de cette date incluse (YYYY-MM-DD). "
            "Peut être utilisé seul (borne ouverte) ou combiné avec added_to. "
            "Pour une date exacte, utiliser la même date pour added_from et added_to."
        ),
    ),
    added_to: date | None = Query(
        None,
        description=(
            "Filtrer sur la date d'ajout (première vue) jusqu'à cette date incluse (YYYY-MM-DD). "
            "Peut être utilisé seul (borne ouverte) ou combiné avec added_from. "
            "Pour une date exacte, utiliser la même date pour added_from et added_to."
        ),
    ),
    google_check_status: str | None = Query(
        None,
        description=(
            "Filtrer par statut Google (mêmes statuts que le dashboard): found, not_found, insufficient, pending, other. "
            "Aucun filtre si vide."
        ),
    ),
    is_individual: bool | None = Query(None, description="Filtrer par entreprise individuelle (true/false)."),
    has_linkedin: bool | None = Query(
        None,
        description="Filtrer les établissements avec au moins un dirigeant LinkedIn trouvé (true/false).",
    ),
    linkedin_statuses: list[str] | None = Query(
        None,
        description=(
            "Filtrer par statuts LinkedIn des dirigeants (répéter linkedin_statuses=pending&linkedin_statuses=error)."
        ),
    ),
    session: Session = Depends(get_db_session),
) -> EstablishmentListOut:
    query = _build_establishments_query(
        session,
        search=search,
        naf_code=naf_code,
        naf_codes=naf_codes,
        department_codes=department_codes,
        region_codes=region_codes,
        added_from=added_from,
        added_to=added_to,
        google_check_status=google_check_status,
        is_individual=is_individual,
        has_linkedin=has_linkedin,
        linkedin_statuses=linkedin_statuses,
    )
    if hasattr(query, "with_entities"):
        total = query.with_entities(func.count(models.Establishment.siret)).scalar() or 0
    elif hasattr(query, "count"):
        total = query.count() or 0
    else:
        total = 0
    establishments = (
        query.options(selectinload(models.Establishment.directors))
        .order_by(
            models.Establishment.date_creation.desc(),
            models.Establishment.last_seen_at.desc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )
    return EstablishmentListOut(
        total=total,
        items=[EstablishmentOut.model_validate(item) for item in establishments],
    )


@router.get(
    "/establishments/{siret}",
    response_model=EstablishmentDetailOut,
    summary="Consulter le détail complet d'un établissement",
)
def get_establishment_detail(
    siret: str,
    session: Session = Depends(get_db_session),
) -> EstablishmentDetailOut:
    entity = (
        session.query(models.Establishment)
        .options(selectinload(models.Establishment.directors))
        .filter(models.Establishment.siret == siret)
        .first()
    )
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Établissement introuvable.")
    return EstablishmentDetailOut.model_validate(entity)


@router.delete(
    "/establishments/{siret}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer un établissement",
)
def delete_establishment(
    siret: str,
    session: Session = Depends(get_db_session),
) -> None:
    entity = session.get(models.Establishment, siret)
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Établissement introuvable.")
    session.delete(entity)
    session.flush()