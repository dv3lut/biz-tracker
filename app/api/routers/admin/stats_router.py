"""Statistics endpoints for the admin API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.api.schemas import DashboardMetrics, StatsSummary
from app.services.sync_service import SyncService

from .stats_builder import build_dashboard_metrics, build_stats_summary

router = APIRouter(tags=["admin"])


@router.get("/stats/summary", response_model=StatsSummary, summary="Synthèse des métriques principales")
def get_stats_summary(session: Session = Depends(get_db_session)) -> StatsSummary:
    """Expose the compact summary for the admin dashboard."""

    return build_stats_summary(session, _resolve_scope_key())


@router.get(
    "/stats/dashboard",
    response_model=DashboardMetrics,
    summary="Tableau de bord consolidé des indicateurs journaliers",
)
def get_dashboard_metrics(
    days: int = Query(30, ge=1, le=180, description="Nombre de jours à couvrir pour les séries temporelles."),
    session: Session = Depends(get_db_session),
) -> DashboardMetrics:
    """Expose the full dashboard metrics (daily series, breakdowns, latest run)."""

    return build_dashboard_metrics(session, days=days, scope_key=_resolve_scope_key())


def _resolve_scope_key() -> str:
    """Centralize how we determine the current sync scope for stats queries."""

    return SyncService().settings.sync.scope_key