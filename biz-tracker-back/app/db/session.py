"""Database engine and session management."""
from __future__ import annotations

from contextlib import contextmanager
import os
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def _initialize() -> None:
    global _engine, _SessionFactory
    if _engine is None or _SessionFactory is None:
        settings = get_settings().database
        if settings.password:
            os.environ["PGPASSWORD"] = settings.password
        _engine = create_engine(
            settings.sqlalchemy_url,
            echo=settings.echo,
            pool_size=settings.pool_size,
            pool_timeout=settings.pool_timeout,
        )
        _SessionFactory = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


def get_engine() -> Engine:
    """Return the configured SQLAlchemy engine."""

    if _engine is None:
        _initialize()
    assert _engine is not None  # for mypy
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return the configured session factory."""

    if _SessionFactory is None:
        _initialize()
    assert _SessionFactory is not None
    return _SessionFactory


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional scope for database interactions."""

    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
