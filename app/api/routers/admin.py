"""Administrative and monitoring endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_admin
from app.api.schemas import AlertOut, StatsSummary, SyncRequest, SyncRunOut, SyncStateOut
from app.db import models
from app.services.sync_service import SyncService

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

def _serialize_run(run: models.SyncRun | None) -> SyncRunOut | None:
    if run is None:
        return None
    return SyncRunOut.model_validate(run)


def _serialize_alert(alert: models.Alert | None) -> AlertOut | None:
    if alert is None:
        return None
    return AlertOut.model_validate(alert)


@router.get("/stats/summary", response_model=StatsSummary, summary="Synthèse des métriques principales")
def get_stats_summary(session: Session = Depends(get_db_session)) -> StatsSummary:
    total_establishments = session.execute(select(func.count(models.Establishment.siret))).scalar_one()
    total_alerts = session.execute(select(func.count(models.Alert.id))).scalar_one()

    last_full_stmt = (
        select(models.SyncRun)
        .where(models.SyncRun.run_type == "full")
        .order_by(models.SyncRun.started_at.desc())
        .limit(1)
    )
    last_incremental_stmt = (
        select(models.SyncRun)
        .where(models.SyncRun.run_type == "incremental")
        .order_by(models.SyncRun.started_at.desc())
        .limit(1)
    )
    last_alert_stmt = select(models.Alert).order_by(models.Alert.created_at.desc()).limit(1)

    last_full = session.execute(last_full_stmt).scalar_one_or_none()
    last_incremental = session.execute(last_incremental_stmt).scalar_one_or_none()
    last_alert = session.execute(last_alert_stmt).scalar_one_or_none()

    return StatsSummary(
        total_establishments=total_establishments,
        total_alerts=total_alerts,
        last_full_run=_serialize_run(last_full),
        last_incremental_run=_serialize_run(last_incremental),
        last_alert=_serialize_alert(last_alert),
    )


@router.get("/sync-runs", response_model=list[SyncRunOut], summary="Historique des synchronisations")
def list_sync_runs(
    limit: int = Query(20, ge=1, le=200),
    session: Session = Depends(get_db_session),
) -> list[SyncRunOut]:
    stmt = select(models.SyncRun).order_by(models.SyncRun.started_at.desc()).limit(limit)
    runs = session.execute(stmt).scalars().all()
    return [SyncRunOut.model_validate(run) for run in runs]


@router.get("/sync-state", response_model=list[SyncStateOut], summary="État des curseurs et checkpoints")
def list_sync_state(session: Session = Depends(get_db_session)) -> list[SyncStateOut]:
    states = session.execute(select(models.SyncState).order_by(models.SyncState.scope_key)).scalars().all()
    return [SyncStateOut.model_validate(state) for state in states]


@router.get("/alerts/recent", response_model=list[AlertOut], summary="Dernières alertes générées")
def list_recent_alerts(
    limit: int = Query(20, ge=1, le=200),
    session: Session = Depends(get_db_session),
) -> list[AlertOut]:
    stmt = select(models.Alert).order_by(models.Alert.created_at.desc()).limit(limit)
    alerts = session.execute(stmt).scalars().all()
    return [AlertOut.model_validate(alert) for alert in alerts]


@router.post("/sync/full", response_model=SyncRunOut, summary="Déclencher une synchronisation complète")
def trigger_full_sync(
    payload: SyncRequest,
    session: Session = Depends(get_db_session),
) -> SyncRunOut:
    run = SyncService().run_full_sync(session, resume=payload.resume)
    session.refresh(run)
    return SyncRunOut.model_validate(run)


@router.post("/sync/incremental", response_model=SyncRunOut, summary="Déclencher une synchronisation incrémentale")
def trigger_incremental_sync(
    session: Session = Depends(get_db_session),
) -> SyncRunOut:
    run = SyncService().run_incremental_sync(session)
    if run is None:
        raise HTTPException(status_code=status.HTTP_202_ACCEPTED, detail="Aucune mise à jour disponible.")
    session.refresh(run)
    return SyncRunOut.model_validate(run)
