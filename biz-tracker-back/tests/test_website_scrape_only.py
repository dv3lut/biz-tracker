from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.db import models
from app.db.base import Base
from app.services.sync.website_scrape_only import load_website_scrape_targets
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
    website: str | None = "https://example.test",
    scraped: bool = False,
    has_info: bool = False,
    naf_code: str | None = "5610A",
) -> models.Establishment:
    return models.Establishment(
        siret=siret,
        siren=siret[:9],
        nic=siret[9:14],
        naf_code=naf_code,
        google_contact_website=website,
        website_scraped_at=utcnow() if scraped else None,
        website_scraped_emails="contact@example.test" if has_info else None,
    )


def test_load_website_scrape_targets_defaults_to_not_scraped() -> None:
    with _session_scope() as session:
        session.add_all(
            [
                _mk_establishment(siret="10000000000001", scraped=False),
                _mk_establishment(siret="10000000000002", scraped=True, has_info=False),
                _mk_establishment(siret="10000000000003", scraped=True, has_info=True),
            ]
        )
        session.commit()

        targets = load_website_scrape_targets(session)

        assert [item.siret for item in targets] == ["10000000000001"]


def test_load_website_scrape_targets_found_only() -> None:
    with _session_scope() as session:
        session.add_all(
            [
                _mk_establishment(siret="10000000000011", scraped=False),
                _mk_establishment(siret="10000000000012", scraped=True, has_info=False),
                _mk_establishment(siret="10000000000013", scraped=True, has_info=True),
            ]
        )
        session.commit()

        targets = load_website_scrape_targets(session, website_statuses=["found"])

        assert [item.siret for item in targets] == ["10000000000013"]


def test_load_website_scrape_targets_no_info_only() -> None:
    with _session_scope() as session:
        session.add_all(
            [
                _mk_establishment(siret="10000000000021", scraped=False),
                _mk_establishment(siret="10000000000022", scraped=True, has_info=False),
                _mk_establishment(siret="10000000000023", scraped=True, has_info=True),
            ]
        )
        session.commit()

        targets = load_website_scrape_targets(session, website_statuses=["no_info"])

        assert [item.siret for item in targets] == ["10000000000022"]


def test_load_website_scrape_targets_scraped_includes_found_and_no_info() -> None:
    with _session_scope() as session:
        session.add_all(
            [
                _mk_establishment(siret="10000000000031", scraped=False),
                _mk_establishment(siret="10000000000032", scraped=True, has_info=False),
                _mk_establishment(siret="10000000000033", scraped=True, has_info=True),
            ]
        )
        session.commit()

        targets = load_website_scrape_targets(session, website_statuses=["scraped"])

        assert {item.siret for item in targets} == {"10000000000032", "10000000000033"}


def test_load_website_scrape_targets_supports_union_statuses() -> None:
    with _session_scope() as session:
        session.add_all(
            [
                _mk_establishment(siret="10000000000041", scraped=False),
                _mk_establishment(siret="10000000000042", scraped=True, has_info=False),
                _mk_establishment(siret="10000000000043", scraped=True, has_info=True),
            ]
        )
        session.commit()

        targets = load_website_scrape_targets(session, website_statuses=["not_scraped", "found"])

        assert {item.siret for item in targets} == {"10000000000041", "10000000000043"}
