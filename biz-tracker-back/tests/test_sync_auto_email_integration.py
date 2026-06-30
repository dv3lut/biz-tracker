"""End-to-end integration tests for the per-NAF auto-email feature.

These tests exercise the full ``SyncService.run_sync`` pipeline against an
in-memory SQLite database, with Sirene and Google clients patched out. They
verify that the per-NAF auto-email configuration drives whether a newly-created
establishment receives an automated email, the contents of that email (template
variables, Reply-To), the run summary persisted on the SyncRun, and the recap
embedded in the admin run-summary email.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.db import models
from app.db.base import Base
from app.services.google_business.google_types import GoogleMatch
from app.services.sync_service import SyncService
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


def _make_settings():
    return SimpleNamespace(
        sync=SimpleNamespace(
            scope_key="default",
            months_back=1,
            incremental_lookback_months=1,
        ),
        sirene=SimpleNamespace(
            page_size=10,
            current_period_date="2100-01-01",
            api_token="token",
            max_calls_per_minute=1_000_000,
        ),
        email=SimpleNamespace(
            enabled=True,
            provider="smtp",
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_username="user",
            smtp_password="pass",
            use_tls=True,
            from_address="contact@business-tracker.fr",
            smtp_timeout_seconds=10,
        ),
        google=SimpleNamespace(
            enabled=True,
            api_key="test",
            max_calls_per_minute=1_000_000,
            category_similarity_threshold=0.72,
            daily_retry_limit=20_000,
            recheck_hours=24,
            find_place_url="https://example.test/find",
            place_details_url="https://example.test/details",
            language="fr",
            website_scrape_enabled=False,
        ),
        logging=SimpleNamespace(service_name="biz-tracker-back"),
    )


def _patch_settings(monkeypatch, settings):
    import app.config as config
    import app.observability as observability
    import app.services.email_service as email_service
    import app.services.google_business.google_business_service as google_service
    import app.services.sync_service as sync_service

    monkeypatch.setattr(config, "get_settings", lambda: settings)
    monkeypatch.setattr(observability, "get_settings", lambda: settings)
    monkeypatch.setattr(email_service, "get_settings", lambda: settings)
    monkeypatch.setattr(google_service, "get_settings", lambda: settings)
    monkeypatch.setattr(sync_service, "get_settings", lambda: settings)


def _patch_sirene_client(monkeypatch, pages):
    import app.services.sync.preparation as preparation

    class FakeSireneClient:
        def __init__(self):
            self._pages = list(pages)
            self._index = 0

        def get_informations(self):
            return {
                "datesDernieresMisesAJourDesDonnees": [
                    {
                        "collection": "etablissements",
                        "dateDernierTraitementMaximum": "2026-02-01T00:00:00Z",
                    }
                ]
            }

        def search_establishments(self, **_kwargs):
            if self._index >= len(self._pages):
                return {
                    "header": {"curseur": _kwargs.get("curseur"), "curseurSuivant": None, "total": 0},
                    "etablissements": [],
                }
            page = self._pages[self._index]
            self._index += 1
            return page

        def close(self):
            return None

    monkeypatch.setattr(preparation, "SireneClient", FakeSireneClient)


def _patch_google_stack(monkeypatch, *, contact_emails_by_siret: dict[str, str]):
    """Patch Google Places + lookup to populate ``google_contact_email`` per SIRET.

    ``contact_emails_by_siret`` maps each SIRET to the email that should be
    persisted on the establishment after the Google enrichment step. Any SIRET
    not in the dict ends up with ``google_contact_email = None``.
    """

    import app.services.google_business.google_business_service as google_service
    import app.services.google_business.google_lookup_engine as lookup_engine

    class DummyGooglePlacesClient:
        def __init__(self):
            return None

        def close(self):
            return None

    def fake_lookup(self, establishment, *, now=None):
        now = now or utcnow()
        return GoogleMatch(
            establishment=establishment,
            place_id=f"place-{establishment.siret}",
            place_url=f"https://maps.google.com/?q={establishment.siret}",
            confidence=0.9,
            category_confidence=0.8,
            listing_origin_at=now,
            listing_origin_source="google",
            listing_age_status="recent_creation",
            contact_email=contact_emails_by_siret.get(establishment.siret),
        )

    monkeypatch.setattr(google_service, "GooglePlacesClient", DummyGooglePlacesClient)
    monkeypatch.setattr(lookup_engine.GoogleLookupEngine, "lookup", fake_lookup)


def _seed_naf_subcategory(
    session,
    *,
    name: str,
    naf_code: str,
    auto_email_enabled: bool,
    auto_email_subject: str | None = None,
    auto_email_body: str | None = None,
) -> models.NafSubCategory:
    category = (
        session.execute(select(models.NafCategory).where(models.NafCategory.name == "Catégorie test"))
        .scalar_one_or_none()
    )
    if category is None:
        category = models.NafCategory(name="Catégorie test", description=None, keywords=[])
        session.add(category)
        session.flush()
    subcategory = models.NafSubCategory(
        name=name,
        description=None,
        naf_code=naf_code,
        price_cents=0,
        is_active=True,
        auto_email_enabled=auto_email_enabled,
        auto_email_subject=auto_email_subject,
        auto_email_body=auto_email_body,
    )
    session.add(subcategory)
    session.flush()
    session.add(
        models.NafCategorySubCategory(category_id=category.id, subcategory_id=subcategory.id)
    )
    session.flush()
    return subcategory


def _seed_client(session, subcategory: models.NafSubCategory) -> models.Client:
    client = models.Client(
        name=f"Client {subcategory.naf_code}",
        start_date=date.today(),
        end_date=None,
        listing_statuses=["recent_creation"],
    )
    session.add(client)
    session.flush()
    session.add(models.ClientRecipient(client_id=client.id, email="client@example.com"))
    session.add(models.ClientSubscription(client_id=client.id, subcategory_id=subcategory.id))
    session.flush()
    return client


def _seed_admin_recipient(session) -> None:
    session.add(models.AdminRecipient(email="admin@example.com"))
    session.flush()


def _seed_google_retry_config(session) -> None:
    session.add(
        models.GoogleRetryConfig(
            retry_weekdays=list(range(7)),
            default_rules=[{"max_age_days": 60, "frequency_days": 7}],
            micro_rules=[{"max_age_days": None, "frequency_days": 21}],
            retry_missing_contact_enabled=True,
            retry_missing_contact_frequency_days=14,
        )
    )
    session.flush()


def _establishment_payload(
    *,
    siret: str,
    name: str,
    naf_code: str,
    code_postal: str = "75001",
    libelle_commune: str = "Paris",
):
    return {
        "siret": siret,
        "siren": siret[:9],
        "nic": siret[9:14],
        "dateCreationEtablissement": "2026-01-15",
        "uniteLegale": {
            "categorieEntreprise": "ME",
            "categorieJuridiqueUniteLegale": "1000",
            "denominationUniteLegale": name,
            "denominationUsuelle1UniteLegale": name,
        },
        "periodesEtablissement": [
            {
                "dateFin": None,
                "etatAdministratifEtablissement": "A",
                "activitePrincipaleEtablissement": naf_code,
                "libelleActivitePrincipaleEtablissement": "Activité test",
                "denominationUsuelleEtablissement": name,
            }
        ],
        "adresseEtablissement": {
            "numeroVoieEtablissement": "1",
            "typeVoieEtablissement": "Rue",
            "libelleVoieEtablissement": "de Test",
            "codePostalEtablissement": code_postal,
            "libelleCommuneEtablissement": libelle_commune,
        },
    }


def _capture_sent_emails(monkeypatch) -> list[dict[str, object]]:
    """Patch EmailService.send to capture every email dispatched during the run."""

    sent: list[dict[str, object]] = []

    def _send(self, subject, body, recipients, *, html_body=None, reply_to=None, attachments=None):
        sent.append(
            {
                "subject": subject,
                "body": body,
                "recipients": list(recipients),
                "reply_to": reply_to,
                "html_body": html_body,
            }
        )

    import app.services.email_service as email_service

    monkeypatch.setattr(email_service.EmailService, "send", _send)
    return sent


def _auto_emails(sent: list[dict[str, object]]) -> list[dict[str, object]]:
    """Filter out admin/client emails — auto-emails are the only ones with Reply-To set."""

    return [item for item in sent if item.get("reply_to")]


def _admin_recap_email(sent: list[dict[str, object]]) -> dict[str, object] | None:
    """Find the run-summary email sent by ``_send_run_summary_email``.

    The admin recipient also receives alert emails from the alert service, so
    we match on the run-summary subject prefix to avoid picking up the wrong
    one.
    """

    for item in sent:
        subject = str(item.get("subject") or "")
        if subject.startswith("Business tracker · Synthese run"):
            return item
    return None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_auto_email_is_sent_for_enabled_naf_with_scraped_email(monkeypatch):
    """Happy path: a new establishment on an enabled NAF with a known email
    receives a personalized auto-email at run completion, and the admin recap
    email lists the contacted business."""

    settings = _make_settings()
    _patch_settings(monkeypatch, settings)
    sent_emails = _capture_sent_emails(monkeypatch)

    siret = "11111111111111"
    _patch_google_stack(monkeypatch, contact_emails_by_siret={siret: "founder@new-biz.fr"})

    with _session_scope() as session:
        subcategory = _seed_naf_subcategory(
            session,
            name="Restaurants",
            naf_code="56.10A",
            auto_email_enabled=True,
            auto_email_subject="Bienvenue {name} ({siret})",
            auto_email_body=(
                "Bonjour,\nFélicitations pour {name} ({siret}) à {commune} {code_postal}.\n"
                "Nous contacter : {email}."
            ),
        )
        _seed_client(session, subcategory)
        _seed_admin_recipient(session)
        _seed_google_retry_config(session)

        _patch_sirene_client(
            monkeypatch,
            [
                {
                    "header": {"curseur": "*", "curseurSuivant": "next", "total": 1},
                    "etablissements": [
                        _establishment_payload(siret=siret, name="Nouvelle Cantine", naf_code="56.10A"),
                    ],
                },
                {
                    "header": {"curseur": "next", "curseurSuivant": None, "total": 1},
                    "etablissements": [],
                },
            ],
        )

        service = SyncService()
        run = service.run_sync(session)

        # Run finished successfully and persisted the auto-email summary.
        assert run.status == "success"
        assert run.created_records == 1
        assert run.summary is not None
        auto_email_summary = run.summary.get("auto_email")
        assert auto_email_summary is not None
        assert auto_email_summary["sent_count"] == 1
        assert auto_email_summary["attempted_count"] == 1
        assert auto_email_summary["skipped_count"] == 0
        assert auto_email_summary["failed_count"] == 0
        assert auto_email_summary["enabled_naf_codes"] == ["56.10A"]
        assert auto_email_summary["items"][0]["sent"] is True
        assert auto_email_summary["items"][0]["recipients"] == ["founder@new-biz.fr"]
        assert auto_email_summary["items"][0]["siret"] == siret

        # The dispatched auto-email contains the substituted template + Reply-To.
        autos = _auto_emails(sent_emails)
        assert len(autos) == 1, f"expected exactly one auto-email, got {autos!r}"
        auto = autos[0]
        assert auto["recipients"] == ["founder@new-biz.fr"]
        assert auto["reply_to"] == "contact@business-tracker.fr"
        assert auto["subject"] == f"Bienvenue Nouvelle Cantine ({siret})"
        assert f"Nouvelle Cantine ({siret})" in str(auto["body"])
        assert "Paris" in str(auto["body"])
        assert "founder@new-biz.fr" in str(auto["body"])

        # The admin recap email mentions the contacted business.
        admin_recap = _admin_recap_email(sent_emails)
        assert admin_recap is not None, "admin recap email should be sent"
        body = str(admin_recap["body"])
        assert "Emails automatiques aux nouveaux établissements" in body
        assert siret in body
        assert "founder@new-biz.fr" in body


def test_auto_email_not_sent_when_naf_disabled(monkeypatch):
    """When the matched NAF has auto_email_enabled=False (or no template),
    no auto-email is dispatched even if the establishment has a known email."""

    settings = _make_settings()
    _patch_settings(monkeypatch, settings)
    sent_emails = _capture_sent_emails(monkeypatch)

    siret = "22222222222222"
    _patch_google_stack(monkeypatch, contact_emails_by_siret={siret: "info@new-biz.fr"})

    with _session_scope() as session:
        subcategory = _seed_naf_subcategory(
            session,
            name="Restaurants",
            naf_code="56.10A",
            auto_email_enabled=False,
            # Template defined but feature disabled — must not send.
            auto_email_subject="Bienvenue {name}",
            auto_email_body="Bonjour {name}",
        )
        _seed_client(session, subcategory)
        _seed_admin_recipient(session)
        _seed_google_retry_config(session)

        _patch_sirene_client(
            monkeypatch,
            [
                {
                    "header": {"curseur": "*", "curseurSuivant": "next", "total": 1},
                    "etablissements": [
                        _establishment_payload(siret=siret, name="Resto", naf_code="56.10A"),
                    ],
                },
                {
                    "header": {"curseur": "next", "curseurSuivant": None, "total": 1},
                    "etablissements": [],
                },
            ],
        )

        service = SyncService()
        run = service.run_sync(session)

        assert run.status == "success"
        assert run.created_records == 1
        auto_email_summary = run.summary["auto_email"]
        assert auto_email_summary["sent_count"] == 0
        assert auto_email_summary["attempted_count"] == 0
        assert auto_email_summary["reason"] == "no_naf_with_auto_email"

        autos = _auto_emails(sent_emails)
        assert autos == [], f"no auto-email expected, got {autos!r}"


def test_auto_email_skipped_when_no_email_found(monkeypatch):
    """An enabled NAF but no scraped/contact email on the establishment must
    record a skipped item with reason ``no_email_found`` and dispatch nothing."""

    settings = _make_settings()
    _patch_settings(monkeypatch, settings)
    sent_emails = _capture_sent_emails(monkeypatch)

    siret = "33333333333333"
    # No contact_email in the patch — establishment ends with google_contact_email = None.
    _patch_google_stack(monkeypatch, contact_emails_by_siret={})

    with _session_scope() as session:
        subcategory = _seed_naf_subcategory(
            session,
            name="Restaurants",
            naf_code="56.10A",
            auto_email_enabled=True,
            auto_email_subject="Bienvenue {name}",
            auto_email_body="Bonjour {name}",
        )
        _seed_client(session, subcategory)
        _seed_admin_recipient(session)
        _seed_google_retry_config(session)

        _patch_sirene_client(
            monkeypatch,
            [
                {
                    "header": {"curseur": "*", "curseurSuivant": "next", "total": 1},
                    "etablissements": [
                        _establishment_payload(siret=siret, name="Resto Sans Email", naf_code="56.10A"),
                    ],
                },
                {
                    "header": {"curseur": "next", "curseurSuivant": None, "total": 1},
                    "etablissements": [],
                },
            ],
        )

        service = SyncService()
        run = service.run_sync(session)

        assert run.status == "success"
        auto_email_summary = run.summary["auto_email"]
        assert auto_email_summary["sent_count"] == 0
        assert auto_email_summary["attempted_count"] == 0
        assert auto_email_summary["skipped_count"] == 1
        items = auto_email_summary["items"]
        assert len(items) == 1
        assert items[0]["sent"] is False
        assert items[0]["reason"] == "no_email_found"
        assert items[0]["siret"] == siret

        autos = _auto_emails(sent_emails)
        assert autos == []


def test_auto_email_only_targets_enabled_naf_in_mixed_run(monkeypatch):
    """A run that creates establishments across two NAFs (one enabled,
    one disabled) only sends auto-emails for establishments under the
    enabled NAF."""

    settings = _make_settings()
    _patch_settings(monkeypatch, settings)
    sent_emails = _capture_sent_emails(monkeypatch)

    enabled_siret = "44444444444444"
    disabled_siret = "55555555555555"
    _patch_google_stack(
        monkeypatch,
        contact_emails_by_siret={
            enabled_siret: "hello@enabled-biz.fr",
            disabled_siret: "hello@disabled-biz.fr",
        },
    )

    with _session_scope() as session:
        enabled_sub = _seed_naf_subcategory(
            session,
            name="Restaurants",
            naf_code="56.10A",
            auto_email_enabled=True,
            auto_email_subject="Bienvenue {name}",
            auto_email_body="Bonjour {name} ({naf_code})",
        )
        disabled_sub = _seed_naf_subcategory(
            session,
            name="Boulangeries",
            naf_code="10.71C",
            auto_email_enabled=False,
            auto_email_subject="Bienvenue {name}",
            auto_email_body="Bonjour {name}",
        )
        _seed_client(session, enabled_sub)
        _seed_client(session, disabled_sub)
        _seed_admin_recipient(session)
        _seed_google_retry_config(session)

        _patch_sirene_client(
            monkeypatch,
            [
                {
                    "header": {"curseur": "*", "curseurSuivant": "next", "total": 2},
                    "etablissements": [
                        _establishment_payload(
                            siret=enabled_siret, name="Enabled Biz", naf_code="56.10A"
                        ),
                        _establishment_payload(
                            siret=disabled_siret, name="Disabled Biz", naf_code="10.71C"
                        ),
                    ],
                },
                {
                    "header": {"curseur": "next", "curseurSuivant": None, "total": 2},
                    "etablissements": [],
                },
            ],
        )

        service = SyncService()
        run = service.run_sync(session)

        assert run.status == "success"
        assert run.created_records == 2

        auto_email_summary = run.summary["auto_email"]
        # Only the enabled NAF should be in the summary.
        assert auto_email_summary["enabled_naf_codes"] == ["56.10A"]
        assert auto_email_summary["sent_count"] == 1
        # The disabled-NAF establishment is filtered out entirely (configs map
        # is keyed on enabled NAF codes only).
        sirets_in_items = {item["siret"] for item in auto_email_summary["items"]}
        assert sirets_in_items == {enabled_siret}

        autos = _auto_emails(sent_emails)
        assert len(autos) == 1
        assert autos[0]["recipients"] == ["hello@enabled-biz.fr"]
        assert autos[0]["reply_to"] == "contact@business-tracker.fr"
        assert "Enabled Biz" in autos[0]["subject"]


def test_auto_email_failure_recorded_and_does_not_break_run(monkeypatch):
    """If SMTP send fails for an auto-email, the run still completes
    successfully and the failure is recorded in the summary."""

    settings = _make_settings()
    _patch_settings(monkeypatch, settings)
    sent_emails = _capture_sent_emails(monkeypatch)

    siret = "66666666666666"
    _patch_google_stack(monkeypatch, contact_emails_by_siret={siret: "ceo@fail-biz.fr"})

    # Override the captured-send to raise on auto-emails (those carry reply_to)
    # but let admin/client emails go through normally.
    import app.services.email_service as email_service

    def _send_with_fault(self, subject, body, recipients, *, html_body=None, reply_to=None, attachments=None):
        if reply_to:
            raise RuntimeError("simulated SMTP failure")
        sent_emails.append(
            {
                "subject": subject,
                "body": body,
                "recipients": list(recipients),
                "reply_to": reply_to,
                "html_body": html_body,
            }
        )

    monkeypatch.setattr(email_service.EmailService, "send", _send_with_fault)

    with _session_scope() as session:
        subcategory = _seed_naf_subcategory(
            session,
            name="Restaurants",
            naf_code="56.10A",
            auto_email_enabled=True,
            auto_email_subject="Hello {name}",
            auto_email_body="Hi {name}",
        )
        _seed_client(session, subcategory)
        _seed_admin_recipient(session)
        _seed_google_retry_config(session)

        _patch_sirene_client(
            monkeypatch,
            [
                {
                    "header": {"curseur": "*", "curseurSuivant": "next", "total": 1},
                    "etablissements": [
                        _establishment_payload(siret=siret, name="Fail Biz", naf_code="56.10A"),
                    ],
                },
                {
                    "header": {"curseur": "next", "curseurSuivant": None, "total": 1},
                    "etablissements": [],
                },
            ],
        )

        service = SyncService()
        run = service.run_sync(session)

        # The run still succeeds; only the per-establishment dispatch failed.
        assert run.status == "success"
        auto_email_summary = run.summary["auto_email"]
        assert auto_email_summary["attempted_count"] == 1
        assert auto_email_summary["sent_count"] == 0
        assert auto_email_summary["failed_count"] == 1
        items = auto_email_summary["items"]
        assert items[0]["sent"] is False
        assert items[0]["reason"] == "send_error"

        # The admin recap is still sent.
        admin_recap = _admin_recap_email(sent_emails)
        assert admin_recap is not None
