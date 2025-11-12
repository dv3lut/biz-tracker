"""Establishment endpoints for the admin API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.api.schemas import EstablishmentDetailOut, EstablishmentOut
from app.db import models

router = APIRouter(tags=["admin"])


@router.get(
    "/establishments",
    response_model=list[EstablishmentOut],
    summary="Lister les établissements actifs",
)
def list_establishments(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: str | None = Query(None, alias="q", description="Filtre sur SIRET, nom ou code postal"),
    session: Session = Depends(get_db_session),
) -> list[EstablishmentOut]:
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
    establishments = (
        query.order_by(
            models.Establishment.date_creation.desc(),
            models.Establishment.last_seen_at.desc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [EstablishmentOut.model_validate(item) for item in establishments]


@router.get(
    "/establishments/{siret}",
    response_model=EstablishmentDetailOut,
    summary="Consulter le détail complet d'un établissement",
)
def get_establishment_detail(
    siret: str,
    session: Session = Depends(get_db_session),
) -> EstablishmentDetailOut:
    entity = session.get(models.Establishment, siret)
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
