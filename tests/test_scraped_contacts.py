"""Tests for label extraction, ContactItem, and ScrapedContact persistence."""
from __future__ import annotations

from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.db import models
from app.db.base import Base
from app.services.website_scraper.extractors import (
    _extract_preceding_label,
    _validate_label,
    extract_emails_with_labels,
    extract_phones_with_labels,
)
from app.services.website_scraper.crawlers import _merge_contacts
from app.services.website_scraper.scraper_service import ContactItem, WebsiteScrapingResult
from app.services.google_business.google_business_service import _persist_scraped_contacts
from app.utils.dates import utcnow


# ──────────────────────────────────────────────────────────────────────────────
# SQLite dialect helpers (same pattern as other DB tests)
# ──────────────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────────────
# _validate_label
# ──────────────────────────────────────────────────────────────────────────────


class TestValidateLabel:
    def test_valid_simple_label(self) -> None:
        assert _validate_label("Réservation") is True

    def test_valid_multi_word_label(self) -> None:
        assert _validate_label("Service commercial") is True

    def test_rejects_empty(self) -> None:
        assert _validate_label("") is False

    def test_rejects_none_like(self) -> None:
        assert _validate_label("") is False

    def test_rejects_too_short(self) -> None:
        assert _validate_label("A") is False

    def test_rejects_too_long(self) -> None:
        assert _validate_label("x" * 81) is False

    def test_rejects_only_digits(self) -> None:
        assert _validate_label("12345") is False

    def test_rejects_url(self) -> None:
        assert _validate_label("https://example.com/contact") is False

    def test_rejects_email_like(self) -> None:
        assert _validate_label("info@example.com") is False

    def test_rejects_mostly_digits(self) -> None:
        assert _validate_label("123 456 789a") is False

    def test_rejects_html_tags(self) -> None:
        assert _validate_label("<div class='phone'>") is False

    def test_rejects_generic_standalone_tel(self) -> None:
        assert _validate_label("tel") is False
        assert _validate_label("Tél") is False
        assert _validate_label("email") is False

    def test_accepts_generic_in_phrase(self) -> None:
        assert _validate_label("Téléphone du bureau") is True

    def test_accepts_accented(self) -> None:
        assert _validate_label("Départément") is True


# ──────────────────────────────────────────────────────────────────────────────
# _extract_preceding_label
# ──────────────────────────────────────────────────────────────────────────────


class TestExtractPrecedingLabel:
    def test_same_line_with_colon(self) -> None:
        text = "Service client : 06 12 34 56 78"
        # "06 12 34 56 78" starts at index 18
        idx = text.index("06")
        label = _extract_preceding_label(text, idx)
        assert label == "Service client"

    def test_same_line_with_dash(self) -> None:
        text = "Réservation - 06 12 34 56 78"
        idx = text.index("06")
        label = _extract_preceding_label(text, idx)
        assert label == "Réservation"

    def test_previous_line_label(self) -> None:
        text = "Contact principal\n06 12 34 56 78"
        idx = text.index("06")
        label = _extract_preceding_label(text, idx)
        assert label == "Contact principal"

    def test_no_label_when_empty(self) -> None:
        text = "06 12 34 56 78"
        label = _extract_preceding_label(text, 0)
        assert label is None

    def test_rejects_long_sentence_preceding(self) -> None:
        text = "Nous sommes une entreprise spécialisée dans les services numériques depuis 2005 basée à Paris 06 12 34 56 78"
        idx = text.index("06")
        label = _extract_preceding_label(text, idx)
        assert label is None

    def test_long_candidate_extracts_last_phrase(self) -> None:
        text = "Nos coordonnées, Service après-vente : 06 12 34 56 78"
        idx = text.index("06")
        label = _extract_preceding_label(text, idx)
        assert label is not None
        assert "après-vente" in label


# ──────────────────────────────────────────────────────────────────────────────
# extract_phones_with_labels
# ──────────────────────────────────────────────────────────────────────────────


class TestExtractPhonesWithLabels:
    def test_mobile_with_label(self) -> None:
        text = "Réservation : 06 12 34 56 78"
        mobiles, nationals = extract_phones_with_labels(text)
        assert len(mobiles) == 1
        value, label = mobiles[0]
        assert value == "+33612345678"
        assert label == "Réservation"

    def test_national_with_label(self) -> None:
        text = "Standard : 01 23 45 67 89"
        mobiles, nationals = extract_phones_with_labels(text)
        assert len(nationals) == 1
        value, label = nationals[0]
        assert value == "+33123456789"
        assert label == "Standard"

    def test_phone_without_label(self) -> None:
        text = "06 12 34 56 78"
        mobiles, _ = extract_phones_with_labels(text)
        assert len(mobiles) == 1
        value, label = mobiles[0]
        assert value == "+33612345678"
        assert label is None

    def test_dedup_prefers_label(self) -> None:
        text = "06 12 34 56 78\nRéservation : 06 12 34 56 78"
        mobiles, _ = extract_phones_with_labels(text)
        assert len(mobiles) == 1
        _, label = mobiles[0]
        assert label == "Réservation"

    def test_multiple_phones_with_labels(self) -> None:
        text = "Réservation : 06 12 34 56 78\nService client : 01 23 45 67 89"
        mobiles, nationals = extract_phones_with_labels(text)
        assert len(mobiles) == 1
        assert len(nationals) == 1
        assert mobiles[0][1] == "Réservation"
        assert nationals[0][1] == "Service client"

    def test_international_format_with_label(self) -> None:
        text = "Urgences : +33 6 12 34 56 78"
        mobiles, _ = extract_phones_with_labels(text)
        assert len(mobiles) == 1
        assert mobiles[0][0] == "+33612345678"
        assert mobiles[0][1] == "Urgences"


# ──────────────────────────────────────────────────────────────────────────────
# extract_emails_with_labels
# ──────────────────────────────────────────────────────────────────────────────


class TestExtractEmailsWithLabels:
    def test_email_with_label(self) -> None:
        text = "Support technique : support@example.com"
        emails = extract_emails_with_labels(text)
        assert len(emails) == 1
        value, label = emails[0]
        assert value == "support@example.com"
        assert label == "Support technique"

    def test_email_without_label(self) -> None:
        text = "contact@example.com"
        emails = extract_emails_with_labels(text)
        assert len(emails) == 1
        value, label = emails[0]
        assert value == "contact@example.com"
        assert label is None

    def test_multiple_emails_with_labels(self) -> None:
        text = "Commercial : sales@example.com\nSupport : help@example.com"
        emails = extract_emails_with_labels(text)
        assert len(emails) == 2
        labels = {e[0]: e[1] for e in emails}
        assert labels["sales@example.com"] == "Commercial"
        assert labels["help@example.com"] == "Support"

    def test_dedup_case_insensitive(self) -> None:
        text = "Contact@Example.COM et aussi contact@example.com"
        emails = extract_emails_with_labels(text)
        assert len(emails) == 1


# ──────────────────────────────────────────────────────────────────────────────
# _merge_contacts (crawlers helper)
# ──────────────────────────────────────────────────────────────────────────────


class TestMergeContacts:
    def test_merge_new_entry(self) -> None:
        target: dict[str, str | None] = {}
        _merge_contacts(target, [("+33612345678", "Bureau")])
        assert target["+33612345678"] == "Bureau"

    def test_merge_prefers_label(self) -> None:
        target: dict[str, str | None] = {"+33612345678": None}
        _merge_contacts(target, [("+33612345678", "Accueil")])
        assert target["+33612345678"] == "Accueil"

    def test_merge_keeps_existing_label(self) -> None:
        target: dict[str, str | None] = {"+33612345678": "Bureau"}
        _merge_contacts(target, [("+33612345678", None)])
        assert target["+33612345678"] == "Bureau"


# ──────────────────────────────────────────────────────────────────────────────
# ContactItem & WebsiteScrapingResult
# ──────────────────────────────────────────────────────────────────────────────


class TestContactItemAndResult:
    def test_contact_item_defaults(self) -> None:
        item = ContactItem("+33612345678")
        assert item.value == "+33612345678"
        assert item.label is None

    def test_result_pipe_separated_properties(self) -> None:
        result = WebsiteScrapingResult(
            mobile_phones=[ContactItem("+33612345678", "Bureau"), ContactItem("+33798765432")],
            emails=[ContactItem("a@b.com", "Commercial")],
        )
        assert result.mobile_phones_str == "+33612345678|+33798765432"
        assert result.emails_str == "a@b.com"
        assert result.national_phones_str is None

    def test_all_contacts_property(self) -> None:
        result = WebsiteScrapingResult(
            mobile_phones=[ContactItem("+33612345678", "Bureau")],
            national_phones=[ContactItem("+33123456789")],
            emails=[ContactItem("a@b.com", "Support")],
        )
        contacts = result.all_contacts
        assert len(contacts) == 3
        assert ("mobile_phone", "+33612345678", "Bureau") in contacts
        assert ("national_phone", "+33123456789", None) in contacts
        assert ("email", "a@b.com", "Support") in contacts

    def test_has_data_true(self) -> None:
        result = WebsiteScrapingResult(emails=[ContactItem("a@b.com")])
        assert result.has_data is True

    def test_has_data_false(self) -> None:
        result = WebsiteScrapingResult()
        assert result.has_data is False


# ──────────────────────────────────────────────────────────────────────────────
# ScrapedContact persistence (_persist_scraped_contacts)
# ──────────────────────────────────────────────────────────────────────────────


class TestPersistScrapedContacts:
    def test_persist_inserts_contacts(self) -> None:
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
                mobile_phones=[ContactItem("+33612345678", "Bureau")],
                emails=[ContactItem("a@b.com", "Support")],
            )
            now = utcnow()
            _persist_scraped_contacts(session, est.siret, result, now)
            session.flush()

            contacts = (
                session.query(models.ScrapedContact)
                .filter_by(establishment_siret=est.siret)
                .all()
            )
            assert len(contacts) == 2
            types = {c.contact_type for c in contacts}
            assert types == {"mobile_phone", "email"}
            labeled = [c for c in contacts if c.label]
            assert len(labeled) == 2

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

            # First scrape
            result1 = WebsiteScrapingResult(
                mobile_phones=[ContactItem("+33612345678", "Bureau")],
            )
            now = utcnow()
            _persist_scraped_contacts(session, est.siret, result1, now)
            session.flush()

            assert (
                session.query(models.ScrapedContact)
                .filter_by(establishment_siret=est.siret)
                .count()
            ) == 1

            # Second scrape replaces
            result2 = WebsiteScrapingResult(
                emails=[ContactItem("x@y.com"), ContactItem("a@b.com")],
            )
            _persist_scraped_contacts(session, est.siret, result2, now)
            session.flush()

            contacts = (
                session.query(models.ScrapedContact)
                .filter_by(establishment_siret=est.siret)
                .all()
            )
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

            result = WebsiteScrapingResult(
                mobile_phones=[ContactItem("+33612345678")],
            )
            now = utcnow()
            _persist_scraped_contacts(session, est.siret, result, now)
            session.flush()
            assert (
                session.query(models.ScrapedContact)
                .filter_by(establishment_siret=est.siret)
                .count()
            ) == 1

            # Empty result clears all contacts
            _persist_scraped_contacts(session, est.siret, WebsiteScrapingResult(), now)
            session.flush()
            assert (
                session.query(models.ScrapedContact)
                .filter_by(establishment_siret=est.siret)
                .count()
            ) == 0
