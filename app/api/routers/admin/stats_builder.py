"""Helper functions for admin statistics endpoints."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable, Literal
from uuid import UUID

from sqlalchemy import String as SqlString, case, func, select
from sqlalchemy.orm import Session

from app.api.schemas import (
    DashboardMetrics,
    DashboardRunBreakdown,
    GoogleListingAgeBreakdown,
    GoogleStatusBreakdown,
    NafAnalyticsItem,
    NafAnalyticsResponse,
    NafAnalyticsTimePoint,
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
    linkedin_subq = (
        select(
            models.Director.establishment_siret,
            func.sum(case((models.Director.linkedin_check_status == "found", 1), else_=0)).label(
                "linkedin_found"
            ),
        )
        .group_by(models.Director.establishment_siret)
        .subquery()
    )
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
                    case((models.Establishment.categorie_juridique.ilike("1%"), 1), else_=0)
                ).label("individual_count"),
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
                func.coalesce(func.sum(linkedin_subq.c.linkedin_found), 0).label("linkedin_found_count"),
            )
            .join(models.NafCategorySubCategory, models.NafCategorySubCategory.category_id == models.NafCategory.id)
            .join(
                models.NafSubCategory,
                models.NafSubCategory.id == models.NafCategorySubCategory.subcategory_id,
            )
            .outerjoin(
                models.Establishment,
                func.upper(models.Establishment.naf_code) == func.upper(models.NafSubCategory.naf_code),
            )
            .outerjoin(linkedin_subq, linkedin_subq.c.establishment_siret == models.Establishment.siret)
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
        individual_count = int(row.individual_count or 0)
        non_individual_count = max(0, sub_count - individual_count)
        google_found = int(row.google_found_count or 0)
        google_not_found = int(row.google_not_found_count or 0)
        google_insufficient = int(row.google_insufficient_count or 0)
        google_pending = int(row.google_pending_count or 0)
        google_other = int(row.google_other_count or 0)
        google_type_mismatch = int(row.google_type_mismatch_count or 0)
        listing_recent = int(row.listing_recent_count or 0)
        listing_recent_missing_contact = int(row.listing_recent_missing_contact_count or 0)
        listing_not_recent = int(row.listing_not_recent_count or 0)
        linkedin_found = int(row.linkedin_found_count or 0)
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
                "individual_establishments": 0,
                "non_individual_establishments": 0,
                "subcategories": [],
            }
            category_map[category_id] = category_entry
            breakdown.append(category_entry)

        category_entry["total_establishments"] = int(category_entry["total_establishments"]) + sub_count
        category_entry["individual_establishments"] = (
            int(category_entry["individual_establishments"]) + individual_count
        )
        category_entry["non_individual_establishments"] = (
            int(category_entry["non_individual_establishments"]) + non_individual_count
        )
        category_entry.setdefault("subcategories", []).append(
            {
                "subcategory_id": row.subcategory_id,
                "naf_code": row.naf_code,
                "name": row.subcategory_name,
                "establishment_count": sub_count,
                "individual_establishments": individual_count,
                "non_individual_establishments": non_individual_count,
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
                "linkedin_found": linkedin_found,
            }
        )

    return breakdown


def _empty_google_statuses() -> dict[str, int]:
    return {"found": 0, "not_found": 0, "insufficient": 0, "pending": 0, "other": 0}


def _iter_days(start_date: date, days: int) -> Iterable[date]:
    for index in range(days):
        yield start_date + timedelta(days=index)


# ---------------------------------------------------------------------------
# NAF Analytics builder
# ---------------------------------------------------------------------------


def build_naf_analytics(
    session: Session,
    *,
    start_date: date | None,
    end_date: date | None,
    granularity: Literal["day", "week", "month"],
    aggregation: Literal["naf", "category", "subcategory"],
    category_id: str | None,
    naf_code: str | None,
) -> NafAnalyticsResponse:
    """Build NAF analytics with time series for proportions dashboard."""
    now = utcnow()
    if end_date is None:
        end_date = now.date()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    since_dt = datetime.combine(start_date, datetime.min.time())
    until_dt = datetime.combine(end_date + timedelta(days=1), datetime.min.time())

    # Determine period format based on granularity
    if granularity == "day":
        period_format = "YYYY-MM-DD"
    elif granularity == "week":
        period_format = "IYYY-\"W\"IW"
    else:  # month
        period_format = "YYYY-MM"

    # Build base query with period grouping
    period_expr = func.to_char(models.Establishment.first_seen_at, period_format).label("period")

    # Build group by key based on aggregation
    if aggregation == "naf":
        group_key = func.upper(models.Establishment.naf_code).label("group_key")
        group_name = models.Establishment.naf_libelle.label("group_name")
        group_naf_code = models.Establishment.naf_code.label("group_naf_code")
    elif aggregation == "category":
        group_key = func.cast(models.NafCategory.id, SqlString).label("group_key")
        group_name = models.NafCategory.name.label("group_name")
        group_naf_code = func.cast(None, SqlString).label("group_naf_code")
    else:  # subcategory
        group_key = func.cast(models.NafSubCategory.id, SqlString).label("group_key")
        group_name = models.NafSubCategory.name.label("group_name")
        group_naf_code = models.NafSubCategory.naf_code.label("group_naf_code")

    # Common aggregation columns
    total_fetched = func.count(models.Establishment.siret).label("total_fetched")
    non_diffusible = func.sum(
        case((models.Establishment.google_check_status == "non_diffusible", 1), else_=0)
    ).label("non_diffusible")
    insufficient_info = func.sum(
        case((models.Establishment.google_check_status == "insufficient", 1), else_=0)
    ).label("insufficient_info")
    google_found = func.sum(
        case((models.Establishment.google_check_status == "found", 1), else_=0)
    ).label("google_found")
    google_not_found = func.sum(
        case((models.Establishment.google_check_status == "not_found", 1), else_=0)
    ).label("google_not_found")
    google_pending = func.sum(
        case((models.Establishment.google_check_status == "pending", 1), else_=0)
    ).label("google_pending")
    listing_recent = func.sum(
        case(
            (
                (models.Establishment.google_check_status == "found")
                & (models.Establishment.google_listing_age_status == "recent_creation"),
                1,
            ),
            else_=0,
        )
    ).label("listing_recent")
    listing_recent_missing_contact = func.sum(
        case(
            (
                (models.Establishment.google_check_status == "found")
                & (models.Establishment.google_listing_age_status == "recent_creation_missing_contact"),
                1,
            ),
            else_=0,
        )
    ).label("listing_recent_missing_contact")
    listing_not_recent = func.sum(
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
    ).label("listing_not_recent")
    individual_count = func.sum(
        case((models.Establishment.categorie_juridique.ilike("1%"), 1), else_=0)
    ).label("individual_count")

    # LinkedIn stats via directors
    linkedin_subq = (
        select(
            models.Director.establishment_siret,
            func.count(models.Director.id).label("total_directors"),
            func.sum(case((models.Director.linkedin_check_status == "found", 1), else_=0)).label("li_found"),
            func.sum(case((models.Director.linkedin_check_status == "not_found", 1), else_=0)).label("li_not_found"),
            func.sum(case((models.Director.linkedin_check_status == "pending", 1), else_=0)).label("li_pending"),
            func.sum(case((models.Director.linkedin_check_status == "skipped_nd", 1), else_=0)).label("li_skipped_nd"),
        )
        .group_by(models.Director.establishment_siret)
        .subquery()
    )

    linkedin_found_expr = func.coalesce(func.sum(linkedin_subq.c.li_found), 0).label("linkedin_found")
    linkedin_not_found_expr = func.coalesce(func.sum(linkedin_subq.c.li_not_found), 0).label("linkedin_not_found")
    linkedin_pending_expr = func.coalesce(func.sum(linkedin_subq.c.li_pending), 0).label("linkedin_pending")
    linkedin_total_directors_expr = func.coalesce(
        func.sum(linkedin_subq.c.total_directors), 0
    ).label("linkedin_total_directors")
    linkedin_skipped_nd_expr = func.coalesce(func.sum(linkedin_subq.c.li_skipped_nd), 0).label("linkedin_skipped_nd")

    # Alerts count per establishment
    alerts_subq = (
        select(
            models.Alert.siret,
            func.count(models.Alert.id).label("alert_count"),
        )
        .where(models.Alert.created_at >= since_dt, models.Alert.created_at < until_dt)
        .group_by(models.Alert.siret)
        .subquery()
    )
    alerts_created_expr = func.coalesce(func.sum(alerts_subq.c.alert_count), 0).label("alerts_created")

    # Build main query
    base_query = select(
        period_expr,
        group_key,
        group_name,
        group_naf_code,
        total_fetched,
        non_diffusible,
        insufficient_info,
        google_found,
        google_not_found,
        google_pending,
        listing_recent,
        listing_recent_missing_contact,
        listing_not_recent,
        individual_count,
        linkedin_found_expr,
        linkedin_not_found_expr,
        linkedin_pending_expr,
        linkedin_total_directors_expr,
        linkedin_skipped_nd_expr,
        alerts_created_expr,
    ).where(
        models.Establishment.first_seen_at >= since_dt,
        models.Establishment.first_seen_at < until_dt,
    )

    # Join with NAF tables if aggregating by category or subcategory
    if aggregation in ("category", "subcategory"):
        base_query = base_query.outerjoin(
            models.NafSubCategory,
            func.upper(models.Establishment.naf_code) == func.upper(models.NafSubCategory.naf_code),
        ).outerjoin(
            models.NafCategorySubCategory,
            models.NafSubCategory.id == models.NafCategorySubCategory.subcategory_id,
        ).outerjoin(
            models.NafCategory,
            models.NafCategorySubCategory.category_id == models.NafCategory.id,
        )

    # Join with linkedin subquery
    base_query = base_query.outerjoin(
        linkedin_subq, linkedin_subq.c.establishment_siret == models.Establishment.siret
    )

    # Join with alerts subquery
    base_query = base_query.outerjoin(
        alerts_subq, alerts_subq.c.siret == models.Establishment.siret
    )

    # Apply filters
    if category_id:
        try:
            cat_uuid = UUID(category_id)
            base_query = base_query.where(models.NafCategory.id == cat_uuid)
        except ValueError:
            pass

    if naf_code:
        base_query = base_query.where(
            func.upper(models.Establishment.naf_code) == naf_code.upper().replace(".", "")
        )

    # Group by period and aggregation key
    base_query = base_query.group_by(
        period_expr, group_key, group_name, group_naf_code
    ).order_by(period_expr, group_name)

    rows = session.execute(base_query).all()

    creation_series = _build_creation_date_series(session, start_date, end_date, period_format)
    creation_series_by_key = _build_creation_date_series_by_group(
        session,
        start_date=start_date,
        end_date=end_date,
        period_format=period_format,
        aggregation=aggregation,
        category_id=category_id,
        naf_code=naf_code,
    )
    creation_periods = _iter_periods(start_date, end_date, period_format)

    # Build result structure
    items_map: dict[str, NafAnalyticsItem] = {}
    global_totals = _empty_analytics_point("")
    periods_set: set[str] = set()

    for row in rows:
        period = row.period or "unknown"
        key = row.group_key or "unknown"
        periods_set.add(period)

        if key not in items_map:
            items_map[key] = NafAnalyticsItem(
                id=key,
                code=row.group_naf_code,
                name=row.group_name or "Inconnu",
                totals=_empty_analytics_point("total"),
                time_series=[],
                creation_series=[
                    {"period": period, "count": creation_series_by_key.get(key, {}).get(period, 0)}
                    for period in creation_periods
                ],
            )

        item = items_map[key]
        point = NafAnalyticsTimePoint(
            period=period,
            total_fetched=int(row.total_fetched or 0),
            non_diffusible=int(row.non_diffusible or 0),
            insufficient_info=int(row.insufficient_info or 0),
            google_found=int(row.google_found or 0),
            google_not_found=int(row.google_not_found or 0),
            google_pending=int(row.google_pending or 0),
            listing_recent=int(row.listing_recent or 0),
            listing_recent_missing_contact=int(row.listing_recent_missing_contact or 0),
            listing_not_recent=int(row.listing_not_recent or 0),
            individual_count=int(row.individual_count or 0),
            linkedin_found=int(row.linkedin_found or 0),
            linkedin_not_found=int(row.linkedin_not_found or 0),
            linkedin_pending=int(row.linkedin_pending or 0),
            linkedin_total_directors=int(row.linkedin_total_directors or 0),
            linkedin_skipped_nd=int(row.linkedin_skipped_nd or 0),
            alerts_created=int(row.alerts_created or 0),
        )
        item.time_series.append(point)

        # Accumulate totals
        _accumulate_point(item.totals, point)
        _accumulate_point(global_totals, point)

    # Sort time series within each item
    for item in items_map.values():
        item.time_series.sort(key=lambda p: p.period)

    return NafAnalyticsResponse(
        granularity=granularity,
        start_date=start_date,
        end_date=end_date,
        aggregation=aggregation,
        items=list(items_map.values()),
        global_totals=global_totals,
        creation_series=creation_series,
    )


def _build_creation_date_series(
    session: Session,
    start_date: date,
    end_date: date,
    period_format: str,
) -> list[dict[str, object]]:
    period_expr = func.to_char(models.Establishment.date_creation, period_format).label("period")
    rows = (
        session.execute(
            select(
                period_expr,
                func.count(models.Establishment.siret).label("count"),
            )
            .where(
                models.Establishment.date_creation.is_not(None),
                models.Establishment.date_creation >= start_date,
                models.Establishment.date_creation <= end_date,
            )
            .group_by(period_expr)
            .order_by(period_expr)
        ).all()
    )

    counts_map = {row.period: int(row.count or 0) for row in rows if row.period}
    periods = _iter_periods(start_date, end_date, period_format)
    return [{"period": period, "count": counts_map.get(period, 0)} for period in periods]


def _build_creation_date_series_by_group(
    session: Session,
    *,
    start_date: date,
    end_date: date,
    period_format: str,
    aggregation: Literal["naf", "category", "subcategory"],
    category_id: str | None,
    naf_code: str | None,
) -> dict[str, dict[str, int]]:
    period_expr = func.to_char(models.Establishment.date_creation, period_format).label("period")

    if aggregation == "naf":
        group_key = func.upper(models.Establishment.naf_code).label("group_key")
    elif aggregation == "category":
        group_key = func.cast(models.NafCategory.id, SqlString).label("group_key")
    else:
        group_key = func.cast(models.NafSubCategory.id, SqlString).label("group_key")

    stmt = (
        select(
            period_expr,
            group_key,
            func.count(models.Establishment.siret).label("count"),
        )
        .where(
            models.Establishment.date_creation.is_not(None),
            models.Establishment.date_creation >= start_date,
            models.Establishment.date_creation <= end_date,
        )
        .group_by(period_expr, group_key)
        .order_by(period_expr)
    )

    if aggregation in ("category", "subcategory"):
        stmt = stmt.outerjoin(
            models.NafSubCategory,
            func.upper(models.Establishment.naf_code) == func.upper(models.NafSubCategory.naf_code),
        ).outerjoin(
            models.NafCategorySubCategory,
            models.NafSubCategory.id == models.NafCategorySubCategory.subcategory_id,
        ).outerjoin(
            models.NafCategory,
            models.NafCategorySubCategory.category_id == models.NafCategory.id,
        )

    if category_id:
        try:
            cat_uuid = UUID(category_id)
            stmt = stmt.where(models.NafCategory.id == cat_uuid)
        except ValueError:
            pass

    if naf_code:
        stmt = stmt.where(
            func.upper(models.Establishment.naf_code) == naf_code.upper().replace(".", "")
        )

    rows = session.execute(stmt).all()
    series_map: dict[str, dict[str, int]] = {}
    for row in rows:
        key = row.group_key or "unknown"
        period = row.period
        if not period:
            continue
        series_map.setdefault(key, {})[period] = int(row.count or 0)
    return series_map


def _iter_periods(start_date: date, end_date: date, period_format: str) -> list[str]:
    periods: list[str] = []
    if period_format == "YYYY-MM-DD":
        cursor = start_date
        while cursor <= end_date:
            periods.append(cursor.isoformat())
            cursor += timedelta(days=1)
        return periods

    if period_format == "IYYY-\"W\"IW":
        cursor = start_date
        while cursor <= end_date:
            iso_year, iso_week, _ = cursor.isocalendar()
            label = f"{iso_year}-W{iso_week:02d}"
            if not periods or periods[-1] != label:
                periods.append(label)
            cursor += timedelta(days=7)
        return periods

    cursor = start_date.replace(day=1)
    end_marker = end_date.replace(day=1)
    while cursor <= end_marker:
        periods.append(f"{cursor.year}-{cursor.month:02d}")
        year = cursor.year + (1 if cursor.month == 12 else 0)
        month = 1 if cursor.month == 12 else cursor.month + 1
        cursor = cursor.replace(year=year, month=month)
    return periods


def _empty_analytics_point(period: str) -> NafAnalyticsTimePoint:
    return NafAnalyticsTimePoint(
        period=period,
        total_fetched=0,
        non_diffusible=0,
        insufficient_info=0,
        google_found=0,
        google_not_found=0,
        google_pending=0,
        listing_recent=0,
        listing_recent_missing_contact=0,
        listing_not_recent=0,
        individual_count=0,
        linkedin_found=0,
        linkedin_not_found=0,
        linkedin_pending=0,
        linkedin_total_directors=0,
        linkedin_skipped_nd=0,
        alerts_created=0,
    )


def _accumulate_point(target: NafAnalyticsTimePoint, source: NafAnalyticsTimePoint) -> None:
    target.total_fetched += source.total_fetched
    target.non_diffusible += source.non_diffusible
    target.insufficient_info += source.insufficient_info
    target.google_found += source.google_found
    target.google_not_found += source.google_not_found
    target.google_pending += source.google_pending
    target.listing_recent += source.listing_recent
    target.listing_recent_missing_contact += source.listing_recent_missing_contact
    target.listing_not_recent += source.listing_not_recent
    target.individual_count += source.individual_count
    target.linkedin_found += source.linkedin_found
    target.linkedin_not_found += source.linkedin_not_found
    target.linkedin_pending += source.linkedin_pending
    target.linkedin_total_directors += source.linkedin_total_directors
    target.linkedin_skipped_nd += source.linkedin_skipped_nd
    target.alerts_created += source.alerts_created
