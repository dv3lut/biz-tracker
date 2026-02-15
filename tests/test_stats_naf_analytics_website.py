from __future__ import annotations

from contextlib import contextmanager
from datetime import date, timedelta

from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.api.routers.admin.stats_builder import build_naf_analytics
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

    @event.listens_for(engine, "connect")
    def _register_to_char(dbapi_connection, _connection_record):  # type: ignore[no-untyped-def]
        dbapi_connection.create_function(
            "to_char",
            2,
            lambda value, _fmt: str(value)[:10] if value is not None else None,
        )

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_build_naf_analytics_includes_website_scraped_with_info() -> None:
    now = utcnow()
    with _session_scope() as session:
        session.add_all(
            [
                models.Establishment(
                    siret="20000000000001",
                    siren="200000000",
                    nic="00001",
                    name="Alpha",
                    naf_code="5610A",
                    first_seen_at=now,
                    last_seen_at=now,
                    google_check_status="found",
                    google_contact_website="https://alpha.test",
                    website_scraped_at=now,
                    website_scraped_emails="contact@alpha.test",
                ),
                models.Establishment(
                    siret="20000000000002",
                    siren="200000000",
                    nic="00002",
                    name="Beta",
                    naf_code="5610A",
                    first_seen_at=now,
                    last_seen_at=now,
                    google_check_status="found",
                    google_contact_website="https://beta.test",
                    website_scraped_at=now,
                ),
                models.Establishment(
                    siret="20000000000003",
                    siren="200000000",
                    nic="00003",
                    name="Gamma",
                    naf_code="5610A",
                    first_seen_at=now,
                    last_seen_at=now,
                    google_check_status="type_mismatch",
                    google_contact_website="https://gamma.test",
                    website_scraped_at=now,
                    website_scraped_emails="contact@gamma.test",
                ),
            ]
        )
        session.commit()

        start = now.date() - timedelta(days=1)
        end = now.date() + timedelta(days=1)
        payload = build_naf_analytics(
            session,
            start_date=start,
            end_date=end,
            granularity="day",
            aggregation="naf",
            category_id=None,
            naf_code=None,
        )

        assert payload.global_totals.website_with_website == 2
        assert payload.global_totals.website_scraped == 2
        assert payload.global_totals.website_scraped_with_info == 1

        assert len(payload.items) == 1
        item = payload.items[0]
        assert item.totals.website_with_website == 2
        assert item.totals.website_scraped == 2
        assert item.totals.website_scraped_with_info == 1
