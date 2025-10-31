"""FastAPI application factory."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.logging_config import configure_logging

from .routers import admin, health


def create_app() -> FastAPI:
    """Instantiate the FastAPI application with all routers."""

    settings = get_settings()
    configure_logging()
    docs_url = "/docs" if settings.api.docs_enabled else None
    redoc_url = "/redoc" if settings.api.docs_enabled else None
    app = FastAPI(
        title="Sirene Restaurant Watcher",
        version="1.0.0",
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url="/openapi.json" if settings.api.docs_enabled else None,
    )

    if settings.api.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.api.allowed_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(health.router)
    app.include_router(admin.router)

    return app


app = create_app()
