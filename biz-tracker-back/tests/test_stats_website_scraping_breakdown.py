from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.api.routers.admin.stats_builder import _build_website_scraping_breakdown
from app.db import models
from app.db.base import Base
from app.utils.dates import utcnow


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kwargs):  # noqa: D401
    return "TEXT"


@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(_type, _compiler, **_kwargs):  # noqa: D401
    return "CHAR(36)"


@contextmanager
def _session_scope():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _mk_establishment(
    *,
    siret: str,
    google_status: str,
    with_website: bool,
    scraped: bool,
    scraped_info: str | None = None,
) -> models.Establishment:
    return models.Establishment(
        siret=siret,
        siren=siret[:9],
        nic=siret[9:14],
        google_check_status=google_status,
        google_contact_website="https://example.test" if with_website else None,
        website_scraped_at=utcnow() if scraped else None,
        website_scraped_emails=scraped_info,
    )


def test_build_website_scraping_breakdown_counts_with_info() -> None:
    with _session_scope() as session:
        session.add_all(
            [
                _mk_establishment(
                    siret="10000000000001",
                    google_status="found",
                    with_website=True,
                    scraped=True,
                    scraped_info="contact@example.test",
                ),
                _mk_establishment(
                    siret="10000000000002",
                    google_status="found",
                    with_website=True,
                    scraped=True,
                    scraped_info=None,
                ),
                _mk_establishment(
                    siret="10000000000003",
                    google_status="found",
                    with_website=True,
                    scraped=False,
                ),
                _mk_establishment(
                    siret="10000000000004",
                    google_status="found",
                    with_website=False,
                    scraped=False,
                ),
                _mk_establishment(
                    siret="10000000000005",
                    google_status="pending",
                    with_website=False,
                    scraped=False,
                ),
            ]
        )
        session.commit()

        breakdown = _build_website_scraping_breakdown(session)

        assert breakdown.with_website == 3
        assert breakdown.without_website == 1
        assert breakdown.scraped == 2
        assert breakdown.scraped_with_info == 1
        assert breakdown.not_scraped == 1
