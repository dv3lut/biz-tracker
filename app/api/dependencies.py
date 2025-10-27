"""Reusable FastAPI dependency definitions."""
from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.session import get_session_factory


def get_db_session() -> Generator[Session, None, None]:
    """Provide a transactional SQLAlchemy session per request."""

    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
        session.commit()
    finally:
        session.close()


def get_settings_dependency() -> Settings:
    """Expose cached settings through dependency injection."""

    return get_settings()


def require_admin(
    request: Request,
    settings: Settings = Depends(get_settings_dependency),
) -> None:
    """Ensure the request contains the expected admin token header."""

    header_name = settings.api.admin_header_name
    provided_token = request.headers.get(header_name)
    if not provided_token or provided_token != settings.api.admin_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin token invalid or missing.")