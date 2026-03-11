"""Tests for scraped contacts extraction and persistence (without labels)."""
from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.db import models
from app.db.base import Base
from app.services.google_business.google_business_service import _persist_scraped_contacts
from app.services.website_scraper.crawlers import _merge_contacts
from app.services.website_scraper.extractors import extract_emails, extract_phones
from app.services.website_scraper.scraper_service import ContactItem, WebsiteScrapingResult
from app.utils.dates import utcnow


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kwargs):
    return "TEXT"


@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(_type, _compiler, **_kwargs):
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


class TestExtractPhones:
    def test_mobile_and_national_formats(self) -> None:
        text = "Mob: 06 12 34 56 78 / Fixe: 01 23 45 67 89"
        mobiles, nationals, internationals = extract_phones(text)
        assert "+33612345678" in mobiles
        assert "+33123456789" in nationals
        assert internationals == []

    def test_dedup_and_exclude_mobile_from_national(self) -> None:
        text = "06 12 34 56 78\n+33 6 12 34 56 78"
        mobiles, nationals, internationals = extract_phones(text)
        assert mobiles == ["+33612345678"]
        assert nationals == []
        assert internationals == []

    def test_extracts_international(self) -> None:
        text = "International: +44 20 1234 5678"
        mobiles, nationals, internationals = extract_phones(text)
        assert mobiles == []
        assert nationals == []
        assert internationals == ["+442012345678"]


class TestExtractEmails:
    def test_extract_emails_unique(self) -> None:
        text = "Contact: a@b.com puis A@B.COM et x@y.fr"
        emails = extract_emails(text)
        lowered = {email.lower() for email in emails}
        assert lowered == {"a@b.com", "x@y.fr"}


class TestMergeContacts:
    def test_merge_contacts_set_dedup(self) -> None:
        target = {"+33612345678"}
        _merge_contacts(target, ["+33612345678", "+33798765432"])
        assert target == {"+33612345678", "+33798765432"}


class TestContactItemAndResult:
    def test_contact_item_value(self) -> None:
        item = ContactItem("+33612345678")
        assert item.value == "+33612345678"

    def test_result_pipe_separated_properties(self) -> None:
        result = WebsiteScrapingResult(
            mobile_phones=[ContactItem("+33612345678"), ContactItem("+33798765432")],
            international_phones=[ContactItem("+442012345678")],
            emails=[ContactItem("a@b.com")],
        )
        assert result.mobile_phones_str == "+33612345678|+33798765432"
        assert result.international_phones_str == "+442012345678"
        assert result.emails_str == "a@b.com"
        assert result.national_phones_str is None

    def test_all_contacts_property(self) -> None:
        result = WebsiteScrapingResult(
            mobile_phones=[ContactItem("+33612345678")],
            national_phones=[ContactItem("+33123456789")],
            international_phones=[ContactItem("+442012345678")],
            emails=[ContactItem("a@b.com")],
        )
        contacts = result.all_contacts
        assert len(contacts) == 4
        assert ("mobile_phone", "+33612345678") in contacts
        assert ("national_phone", "+33123456789") in contacts
        assert ("international_phone", "+442012345678") in contacts
        assert ("email", "a@b.com") in contacts


class TestPersistScrapedContacts:
    def test_persist_inserts_contacts_without_label(self) -> None:
        with _session_scope() as session:
            est = models.Establishment(
                siret="12345678901234",
                siren="123456789",
                nic="01234",
                google_check_status="pending",
            )
            session.add(est)
            session.flush()

            result = WebsiteScrapingResult(
                mobile_phones=[ContactItem("+33612345678")],
                emails=[ContactItem("a@b.com")],
            )
            now = utcnow()
            _persist_scraped_contacts(session, est.siret, result, now)
            session.flush()

            contacts = session.query(models.ScrapedContact).filter_by(establishment_siret=est.siret).all()
            assert len(contacts) == 2
            assert {c.contact_type for c in contacts} == {"mobile_phone", "email"}
            assert all(c.value for c in contacts)

    def test_persist_replaces_existing_contacts(self) -> None:
        with _session_scope() as session:
            est = models.Establishment(
                siret="12345678901234",
                siren="123456789",
                nic="01234",
                google_check_status="pending",
            )
            session.add(est)
            session.flush()

            now = utcnow()
            _persist_scraped_contacts(
                session,
                est.siret,
                WebsiteScrapingResult(mobile_phones=[ContactItem("+33612345678")]),
                now,
            )
            session.flush()
            assert session.query(models.ScrapedContact).filter_by(establishment_siret=est.siret).count() == 1

            _persist_scraped_contacts(
                session,
                est.siret,
                WebsiteScrapingResult(emails=[ContactItem("x@y.com"), ContactItem("a@b.com")]),
                now,
            )
            session.flush()

            contacts = session.query(models.ScrapedContact).filter_by(establishment_siret=est.siret).all()
            assert len(contacts) == 2
            assert all(c.contact_type == "email" for c in contacts)

    def test_persist_empty_result_clears(self) -> None:
        with _session_scope() as session:
            est = models.Establishment(
                siret="12345678901234",
                siren="123456789",
                nic="01234",
                google_check_status="pending",
            )
            session.add(est)
            session.flush()

            now = utcnow()
            _persist_scraped_contacts(
                session,
                est.siret,
                WebsiteScrapingResult(mobile_phones=[ContactItem("+33612345678")]),
                now,
            )
            session.flush()
            assert session.query(models.ScrapedContact).filter_by(establishment_siret=est.siret).count() == 1

            _persist_scraped_contacts(session, est.siret, WebsiteScrapingResult(), now)
            session.flush()
            assert session.query(models.ScrapedContact).filter_by(establishment_siret=est.siret).count() == 0

    def test_persist_truncates_contact_value_to_512(self) -> None:
        with _session_scope() as session:
            est = models.Establishment(
                siret="12345678901234",
                siren="123456789",
                nic="01234",
                google_check_status="pending",
            )
            session.add(est)
            session.flush()

            now = utcnow()
            _persist_scraped_contacts(
                session,
                est.siret,
                WebsiteScrapingResult(emails=[ContactItem("a" * 700)]),
                now,
            )
            session.flush()

            contact = session.query(models.ScrapedContact).filter_by(establishment_siret=est.siret).one()
            assert len(contact.value) == 512
