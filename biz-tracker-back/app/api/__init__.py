"""FastAPI application factory."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.config import get_settings
from app.logging_config import configure_logging


def _build_lifespan():
    @asynccontextmanager
    async def _lifespan(_: FastAPI):
        from app.services.sync_scheduler import SyncScheduler

        sync_scheduler = SyncScheduler()
        sync_scheduler.start()
        try:
            yield
        finally:
            sync_scheduler.stop()

    return _lifespan


def create_app() -> FastAPI:
    """Instantiate the FastAPI application with all routers."""

    from .middlewares.access_log_middleware import AccessLogMiddleware
    from .middlewares.rate_limit_middleware import RateLimitMiddleware, RateLimitPolicy
    from .routers import admin_router, health_router, public_router

    settings = get_settings()
    logger = logging.getLogger(__name__)
    configure_logging()
    # Log only the CORS origins to confirm env parsing without leaking secrets.
    logger.info("CORS allowed_origins (parsed) = %s", settings.api.allowed_origins)
    docs_url = "/docs" if settings.api.docs_enabled else None
    redoc_url = "/redoc" if settings.api.docs_enabled else None
    app = FastAPI(
        title="Sirene Restaurant Watcher",
        version="1.0.0",
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url="/openapi.json" if settings.api.docs_enabled else None,
        lifespan=_build_lifespan(),
    )

    if settings.api.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.api.allowed_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Global inbound throttling.
    # Keep public endpoints stricter (anti-spam), and keep the rest permissive
    # to avoid impacting admin usage.
    app.add_middleware(AccessLogMiddleware, log_admin_requests=settings.api.log_admin_requests)
    app.add_middleware(
        RateLimitMiddleware,
        default_policy=RateLimitPolicy(max_per_second=50, max_per_minute=1200),
        public_policy=RateLimitPolicy(max_per_second=5, max_per_minute=30),
    )

    app.include_router(health_router.router)
    app.include_router(admin_router.router)
    app.include_router(public_router.router)

    return app
