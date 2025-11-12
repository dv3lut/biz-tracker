"""Alert endpoints for the admin API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.api.schemas import AlertOut
from app.db import models

router = APIRouter(tags=["admin"])


@router.get("/alerts/recent", response_model=list[AlertOut], summary="Dernières alertes générées")
def list_recent_alerts(
    limit: int = Query(20, ge=1, le=200),
    session: Session = Depends(get_db_session),
) -> list[AlertOut]:
    stmt = select(models.Alert).order_by(models.Alert.created_at.desc()).limit(limit)
    alerts = session.execute(stmt).scalars().all()
    return [AlertOut.model_validate(alert) for alert in alerts]
