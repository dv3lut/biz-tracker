"""Admin router exposing all sub-routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import require_admin

from . import (
    alerts_router,
    clients_router,
    email_router,
    establishments_router,
    google_router,
    naf_categories_router,
    regions_router,
    stats_router,
    stripe_router,
    sync_runs_router,
    tools_router,
)

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

for subrouter in (
    stats_router.router,
    google_router.router,
    alerts_router.router,
    establishments_router.router,
    naf_categories_router.router,
    regions_router.router,
    sync_runs_router.router,
    email_router.router,
    clients_router.router,
    stripe_router.router,
    tools_router.router,
):
    router.include_router(subrouter)

__all__ = ["router"]