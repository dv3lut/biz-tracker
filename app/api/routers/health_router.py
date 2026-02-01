"""Health check endpoints."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="", tags=["health"])


@router.get("/health", summary="Application health status")
def health() -> dict[str, str]:
    return {"status": "ok"}