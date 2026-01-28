"""Alert endpoints for the admin API."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import get_db_session
from app.api.schemas import AlertOut
from app.db import models
from app.observability import log_event
from app.services.export_service import build_alerts_workbook

router = APIRouter(tags=["admin"])


@router.get("/alerts/recent", response_model=list[AlertOut], summary="Dernières alertes générées")
def list_recent_alerts(
    limit: int = Query(20, ge=1, le=200),
    session: Session = Depends(get_db_session),
) -> list[AlertOut]:
    stmt = select(models.Alert).order_by(models.Alert.created_at.desc()).limit(limit)
    alerts = session.execute(stmt).scalars().all()
    return [AlertOut.model_validate(alert) for alert in alerts]


@router.get(
    "/alerts/export",
    summary="Exporter les alertes par date de création",
    response_class=StreamingResponse,
)
def export_alerts_by_creation_date(
    days: int = Query(30, ge=1, le=365, description="Fenêtre glissante basée sur la date de création d'établissement."),
    session: Session = Depends(get_db_session),
) -> StreamingResponse:
    cutoff_date = date.today() - timedelta(days=days)
    stmt = (
        select(models.Alert)
        .join(models.Establishment)
        .options(selectinload(models.Alert.establishment), selectinload(models.Alert.run))
        .where(
            models.Establishment.date_creation.isnot(None),
            models.Establishment.date_creation >= cutoff_date,
        )
        .order_by(models.Establishment.date_creation.desc(), models.Alert.created_at.desc())
    )
    alerts = session.execute(stmt).scalars().all()
    workbook = build_alerts_workbook(alerts)

    filename = f"biz-tracker-alerts-last-{days}-days.xlsx"
    log_event(
        "export.alerts.creation_date",
        days=days,
        cutoff=cutoff_date.isoformat(),
        alert_count=len(alerts),
    )

    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )