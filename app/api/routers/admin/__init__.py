"""Admin router exposing all sub-routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import require_admin

from . import alerts, clients, email, establishments, google, naf_categories, stats, sync_runs

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

for subrouter in (
    stats.router,
    google.router,
    alerts.router,
    establishments.router,
    naf_categories.router,
    sync_runs.router,
    email.router,
    clients.router,
):
    router.include_router(subrouter)

__all__ = ["router"]
