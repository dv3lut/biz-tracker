"""Helper functions for admin statistics endpoints."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.api.schemas import (
    DashboardMetrics,
    DashboardRunBreakdown,
    GoogleListingAgeBreakdown,
    GoogleStatusBreakdown,
    StatsSummary,
)
from app.db import models
from app.utils.dates import utcnow

from .common import serialize_alert, serialize_run


def build_stats_summary(session: Session, scope_key: str) -> StatsSummary:
    """Return the lightweight summary displayed at the top of the dashboard."""

    total_establishments = session.execute(select(func.count(models.Establishment.siret))).scalar_one()
    total_alerts = session.execute(select(func.count(models.Alert.id))).scalar_one()
    database_size_pretty = session.execute(
        select(func.pg_size_pretty(func.pg_database_size(func.current_database())))
    ).scalar_one()

    last_run = _fetch_latest_run(session, scope_key=scope_key, require_success=False)
    if not last_run:
        last_run = _fetch_latest_run(session, scope_key=None, require_success=False)
    last_run_state = session.get(models.SyncState, last_run.scope_key) if last_run else None

    last_alert_stmt = select(models.Alert).order_by(models.Alert.created_at.desc()).limit(1)
    last_alert = session.execute(last_alert_stmt).scalar_one_or_none()

    return StatsSummary(
        total_establishments=total_establishments,
        total_alerts=total_alerts,
        last_run=serialize_run(last_run, state=last_run_state),
        last_alert=serialize_alert(last_alert),
        database_size_pretty=database_size_pretty,
    )


def build_dashboard_metrics(session: Session, *, days: int, scope_key: str) -> DashboardMetrics:
    """Compute the full dashboard payload over the requested window."""

    now = utcnow()
    start_date = now.date() - timedelta(days=days - 1) if days > 1 else now.date()
    since_dt = datetime.combine(start_date, datetime.min.time())

    last_run = _fetch_latest_run(session, scope_key=scope_key, require_success=True)
    if not last_run:
        last_run = _fetch_latest_run(session, scope_key=None, require_success=True)
    last_run_state = session.get(models.SyncState, last_run.scope_key) if last_run else None

    serialized_last_run = serialize_run(last_run, state=last_run_state)
    latest_run_breakdown = _build_latest_run_breakdown(session, last_run)

    runs_map = _build_runs_map(session, since_dt)
    daily_new_businesses, daily_api_calls, daily_run_outcomes = _build_daily_run_series(
        days, start_date, runs_map
    )
    daily_alerts = _build_daily_alert_series(session, since_dt, days, start_date)

    google_status_map = _build_daily_google_status_map(session, since_dt)
    daily_google_statuses = _build_daily_google_statuses(days, start_date, runs_map, google_status_map)

    google_status_breakdown = GoogleStatusBreakdown(**_build_global_google_counts(session))
    listing_age_breakdown = GoogleListingAgeBreakdown(**_build_listing_age_counts(session))
    establishment_status_breakdown = _build_establishment_breakdown(session)
    naf_category_breakdown = _build_naf_category_breakdown(session)

    return DashboardMetrics(
        latest_run=serialized_last_run,
        latest_run_breakdown=latest_run_breakdown,
        daily_new_businesses=daily_new_businesses,
        daily_api_calls=daily_api_calls,
        daily_alerts=daily_alerts,
        daily_run_outcomes=daily_run_outcomes,
        daily_google_statuses=daily_google_statuses,
        google_status_breakdown=google_status_breakdown,
        listing_age_breakdown=listing_age_breakdown,
        establishment_status_breakdown=establishment_status_breakdown,
        naf_category_breakdown=naf_category_breakdown,
    )


def _fetch_latest_run(
    session: Session,
    *,
    scope_key: str | None,
    require_success: bool,
) -> models.SyncRun | None:
    stmt = select(models.SyncRun)
    if scope_key:
        stmt = stmt.where(models.SyncRun.scope_key == scope_key)
    if require_success:
        stmt = stmt.where(models.SyncRun.status == "success")
    stmt = stmt.order_by(models.SyncRun.started_at.desc()).limit(1)
    run = session.execute(stmt).scalar_one_or_none()
    if run or scope_key is None:
        return run
    fallback = select(models.SyncRun)
    if require_success:
        fallback = fallback.where(models.SyncRun.status == "success")
    fallback = fallback.order_by(models.SyncRun.started_at.desc()).limit(1)
    return session.execute(fallback).scalar_one_or_none()


def _build_latest_run_breakdown(
    session: Session,
    last_run: models.SyncRun | None,
) -> DashboardRunBreakdown | None:
    if not last_run:
        return None

    run_google_rows = (
        session.execute(
            select(
                models.Establishment.google_check_status,
                func.count(models.Establishment.siret),
            )
            .where(models.Establishment.created_run_id == last_run.id)
            .group_by(models.Establishment.google_check_status)
        ).all()
    )
    run_google_counts = _empty_google_statuses()
    for status, count in run_google_rows:
        key = status or "pending"
        bucket = key if key in run_google_counts else "other"
        run_google_counts[bucket] += int(count or 0)

    run_listing_rows = (
        session.execute(
            select(
                models.Establishment.google_listing_age_status,
                func.count(models.Establishment.siret),
            )
            .where(
                models.Establishment.created_run_id == last_run.id,
                models.Establishment.google_check_status == "found",
            )
            .group_by(models.Establishment.google_listing_age_status)
        ).all()
    )
    run_listing_counts = {
        "recent_creation": 0,
        "recent_creation_missing_contact": 0,
        "not_recent_creation": 0,
        "unknown": 0,
    }
    for status, count in run_listing_rows:
        key = status or "unknown"
        if key == "buyback_suspected":
            key = "not_recent_creation"
        bucket = key if key in run_listing_counts else "unknown"
        run_listing_counts[bucket] += int(count or 0)

    alerts_row = session.execute(
        select(
            func.count(models.Alert.id).label("created"),
            func.count(models.Alert.sent_at).label("sent"),
        ).where(models.Alert.run_id == last_run.id)
    ).one()

    return DashboardRunBreakdown(
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
        listing_recent=run_listing_counts["recent_creation"],
        listing_recent_missing_contact=run_listing_counts["recent_creation_missing_contact"],
        listing_not_recent=run_listing_counts["not_recent_creation"],
        listing_unknown=run_listing_counts["unknown"],
        alerts_created=int(alerts_row.created or 0),
        alerts_sent=int(alerts_row.sent or 0),
    )


def _build_runs_map(session: Session, since_dt: datetime) -> dict[date, object]:
    rows = (
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
    return {row.day.date(): row for row in rows}


def _build_daily_run_series(
    days: int,
    start_date: date,
    runs_map: dict[date, object],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    daily_new_businesses: list[dict[str, object]] = []
    daily_api_calls: list[dict[str, object]] = []
    daily_run_outcomes: list[dict[str, object]] = []
    for day in _iter_days(start_date, days):
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
    return daily_new_businesses, daily_api_calls, daily_run_outcomes


def _build_daily_alert_series(
    session: Session,
    since_dt: datetime,
    days: int,
    start_date: date,
) -> list[dict[str, object]]:
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
    for day in _iter_days(start_date, days):
        row = alerts_map.get(day)
        created = int(row.created or 0) if row else 0
        sent = int(row.sent or 0) if row else 0
        daily_alerts.append({"date": day, "created": created, "sent": sent})
    return daily_alerts


def _build_daily_google_status_map(session: Session, since_dt: datetime) -> dict[date, dict[str, int]]:
    rows = (
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
    google_status_map: dict[date, dict[str, int]] = {}
    for row in rows:
        day = row.day.date()
        status = row.status or "pending"
        bucket = status if status in {"found", "not_found", "insufficient", "pending"} else "other"
        counts = google_status_map.setdefault(day, _empty_google_statuses())
        counts[bucket] += int(row.count or 0)
    return google_status_map


def _build_daily_google_statuses(
    days: int,
    start_date: date,
    runs_map: dict[date, object],
    google_status_map: dict[date, dict[str, int]],
) -> list[dict[str, object]]:
    series: list[dict[str, object]] = []
    for day in _iter_days(start_date, days):
        row = runs_map.get(day)
        status_counts = google_status_map.get(day, _empty_google_statuses())
        immediate = int(row.google_immediate or 0) if row else 0
        late = int(row.google_late or 0) if row else 0
        if immediate == 0 and status_counts.get("found"):
            immediate = status_counts["found"]
        series.append(
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
    return series


def _build_global_google_counts(session: Session) -> dict[str, int]:
    rows = session.execute(
        select(
            models.Establishment.google_check_status,
            func.count(models.Establishment.siret),
        ).group_by(models.Establishment.google_check_status)
    ).all()
    counts = _empty_google_statuses()
    for status, count in rows:
        key = status or "pending"
        bucket = key if key in counts else "other"
        counts[bucket] += int(count or 0)
    return counts


def _build_listing_age_counts(session: Session) -> dict[str, int]:
    rows = session.execute(
        select(
            models.Establishment.google_listing_age_status,
            func.count(models.Establishment.siret),
        )
        .where(models.Establishment.google_check_status == "found")
        .group_by(models.Establishment.google_listing_age_status)
    ).all()
    counts = {
        "recent_creation": 0,
        "recent_creation_missing_contact": 0,
        "not_recent_creation": 0,
        "unknown": 0,
    }
    for status, count in rows:
        key = status or "unknown"
        if key == "buyback_suspected":
            key = "not_recent_creation"
        bucket = key if key in counts else "unknown"
        counts[bucket] += int(count or 0)
    return counts


def _build_establishment_breakdown(session: Session) -> dict[str, int]:
    rows = session.execute(
        select(
            models.Establishment.etat_administratif,
            func.count(models.Establishment.siret),
        ).group_by(models.Establishment.etat_administratif)
    ).all()
    breakdown: dict[str, int] = {}
    for status, count in rows:
        key = status or "INCONNU"
        breakdown[key] = int(count or 0)
    return breakdown


def _build_naf_category_breakdown(session: Session) -> list[dict[str, object]]:
    rows = (
        session.execute(
            select(
                models.NafCategory.id.label("category_id"),
                models.NafCategory.name.label("category_name"),
                models.NafSubCategory.id.label("subcategory_id"),
                models.NafSubCategory.name.label("subcategory_name"),
                models.NafSubCategory.naf_code.label("naf_code"),
                func.count(models.Establishment.siret).label("establishment_count"),
                func.sum(
                    case((models.Establishment.google_check_status == "found", 1), else_=0)
                ).label("google_found_count"),
                func.sum(
                    case((models.Establishment.google_check_status == "not_found", 1), else_=0)
                ).label("google_not_found_count"),
                func.sum(
                    case((models.Establishment.google_check_status == "insufficient", 1), else_=0)
                ).label("google_insufficient_count"),
                func.sum(
                    case((models.Establishment.google_check_status == "pending", 1), else_=0)
                ).label("google_pending_count"),
                func.sum(
                    case((models.Establishment.google_check_status == "type_mismatch", 1), else_=0)
                ).label("google_type_mismatch_count"),
                func.sum(
                    case(
                        (
                            models.Establishment.google_check_status.notin_(
                                ["found", "not_found", "insufficient", "pending", "type_mismatch"]
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("google_other_count"),
                func.sum(
                    case(
                        (
                            (models.Establishment.google_check_status == "found")
                            & (models.Establishment.google_listing_age_status == "recent_creation"),
                            1,
                        ),
                        else_=0,
                    )
                ).label("listing_recent_count"),
                func.sum(
                    case(
                        (
                            (models.Establishment.google_check_status == "found")
                            & (
                                models.Establishment.google_listing_age_status
                                == "recent_creation_missing_contact"
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("listing_recent_missing_contact_count"),
                func.sum(
                    case(
                        (
                            (models.Establishment.google_check_status == "found")
                            & (
                                models.Establishment.google_listing_age_status.in_(
                                    ["not_recent_creation", "buyback_suspected"]
                                )
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("listing_not_recent_count"),
            )
            .join(models.NafSubCategory, models.NafSubCategory.category_id == models.NafCategory.id)
            .outerjoin(
                models.Establishment,
                func.upper(models.Establishment.naf_code) == func.upper(models.NafSubCategory.naf_code),
            )
            .where(models.NafSubCategory.is_active.is_(True))
            .group_by(
                models.NafCategory.id,
                models.NafCategory.name,
                models.NafSubCategory.id,
                models.NafSubCategory.name,
                models.NafSubCategory.naf_code,
            )
            .order_by(models.NafCategory.name.asc(), models.NafSubCategory.name.asc())
        )
        .all()
    )

    breakdown: list[dict[str, object]] = []
    category_map: dict[object, dict[str, object]] = {}
    for row in rows:
        category_id = row.category_id
        sub_count = int(row.establishment_count or 0)
        google_found = int(row.google_found_count or 0)
        google_not_found = int(row.google_not_found_count or 0)
        google_insufficient = int(row.google_insufficient_count or 0)
        google_pending = int(row.google_pending_count or 0)
        google_other = int(row.google_other_count or 0)
        google_type_mismatch = int(row.google_type_mismatch_count or 0)
        listing_recent = int(row.listing_recent_count or 0)
        listing_recent_missing_contact = int(row.listing_recent_missing_contact_count or 0)
        listing_not_recent = int(row.listing_not_recent_count or 0)
        listing_unknown = max(
            0,
            google_found - listing_recent - listing_recent_missing_contact - listing_not_recent,
        )

        category_entry = category_map.get(category_id)
        if not category_entry:
            category_entry = {
                "category_id": category_id,
                "name": row.category_name,
                "total_establishments": 0,
                "subcategories": [],
            }
            category_map[category_id] = category_entry
            breakdown.append(category_entry)

        category_entry["total_establishments"] = int(category_entry["total_establishments"]) + sub_count
        category_entry.setdefault("subcategories", []).append(
            {
                "subcategory_id": row.subcategory_id,
                "naf_code": row.naf_code,
                "name": row.subcategory_name,
                "establishment_count": sub_count,
                "google_found": google_found,
                "google_not_found": google_not_found,
                "google_insufficient": google_insufficient,
                "google_pending": google_pending,
                "google_type_mismatch": google_type_mismatch,
                "google_other": google_other,
                "listing_recent": listing_recent,
                "listing_recent_missing_contact": listing_recent_missing_contact,
                "listing_not_recent": listing_not_recent,
                "listing_unknown": listing_unknown,
            }
        )

    return breakdown


def _empty_google_statuses() -> dict[str, int]:
    return {"found": 0, "not_found": 0, "insufficient": 0, "pending": 0, "other": 0}


def _iter_days(start_date: date, days: int) -> Iterable[date]:
    for index in range(days):
        yield start_date + timedelta(days=index)
