"""Statistics endpoints for the admin API."""
from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.api.schemas import DashboardMetrics, NafAnalyticsResponse, StatsSummary
from app.services.sync_service import SyncService

from .stats_builder import build_dashboard_metrics, build_naf_analytics, build_stats_summary

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


@router.get(
    "/stats/naf-analytics",
    response_model=NafAnalyticsResponse,
    summary="Statistiques détaillées par NAF/catégorie avec séries temporelles",
)
def get_naf_analytics(
    start_date: date | None = Query(None, description="Date de début de la fenêtre (défaut: 30j en arrière)."),
    end_date: date | None = Query(None, description="Date de fin de la fenêtre (défaut: aujourd'hui)."),
    granularity: Literal["day", "week", "month"] = Query(
        "week", description="Granularité temporelle: day, week, month."
    ),
    aggregation: Literal["naf", "category", "subcategory"] = Query(
        "category", description="Mode d'agrégation: naf (brut), category, subcategory."
    ),
    category_id: str | None = Query(None, description="Filtrer sur une catégorie (UUID)."),
    naf_code: str | None = Query(None, description="Filtrer sur un code NAF précis."),
    session: Session = Depends(get_db_session),
) -> NafAnalyticsResponse:
    """Retourne les proportions et séries temporelles par code NAF ou catégorie.

    Permet d'analyser la conversion de l'API SIRENE vers Google/LinkedIn et alertes.
    """
    return build_naf_analytics(
        session,
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
        aggregation=aggregation,
        category_id=category_id,
        naf_code=naf_code,
    )


def _resolve_scope_key() -> str:
    """Centralize how we determine the current sync scope for stats queries."""

    return SyncService().settings.sync.scope_key