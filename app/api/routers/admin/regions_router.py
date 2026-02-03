"""Admin endpoints for regions."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.api.schemas import RegionOut
from app.services.regions_service import list_regions

router = APIRouter(tags=["admin"])


@router.get("/regions", response_model=list[RegionOut], summary="Lister les régions")
def list_regions_endpoint(session: Session = Depends(get_db_session)) -> list[RegionOut]:
    regions = list_regions(session)
    return [RegionOut.model_validate(region) for region in regions]


__all__ = ["router"]
