"""Router package exports."""
from __future__ import annotations

from .admin import admin_router
from . import health_router, public_router

__all__ = ["admin_router", "health_router", "public_router"]
