"""Statistics endpoints for the admin API."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.api.schemas import (
    DashboardMetrics,
    DashboardRunBreakdown,
    GoogleStatusBreakdown,
    StatsSummary,
)
from app.db import models
from app.services.sync_service import SyncService

from .common import serialize_alert, serialize_run

router = APIRouter(tags=["admin"])


@router.get("/stats/summary", response_model=StatsSummary, summary="Synthèse des métriques principales")
def get_stats_summary(session: Session = Depends(get_db_session)) -> StatsSummary:
    total_establishments = session.execute(select(func.count(models.Establishment.siret))).scalar_one()
    total_alerts = session.execute(select(func.count(models.Alert.id))).scalar_one()
    database_size_pretty = session.execute(
        select(func.pg_size_pretty(func.pg_database_size(func.current_database())))
    ).scalar_one()

    service = SyncService()
    target_scope = service.settings.sync.scope_key

    last_run_stmt = (
        select(models.SyncRun)
        .where(models.SyncRun.scope_key == target_scope)
        .order_by(models.SyncRun.started_at.desc())
        .limit(1)
    )
    last_run = session.execute(last_run_stmt).scalar_one_or_none()
    if not last_run:
        fallback_stmt = select(models.SyncRun).order_by(models.SyncRun.started_at.desc()).limit(1)
        last_run = session.execute(fallback_stmt).scalar_one_or_none()

    last_alert_stmt = select(models.Alert).order_by(models.Alert.created_at.desc()).limit(1)
    last_alert = session.execute(last_alert_stmt).scalar_one_or_none()

    last_run_state = session.get(models.SyncState, last_run.scope_key) if last_run else None

    return StatsSummary(
        total_establishments=total_establishments,
        total_alerts=total_alerts,
        last_run=serialize_run(last_run, state=last_run_state),
        last_alert=serialize_alert(last_alert),
        database_size_pretty=database_size_pretty,
    )


@router.get(
    "/stats/dashboard",
    response_model=DashboardMetrics,
    summary="Tableau de bord consolidé des indicateurs journaliers",
)
def get_dashboard_metrics(
    days: int = Query(30, ge=1, le=180, description="Nombre de jours à couvrir pour les séries temporelles."),
    session: Session = Depends(get_db_session),
) -> DashboardMetrics:
    now = datetime.utcnow()
    start_date = now.date() - timedelta(days=days - 1) if days > 1 else now.date()
    since_dt = datetime.combine(start_date, datetime.min.time())

    service = SyncService()
    scope_key = service.settings.sync.scope_key

    last_run_stmt = (
        select(models.SyncRun)
        .where(models.SyncRun.scope_key == scope_key, models.SyncRun.status == "success")
        .order_by(models.SyncRun.started_at.desc())
        .limit(1)
    )
    last_run = session.execute(last_run_stmt).scalar_one_or_none()
    if not last_run:
        fallback_stmt = (
            select(models.SyncRun)
            .where(models.SyncRun.status == "success")
            .order_by(models.SyncRun.started_at.desc())
            .limit(1)
        )
        last_run = session.execute(fallback_stmt).scalar_one_or_none()

    last_run_state = session.get(models.SyncState, last_run.scope_key) if last_run else None
    serialized_last_run = serialize_run(last_run, state=last_run_state)

    latest_run_breakdown = None
    if last_run:
        run_google_rows = (
            session.execute(
                select(
                    models.Establishment.google_check_status,
                    func.count(models.Establishment.siret),
                )
                .where(models.Establishment.created_run_id == last_run.id)
                .group_by(models.Establishment.google_check_status)
            )
            .all()
        )
        run_google_counts = {"found": 0, "not_found": 0, "insufficient": 0, "pending": 0, "other": 0}
        for status, count in run_google_rows:
            key = status or "pending"
            bucket = key if key in run_google_counts else "other"
            run_google_counts[bucket] += int(count or 0)

        alerts_row = session.execute(
            select(
                func.count(models.Alert.id).label("created"),
                func.count(models.Alert.sent_at).label("sent"),
            ).where(models.Alert.run_id == last_run.id)
        ).one()

        latest_run_breakdown = DashboardRunBreakdown(
            run_id=last_run.id,
            started_at=last_run.started_at,
            created_records=last_run.created_records,
            updated_records=last_run.updated_records,
            api_call_count=last_run.api_call_count,
            google_api_call_count=last_run.google_api_call_count,
            google_found=last_run.google_immediate_matched_count,
            google_found_late=last_run.google_late_matched_count,
            google_not_found=run_google_counts["not_found"],
            google_insufficient=run_google_counts["insufficient"],
            google_pending=run_google_counts["pending"],
            google_other=run_google_counts["other"],
            alerts_created=int(alerts_row.created or 0),
            alerts_sent=int(alerts_row.sent or 0),
        )

    runs_rows = (
        session.execute(
            select(
                func.date_trunc("day", models.SyncRun.started_at).label("day"),
                func.sum(models.SyncRun.created_records).label("created"),
                func.sum(models.SyncRun.updated_records).label("updated"),
                func.sum(models.SyncRun.api_call_count).label("api_calls"),
                func.sum(models.SyncRun.google_api_call_count).label("google_api_calls"),
                func.sum(models.SyncRun.google_immediate_matched_count).label("google_immediate"),
                func.sum(models.SyncRun.google_late_matched_count).label("google_late"),
                func.count(models.SyncRun.id).label("run_count"),
            )
            .where(
                models.SyncRun.run_type == "sync",
                models.SyncRun.status == "success",
                models.SyncRun.started_at >= since_dt,
            )
            .group_by("day")
            .order_by("day")
        )
        .all()
    )
    runs_map = {row.day.date(): row for row in runs_rows}

    daily_new_businesses: list[dict[str, object]] = []
    daily_api_calls: list[dict[str, object]] = []
    daily_run_outcomes: list[dict[str, object]] = []
    for index in range(days):
        day = start_date + timedelta(days=index)
        row = runs_map.get(day)
        created = int(row.created or 0) if row else 0
        updated = int(row.updated or 0) if row else 0
        api_calls = int(row.api_calls or 0) if row else 0
        run_count = int(row.run_count or 0) if row else 0
        google_api_calls = int(row.google_api_calls or 0) if row else 0
        daily_run_outcomes.append({"date": day, "created_records": created, "updated_records": updated})
        daily_new_businesses.append({"date": day, "value": created})
        daily_api_calls.append(
            {
                "date": day,
                "value": api_calls,
                "run_count": run_count,
                "google_api_call_count": google_api_calls,
            }
        )

    alerts_rows = (
        session.execute(
            select(
                func.date_trunc("day", models.Alert.created_at).label("day"),
                func.count(models.Alert.id).label("created"),
                func.count(models.Alert.sent_at).label("sent"),
            )
            .where(models.Alert.created_at >= since_dt)
            .group_by("day")
            .order_by("day")
        )
        .all()
    )
    alerts_map = {row.day.date(): row for row in alerts_rows}
    daily_alerts: list[dict[str, object]] = []
    for index in range(days):
        day = start_date + timedelta(days=index)
        row = alerts_map.get(day)
        created = int(row.created or 0) if row else 0
        sent = int(row.sent or 0) if row else 0
        daily_alerts.append({"date": day, "created": created, "sent": sent})

    google_status_rows = (
        session.execute(
            select(
                func.date_trunc("day", models.SyncRun.started_at).label("day"),
                models.Establishment.google_check_status.label("status"),
                func.count(models.Establishment.siret).label("count"),
            )
            .join(models.SyncRun, models.SyncRun.id == models.Establishment.created_run_id)
            .where(
                models.SyncRun.run_type == "sync",
                models.SyncRun.status == "success",
                models.SyncRun.started_at >= since_dt,
            )
            .group_by("day", models.Establishment.google_check_status)
            .order_by("day")
        )
        .all()
    )

    def empty_google_statuses() -> dict[str, int]:
        return {"found": 0, "not_found": 0, "insufficient": 0, "pending": 0, "other": 0}

    google_status_map: dict[date, dict[str, int]] = {}
    for row in google_status_rows:
        day = row.day.date()
        status = row.status or "pending"
        bucket = status if status in {"found", "not_found", "insufficient", "pending"} else "other"
        counts = google_status_map.setdefault(day, empty_google_statuses())
        counts[bucket] += int(row.count or 0)

    daily_google_statuses: list[dict[str, object]] = []
    for index in range(days):
        day = start_date + timedelta(days=index)
        row = runs_map.get(day)
        status_counts = google_status_map.get(day, empty_google_statuses())
        immediate = int(row.google_immediate or 0) if row else 0
        late = int(row.google_late or 0) if row else 0
        if immediate == 0 and status_counts.get("found"):
            immediate = status_counts["found"]
        daily_google_statuses.append(
            {
                "date": day,
                "immediate_matches": immediate,
                "late_matches": late,
                "not_found": status_counts.get("not_found", 0),
                "insufficient": status_counts.get("insufficient", 0),
                "pending": status_counts.get("pending", 0),
                "other": status_counts.get("other", 0),
            }
        )

    global_google_rows = (
        session.execute(
            select(
                models.Establishment.google_check_status,
                func.count(models.Establishment.siret),
            ).group_by(models.Establishment.google_check_status)
        )
        .all()
    )
    global_google_counts = {"found": 0, "not_found": 0, "insufficient": 0, "pending": 0, "other": 0}
    for status, count in global_google_rows:
        key = status or "pending"
        bucket = key if key in global_google_counts else "other"
        global_google_counts[bucket] += int(count or 0)

    establishment_rows = (
        session.execute(
            select(
                models.Establishment.etat_administratif,
                func.count(models.Establishment.siret),
            ).group_by(models.Establishment.etat_administratif)
        )
        .all()
    )
    establishment_breakdown: dict[str, int] = {}
    for status, count in establishment_rows:
        key = status or "INCONNU"
        establishment_breakdown[key] = int(count or 0)

    return DashboardMetrics(
        latest_run=serialized_last_run,
        latest_run_breakdown=latest_run_breakdown,
        daily_new_businesses=daily_new_businesses,
        daily_api_calls=daily_api_calls,
        daily_alerts=daily_alerts,
        daily_run_outcomes=daily_run_outcomes,
        daily_google_statuses=daily_google_statuses,
        google_status_breakdown=GoogleStatusBreakdown(**global_google_counts),
        establishment_status_breakdown=establishment_breakdown,
    )
