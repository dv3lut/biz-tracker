"""Administrative and monitoring endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, require_admin
from app.api.schemas import (
    AlertOut,
    DeleteRunResult,
    EstablishmentOut,
    StatsSummary,
    SyncRequest,
    SyncRunOut,
    SyncStateOut,
)
from app.db import models
from app.services.sync_service import SyncService

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

def _serialize_run(run: models.SyncRun | None, *, state: models.SyncState | None = None) -> SyncRunOut | None:
    if run is None:
        return None
    enriched = SyncRunOut.model_validate(run)
    total_expected, progress, remaining_seconds, eta = _compute_run_metrics(run, state)
    enriched.total_expected_records = total_expected
    enriched.progress = progress
    enriched.estimated_remaining_seconds = remaining_seconds
    enriched.estimated_completion_at = eta
    return enriched


def _serialize_alert(alert: models.Alert | None) -> AlertOut | None:
    if alert is None:
        return None
    return AlertOut.model_validate(alert)


def _compute_run_metrics(
    run: models.SyncRun,
    state: models.SyncState | None,
) -> tuple[int | None, float | None, float | None, datetime | None]:
    target_raw = run.max_records if run.max_records is not None else (state.last_total if state else None)
    total_expected: int | None
    try:
        total_candidate = int(target_raw) if target_raw is not None else None
    except (TypeError, ValueError):
        total_candidate = None
    total_expected = total_candidate if total_candidate and total_candidate > 0 else None

    progress: float | None = None
    if total_expected:
        progress = min(run.fetched_records / total_expected, 1.0)

    estimated_remaining_seconds: float | None = None
    estimated_completion_at: datetime | None = None
    if run.status == "running" and total_expected and run.fetched_records > 0:
        now = datetime.utcnow()
        elapsed_seconds = max((now - run.started_at).total_seconds(), 0.0)
        if elapsed_seconds > 0:
            rate = run.fetched_records / elapsed_seconds
            if rate > 0:
                remaining = max(total_expected - run.fetched_records, 0)
                estimated_remaining_seconds = remaining / rate if remaining > 0 else 0.0
                estimated_completion_at = now + timedelta(seconds=estimated_remaining_seconds)

    return total_expected, progress, estimated_remaining_seconds, estimated_completion_at


@router.get("/stats/summary", response_model=StatsSummary, summary="Synthèse des métriques principales")
def get_stats_summary(session: Session = Depends(get_db_session)) -> StatsSummary:
    total_establishments = session.execute(select(func.count(models.Establishment.siret))).scalar_one()
    total_alerts = session.execute(select(func.count(models.Alert.id))).scalar_one()
    database_size_pretty = session.execute(
        select(func.pg_size_pretty(func.pg_database_size(func.current_database())))
    ).scalar_one()

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

    last_full_state = session.get(models.SyncState, last_full.scope_key) if last_full else None
    last_incremental_state = session.get(models.SyncState, last_incremental.scope_key) if last_incremental else None

    return StatsSummary(
        total_establishments=total_establishments,
        total_alerts=total_alerts,
        last_full_run=_serialize_run(last_full, state=last_full_state),
        last_incremental_run=_serialize_run(last_incremental, state=last_incremental_state),
        last_alert=_serialize_alert(last_alert),
        database_size_pretty=database_size_pretty,
    )


@router.get("/sync-runs", response_model=list[SyncRunOut], summary="Historique des synchronisations")
def list_sync_runs(
    limit: int = Query(20, ge=1, le=200),
    session: Session = Depends(get_db_session),
) -> list[SyncRunOut]:
    stmt = select(models.SyncRun).order_by(models.SyncRun.started_at.desc()).limit(limit)
    runs = session.execute(stmt).scalars().all()
    states = session.execute(select(models.SyncState)).scalars().all()
    states_by_scope = {state.scope_key: state for state in states}
    return [
        _serialize_run(run, state=states_by_scope.get(run.scope_key))
        for run in runs
    ]


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


@router.delete(
    "/sync-runs/{run_id}",
    response_model=DeleteRunResult,
    summary="Supprimer un run et les données associées",
)
def delete_sync_run(
    run_id: UUID,
    session: Session = Depends(get_db_session),
) -> DeleteRunResult:
    run = session.get(models.SyncRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run introuvable.")

    alerts_deleted = (
        session.query(models.Alert)
        .filter(models.Alert.run_id == run_id)
        .delete(synchronize_session=False)
    )

    establishments_deleted = (
        session.query(models.Establishment)
        .filter(models.Establishment.created_run_id == run_id)
        .delete(synchronize_session=False)
    )

    session.query(models.Establishment).filter(models.Establishment.last_run_id == run_id).update(
        {models.Establishment.last_run_id: None}, synchronize_session=False
    )

    states_reset = (
        session.query(models.SyncState)
        .filter(models.SyncState.last_successful_run_id == run_id)
        .update(
            {
                models.SyncState.last_successful_run_id: None,
                models.SyncState.last_cursor: None,
                models.SyncState.cursor_completed: False,
                models.SyncState.last_synced_at: None,
                models.SyncState.last_total: None,
                models.SyncState.last_treated_max: None,
                models.SyncState.query_checksum: None,
            },
            synchronize_session=False,
        )
    )

    runs_updated = (
        session.query(models.SyncRun)
        .filter(models.SyncRun.resumed_from_run_id == run_id)
        .update({models.SyncRun.resumed_from_run_id: None}, synchronize_session=False)
    )

    session.delete(run)
    session.flush()

    return DeleteRunResult(
        establishments_deleted=establishments_deleted,
        alerts_deleted=alerts_deleted,
        states_reset=states_reset,
        runs_updated=runs_updated,
        sync_run_deleted=True,
    )


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


@router.post("/sync/full", response_model=SyncRunOut, summary="Déclencher une synchronisation complète")
def trigger_full_sync(
    payload: SyncRequest,
    session: Session = Depends(get_db_session),
) -> SyncRunOut:
    run = SyncService().run_full_sync(session, resume=payload.resume, max_records=payload.max_records)
    session.refresh(run)
    state = session.get(models.SyncState, run.scope_key)
    return _serialize_run(run, state=state)


@router.post("/sync/incremental", response_model=SyncRunOut, summary="Déclencher une synchronisation incrémentale")
def trigger_incremental_sync(
    session: Session = Depends(get_db_session),
) -> SyncRunOut:
    run = SyncService().run_incremental_sync(session)
    if run is None:
        raise HTTPException(status_code=status.HTTP_202_ACCEPTED, detail="Aucune mise à jour disponible.")
    session.refresh(run)
    state = session.get(models.SyncState, run.scope_key)
    return _serialize_run(run, state=state)
