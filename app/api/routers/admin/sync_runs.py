"""Synchronization run endpoints for the admin API."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.api.schemas import DeleteRunResult, SyncRequest, SyncRunOut, SyncStateOut
from app.db import models
from app.observability import log_event
from app.services.sync.mode import SyncMode
from app.services.sync_service import SyncService

from .common import serialize_run

router = APIRouter(tags=["admin"])


@router.get("/sync-runs", response_model=list[SyncRunOut], summary="Historique des synchronisations")
def list_sync_runs(
    limit: int = Query(20, ge=1, le=200),
    session: Session = Depends(get_db_session),
) -> list[SyncRunOut]:
    stmt = select(models.SyncRun).order_by(models.SyncRun.started_at.desc()).limit(limit)
    runs = session.execute(stmt).scalars().all()
    states = session.execute(select(models.SyncState)).scalars().all()
    states_by_scope = {state.scope_key: state for state in states}
    return [serialize_run(run, state=states_by_scope.get(run.scope_key)) for run in runs]


@router.get("/sync-state", response_model=list[SyncStateOut], summary="État des curseurs et checkpoints")
def list_sync_state(session: Session = Depends(get_db_session)) -> list[SyncStateOut]:
    states = session.execute(select(models.SyncState).order_by(models.SyncState.scope_key)).scalars().all()
    return [SyncStateOut.model_validate(state) for state in states]


@router.post(
    "/sync",
    response_model=SyncRunOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Déclencher une synchronisation",
)
def trigger_sync_run(
    payload: SyncRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db_session),
) -> SyncRunOut:
    service = SyncService()
    scope_key = service.settings.sync.scope_key
    if service.has_active_run(session, scope_key):
        log_event(
            "sync.run.request_rejected",
            scope_key=scope_key,
            reason="active_run",
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Une synchronisation est déjà en cours.")

    run = service.prepare_sync_run(
        session,
        check_informations=payload.check_for_updates,
        mode=payload.mode,
        replay_for_date=payload.replay_for_date,
        replay_reference=payload.replay_reference,
        target_naf_codes=payload.naf_codes,
        initial_backfill=payload.initial_backfill,
        target_client_ids=payload.target_client_ids,
        notify_admins=payload.notify_admins,
        force_google_replay=payload.force_google_replay,
        google_reset_state=payload.reset_google_state,
    )
    if run is None:
        log_event(
            "sync.run.request_no_updates",
            scope_key=scope_key,
            check_informations=payload.check_for_updates,
            mode=payload.mode.value,
        )
        raise HTTPException(status_code=status.HTTP_202_ACCEPTED, detail="Aucune mise à jour disponible.")

    session.commit()
    session.refresh(run)
    state = session.get(models.SyncState, run.scope_key)

    log_event(
        "sync.run.request_accepted",
        run_id=str(run.id),
        scope_key=scope_key,
        check_informations=payload.check_for_updates,
        mode=payload.mode.value,
        reset_google_state=payload.reset_google_state,
        replay_for_date=payload.replay_for_date.isoformat() if payload.replay_for_date else None,
        replay_reference=payload.replay_reference.value,
        target_client_ids=payload.target_client_ids,
        notify_admins=payload.notify_admins,
        force_google_replay=payload.force_google_replay,
    )

    background_tasks.add_task(
        service.execute_sync_run,
        run.id,
        triggered_by="api",
    )
    return serialize_run(run, state=state)


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
                models.SyncState.last_creation_date: None,
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
