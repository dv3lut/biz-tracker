from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.db import models
from app.db.base import Base
from app.services.sync.auto_email import dispatch_auto_emails


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


def _make_run() -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), scope_key="default")


def _make_establishment(siret: str, naf_code: str, *, email: str | None) -> models.Establishment:
    establishment = models.Establishment(
        siret=siret,
        siren=siret[:9],
        nic=siret[9:],
        name=f"Boulangerie {siret[-2:]}",
        naf_code=naf_code,
        code_postal="75001",
        libelle_commune="Paris",
        first_seen_at=datetime(2024, 1, 1),
        last_seen_at=datetime(2024, 1, 1),
    )
    if email:
        establishment.scraped_contacts = [
            models.ScrapedContact(
                id=uuid4(),
                establishment_siret=siret,
                contact_type="email",
                value=email,
            )
        ]
    return establishment


def _enable_naf(session, naf_code: str, *, subject: str, body: str) -> None:
    subcategory = models.NafSubCategory(
        id=uuid4(),
        name=f"NAF {naf_code}",
        naf_code=naf_code,
        price_cents=0,
        is_active=True,
        auto_email_enabled=True,
        auto_email_subject=subject,
        auto_email_body=body,
    )
    session.add(subcategory)
    session.flush()


def test_dispatch_auto_emails_returns_no_new_establishments_when_empty():
    with _session_scope() as session:
        summary = dispatch_auto_emails(session, _make_run(), [])
    assert summary["reason"] == "no_new_establishments"
    assert summary["sent_count"] == 0


def test_dispatch_auto_emails_skips_when_no_naf_enabled():
    with _session_scope() as session:
        establishment = _make_establishment("11111111100011", "56.10A", email="a@example.com")
        session.add(establishment)
        session.flush()
        summary = dispatch_auto_emails(session, _make_run(), [establishment])
    assert summary["reason"] == "no_naf_with_auto_email"
    assert summary["sent_count"] == 0


@pytest.fixture
def configured_email_service(monkeypatch):
    settings = SimpleNamespace(
        enabled=True,
        provider="smtp",
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="user",
        smtp_password="pass",
        use_tls=True,
        from_address="contact@business-tracker.fr",
        smtp_timeout_seconds=10,
    )

    def _is_enabled(self):
        return True

    def _is_configured(self):
        return True

    sent_calls: list[dict] = []

    def _send(self, subject, body, recipients, *, html_body=None, reply_to=None, attachments=None):
        sent_calls.append(
            {
                "subject": subject,
                "body": body,
                "recipients": list(recipients),
                "reply_to": reply_to,
            }
        )

    from app.services import email_service as email_service_module

    monkeypatch.setattr(email_service_module.EmailService, "is_enabled", _is_enabled)
    monkeypatch.setattr(email_service_module.EmailService, "is_configured", _is_configured)
    monkeypatch.setattr(email_service_module.EmailService, "send", _send)
    monkeypatch.setattr(
        email_service_module.EmailService,
        "settings",
        property(lambda self: settings),
    )

    return sent_calls


def test_dispatch_auto_emails_sends_with_template_variables(configured_email_service):
    with _session_scope() as session:
        _enable_naf(
            session,
            "56.10A",
            subject="Bonjour {name}",
            body="Bonjour {name}, votre SIRET est {siret}. ({email})",
        )
        establishment = _make_establishment("11111111100011", "56.10A", email="ceo@boul.fr")
        session.add(establishment)
        session.flush()
        summary = dispatch_auto_emails(session, _make_run(), [establishment])

    assert summary["sent_count"] == 1
    assert summary["attempted_count"] == 1
    assert summary["skipped_count"] == 0
    assert summary["failed_count"] == 0
    assert summary["enabled_naf_codes"] == ["56.10A"]
    assert len(configured_email_service) == 1
    call = configured_email_service[0]
    assert call["subject"] == "Bonjour Boulangerie 11"
    assert "11111111100011" in call["body"]
    assert call["recipients"] == ["ceo@boul.fr"]
    assert call["reply_to"] == "contact@business-tracker.fr"
    item = summary["items"][0]
    assert item["sent"] is True
    assert item["recipients"] == ["ceo@boul.fr"]


def test_dispatch_auto_emails_skips_establishment_without_email(configured_email_service):
    with _session_scope() as session:
        _enable_naf(session, "56.10A", subject="Hello", body="Hello {name}")
        establishment = _make_establishment("11111111100011", "56.10A", email=None)
        session.add(establishment)
        session.flush()
        summary = dispatch_auto_emails(session, _make_run(), [establishment])

    assert summary["sent_count"] == 0
    assert summary["skipped_count"] == 1
    assert summary["items"][0]["reason"] == "no_email_found"
    assert configured_email_service == []


def test_dispatch_auto_emails_skips_when_template_missing(configured_email_service):
    with _session_scope() as session:
        _enable_naf(session, "56.10A", subject="Hello", body="")
        # auto_email_body was rejected by _enable_naf? It set it. We need to actually
        # set it back to None to test the missing-template path.
        sub = session.query(models.NafSubCategory).first()
        sub.auto_email_body = None
        session.flush()
        establishment = _make_establishment("11111111100011", "56.10A", email="x@example.com")
        session.add(establishment)
        session.flush()
        summary = dispatch_auto_emails(session, _make_run(), [establishment])

    assert summary["sent_count"] == 0
    assert summary["skipped_count"] == 1
    assert summary["items"][0]["reason"] == "missing_template"


def test_dispatch_auto_emails_reports_send_errors(configured_email_service, monkeypatch):
    from app.services import email_service as email_service_module

    def _raise(self, *_args, **_kwargs):
        raise RuntimeError("smtp boom")

    monkeypatch.setattr(email_service_module.EmailService, "send", _raise)

    with _session_scope() as session:
        _enable_naf(session, "56.10A", subject="Hi", body="Hi {name}")
        establishment = _make_establishment("11111111100011", "56.10A", email="x@example.com")
        session.add(establishment)
        session.flush()
        summary = dispatch_auto_emails(session, _make_run(), [establishment])

    assert summary["failed_count"] == 1
    assert summary["sent_count"] == 0
    item = summary["items"][0]
    assert item["sent"] is False
    assert item["reason"] == "send_error"
