from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from contextlib import contextmanager

from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.db import models
from app.db.base import Base
from app.services.google_business.google_types import GoogleMatch
from app.services.regions_service import list_departments
from app.services.sync.mode import SyncMode
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


def _make_settings(*, google_enabled: bool = True):
    return SimpleNamespace(
        sync=SimpleNamespace(
            scope_key="default",
            months_back=1,
            incremental_lookback_months=1,
        ),
        sirene=SimpleNamespace(
            page_size=2,
            current_period_date="2100-01-01",
            api_token="token",
            max_calls_per_minute=1_000_000,
        ),
        email=SimpleNamespace(
            enabled=False,
            provider="custom",
            smtp_host=None,
            smtp_port=25,
            smtp_username=None,
            smtp_password=None,
            use_tls=False,
            from_address="noreply@example.com",
        ),
        google=SimpleNamespace(
            enabled=google_enabled,
            api_key="test" if google_enabled else None,
            max_calls_per_minute=1_000_000,
            category_similarity_threshold=0.72,
            daily_retry_limit=20_000,
            recheck_hours=24,
            find_place_url="https://example.test/find",
            place_details_url="https://example.test/details",
            language="fr",
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


def _patch_sirene_client(monkeypatch, pages, informations=None):
    import app.services.sync.preparation as preparation

    class FakeSireneClient:
        def __init__(self):
            self._pages = list(pages)
            self._index = 0

        def get_informations(self):
            return informations or {
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


def _patch_google_stack(monkeypatch):
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
        )

    monkeypatch.setattr(google_service, "GooglePlacesClient", DummyGooglePlacesClient)
    monkeypatch.setattr(lookup_engine.GoogleLookupEngine, "lookup", fake_lookup)


def _patch_google_client(monkeypatch):
    import app.services.google_business.google_business_service as google_service

    class DummyGooglePlacesClient:
        def __init__(self):
            return None

        def close(self):
            return None

    monkeypatch.setattr(google_service, "GooglePlacesClient", DummyGooglePlacesClient)


def _seed_naf(session):
    category = models.NafCategory(
        name="Restauration",
        description=None,
        keywords=["restaurant"],
    )
    session.add(category)
    session.flush()
    subcategory = models.NafSubCategory(
        name="Restaurants",
        description=None,
        naf_code="56.10A",
        price_cents=0,
        is_active=True,
    )
    session.add(subcategory)
    session.flush()
    session.add(
        models.NafCategorySubCategory(
            category_id=category.id,
            subcategory_id=subcategory.id,
        )
    )
    session.flush()
    return subcategory


def _seed_client(session, subcategory):
    client = models.Client(
        name="Client A",
        start_date=date.today(),
        end_date=None,
        listing_statuses=["recent_creation"],
    )
    session.add(client)
    session.flush()
    recipient = models.ClientRecipient(client_id=client.id, email="client@example.com")
    session.add(recipient)
    subscription = models.ClientSubscription(client_id=client.id, subcategory_id=subcategory.id)
    session.add(subscription)
    session.flush()
    return client


def _seed_google_retry_config(session):
    record = models.GoogleRetryConfig(
        retry_weekdays=list(range(7)),
        default_rules=[{"max_age_days": 60, "frequency_days": 7}],
        micro_rules=[{"max_age_days": None, "frequency_days": 21}],
        retry_missing_contact_enabled=True,
        retry_missing_contact_frequency_days=14,
    )
    session.add(record)
    session.flush()


def _make_establishment_payload(*, siret: str, name: str, naf_code: str):
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
                "libelleActivitePrincipaleEtablissement": "Restauration",
                "denominationUsuelleEtablissement": name,
            }
        ],
        "adresseEtablissement": {
            "numeroVoieEtablissement": "1",
            "typeVoieEtablissement": "Rue",
            "libelleVoieEtablissement": "de Test",
            "codePostalEtablissement": "75001",
            "libelleCommuneEtablissement": "Paris",
        },
    }


def test_full_sync_flow_with_google_and_alerts(monkeypatch):
    settings = _make_settings(google_enabled=True)
    _patch_settings(monkeypatch, settings)
    _patch_google_stack(monkeypatch)

    with _session_scope() as session:
        subcategory = _seed_naf(session)
        _seed_client(session, subcategory)
        _seed_google_retry_config(session)

        old_run_id = uuid4()
        backlog = models.Establishment(
            siret="11111111111111",
            siren="111111111",
            nic="11111",
            naf_code="56.10A",
            etat_administratif="A",
            name="Backlog Cafe",
            code_postal="75001",
            libelle_commune="Paris",
            categorie_entreprise="ME",
            categorie_juridique="1000",
            created_run_id=old_run_id,
            last_run_id=old_run_id,
            google_check_status="not_found",
            google_last_checked_at=utcnow() - timedelta(days=30),
        )
        session.add(backlog)
        session.commit()

        page_1 = {
            "header": {"curseur": "*", "curseurSuivant": "next", "total": 2},
            "etablissements": [
                _make_establishment_payload(siret="22222222222222", name="Bistro 1", naf_code="56.10A"),
                _make_establishment_payload(siret="33333333333333", name="Bistro 2", naf_code="56.10A"),
            ],
        }
        page_2 = {
            "header": {"curseur": "next", "curseurSuivant": None, "total": 2},
            "etablissements": [],
        }
        _patch_sirene_client(monkeypatch, [page_1, page_2])

        service = SyncService()
        run = service.run_sync(session)

        alerts = session.execute(select(models.Alert)).scalars().all()
        establishments = session.execute(select(models.Establishment)).scalars().all()

        assert run.status == "success"
        assert run.created_records == 2
        assert run.google_queue_count == 3
        assert run.google_matched_count == 3
        assert run.google_immediate_matched_count == 2
        assert run.google_late_matched_count == 1
        assert len(alerts) == 3
        assert len(establishments) == 3
        assert all(est.google_check_status == "found" for est in establishments)


def test_auto_full_empty_sirene_skips_client_zero_alerts_and_keeps_retry_checkpoint(monkeypatch):
    settings = _make_settings(google_enabled=True)
    settings.email.enabled = True
    settings.email.smtp_host = "localhost"
    _patch_settings(monkeypatch, settings)
    _patch_google_client(monkeypatch)

    sent_emails: list[dict[str, object]] = []

    def _capture_send(self, subject, body, recipients, *, html_body=None, reply_to=None, attachments=None):
        sent_emails.append(
            {
                "subject": subject,
                "body": body,
                "recipients": list(recipients),
                "html_body": html_body,
                "reply_to": reply_to,
                "attachments": attachments,
            }
        )

    import app.services.email_service as email_service

    monkeypatch.setattr(email_service.EmailService, "send", _capture_send)

    with _session_scope() as session:
        subcategory = _seed_naf(session)
        _seed_client(session, subcategory)
        _seed_google_retry_config(session)

        previous_success = models.SyncRun(
            scope_key=settings.sync.scope_key,
            run_type="sync",
            status="success",
            mode=SyncMode.FULL.value,
            finished_at=utcnow(),
        )
        session.add(previous_success)
        session.commit()

        _patch_sirene_client(
            monkeypatch,
            [
                {
                    "header": {"curseur": "*", "curseurSuivant": None, "total": 0},
                    "etablissements": [],
                }
            ],
            informations={
                "datesDernieresMisesAJourDesDonnees": [
                    {
                        "collection": "etablissements",
                        "dateDernierTraitementMaximum": "2026-02-20T00:00:00Z",
                    }
                ]
            },
        )

        service = SyncService()
        run = service._start_run(
            session,
            scope_key=settings.sync.scope_key,
            run_type="sync_auto",
            initial_status="running",
            mode=SyncMode.FULL,
        )
        state = service._get_or_create_state(session, settings.sync.scope_key)
        run.started_at = utcnow()
        session.commit()

        context = service._build_context(session, run, state)
        result = service._collect_sync(context)
        service._finish_run(
            run,
            state,
            last_treated_max=result.last_treated,
            last_creation_date=result.max_creation_date,
            mode=result.mode,
        )
        session.commit()

        session.refresh(state)
        assert run.status == "success"
        assert run.fetched_records == 0
        assert run.created_records == 0
        assert run.updated_records == 0
        assert result.last_treated is not None
        assert state.last_treated_max is None

        client_emails = [item for item in sent_emails if "client@example.com" in item["recipients"]]
        assert client_emails == []


def test_full_sync_flow_includes_linkedin_profile_in_client_email(monkeypatch):
    settings = _make_settings(google_enabled=True)
    settings.email.enabled = True
    settings.email.smtp_host = "localhost"
    _patch_settings(monkeypatch, settings)
    _patch_google_stack(monkeypatch)

    sent_emails: list[dict[str, object]] = []

    def _capture_send(self, subject, body, recipients, *, html_body=None, reply_to=None, attachments=None):
        sent_emails.append(
            {
                "subject": subject,
                "body": body,
                "recipients": list(recipients),
                "html_body": html_body,
                "reply_to": reply_to,
                "attachments": attachments,
            }
        )

    import app.services.email_service as email_service

    monkeypatch.setattr(email_service.EmailService, "send", _capture_send)

    with _session_scope() as session:
        subcategory = _seed_naf(session)
        _seed_client(session, subcategory)
        _seed_google_retry_config(session)

        previous_success = models.SyncRun(
            scope_key=settings.sync.scope_key,
            run_type="sync",
            status="success",
            mode=SyncMode.FULL.value,
            finished_at=utcnow(),
        )
        session.add(previous_success)

        old_run_id = uuid4()
        backlog = models.Establishment(
            siret="12121212121212",
            siren="121212121",
            nic="21212",
            naf_code="56.10A",
            etat_administratif="A",
            name="Backlog LinkedIn Cafe",
            code_postal="75001",
            libelle_commune="Paris",
            categorie_entreprise="ME",
            categorie_juridique="1000",
            created_run_id=old_run_id,
            last_run_id=old_run_id,
            google_check_status="not_found",
            google_last_checked_at=utcnow() - timedelta(days=30),
        )
        session.add(backlog)
        session.flush()
        session.add(
            models.Director(
                establishment_siret=backlog.siret,
                type_dirigeant="personne physique",
                first_names="Jane",
                last_name="Doe",
                linkedin_profile_url="https://linkedin.com/in/jane-doe",
                linkedin_profile_data={"title": "Dirigeante"},
            )
        )
        session.commit()

        page_1 = {
            "header": {"curseur": "*", "curseurSuivant": "next", "total": 1},
            "etablissements": [
                _make_establishment_payload(siret="23232323232323", name="Bistro Email", naf_code="56.10A"),
            ],
        }
        page_2 = {
            "header": {"curseur": "next", "curseurSuivant": None, "total": 1},
            "etablissements": [],
        }
        _patch_sirene_client(monkeypatch, [page_1, page_2])

        service = SyncService()
        run = service.run_sync(session)

        alerts = session.execute(select(models.Alert)).scalars().all()

        assert run.status == "success"
        assert len(alerts) == 2
        assert sent_emails

        client_emails = [
            item for item in sent_emails if "client@example.com" in item["recipients"]
        ]
        assert client_emails
        assert "https://linkedin.com/in/jane-doe" in (client_emails[0]["html_body"] or "")


def test_full_sync_alerts_include_linkedin_only_found_during_run(monkeypatch):
    settings = _make_settings(google_enabled=True)
    settings.email.enabled = True
    settings.email.smtp_host = "localhost"
    _patch_settings(monkeypatch, settings)
    _patch_google_client(monkeypatch)

    import app.services.sync.collector as collector_module
    import app.services.google_business.google_lookup_engine as lookup_engine
    import app.services.email_service as email_service

    monkeypatch.setattr(
        lookup_engine.GoogleLookupEngine,
        "lookup",
        lambda self, establishment, *, now=None: None,
    )

    def _fake_linkedin_enrichment(self, context, establishments, *, session_override=None, update_run_counters=True):
        session = session_override or context.session
        for establishment in establishments:
            session.add(
                models.Director(
                    establishment_siret=establishment.siret,
                    type_dirigeant="personne physique",
                    first_names="Alice",
                    last_name="Durand",
                    linkedin_profile_url=f"https://linkedin.com/in/{establishment.siret}",
                    linkedin_profile_data={"title": "CEO"},
                    linkedin_check_status="found",
                )
            )
        session.flush()
        return {
            "total_directors": len(establishments),
            "searched_count": len(establishments),
            "found_count": len(establishments),
            "not_found_count": 0,
            "error_count": 0,
        }

    monkeypatch.setattr(
        collector_module.SyncCollectorMixin,
        "_run_linkedin_enrichment",
        _fake_linkedin_enrichment,
    )

    sent_emails: list[dict[str, object]] = []

    def _capture_send(self, subject, body, recipients, *, html_body=None, reply_to=None, attachments=None):
        sent_emails.append(
            {
                "subject": subject,
                "body": body,
                "recipients": list(recipients),
                "html_body": html_body,
            }
        )

    monkeypatch.setattr(email_service.EmailService, "send", _capture_send)

    with _session_scope() as session:
        subcategory = _seed_naf(session)
        _seed_client(session, subcategory)
        _seed_google_retry_config(session)
        previous_success = models.SyncRun(
            scope_key=settings.sync.scope_key,
            run_type="sync",
            status="success",
            mode=SyncMode.FULL.value,
            finished_at=utcnow(),
        )
        session.add(previous_success)
        session.add(models.AdminRecipient(email="admin@example.com"))
        session.commit()

        page_1 = {
            "header": {"curseur": "*", "curseurSuivant": None, "total": 1},
            "etablissements": [
                _make_establishment_payload(
                    siret="24242424242424",
                    name="LinkedIn Sans Google",
                    naf_code="56.10A",
                ),
            ],
        }
        _patch_sirene_client(monkeypatch, [page_1])

        service = SyncService()
        run = service.run_sync(session)

        assert run.status == "success"

        alerts = session.execute(select(models.Alert)).scalars().all()
        assert len(alerts) == 1
        assert alerts[0].siret == "24242424242424"

        establishment = session.get(models.Establishment, "24242424242424")
        assert establishment is not None
        assert establishment.google_check_status != "found"

        admin_emails = [item for item in sent_emails if "admin@example.com" in item["recipients"]]
        assert admin_emails
        assert "https://linkedin.com/in/24242424242424" in (admin_emails[0]["html_body"] or "")

        client_emails = [item for item in sent_emails if "client@example.com" in item["recipients"]]
        assert client_emails
        assert "https://linkedin.com/in/24242424242424" in (client_emails[0]["html_body"] or "")


def test_sirene_only_flow_skips_google(monkeypatch):
    settings = _make_settings(google_enabled=True)
    _patch_settings(monkeypatch, settings)

    with _session_scope() as session:
        _seed_naf(session)

        page_1 = {
            "header": {"curseur": "*", "curseurSuivant": None, "total": 1},
            "etablissements": [
                _make_establishment_payload(siret="44444444444444", name="Sirene Only", naf_code="56.10A"),
            ],
        }
        _patch_sirene_client(monkeypatch, [page_1])

        service = SyncService()
        run = service._start_run(
            session,
            scope_key=settings.sync.scope_key,
            run_type="sync",
            initial_status="running",
            mode=SyncMode.SIRENE_ONLY,
        )
        state = service._get_or_create_state(session, settings.sync.scope_key)
        run.started_at = utcnow()
        session.commit()

        context = service._build_context(session, run, state)
        result = service._collect_sync(context)
        service._finish_run(
            run,
            state,
            last_treated_max=result.last_treated,
            last_creation_date=result.max_creation_date,
            mode=result.mode,
        )
        session.commit()

        assert run.status == "success"
        assert run.created_records == 1
        assert run.google_queue_count == 0
        assert run.google_api_call_count == 0
        assert run.google_matched_count == 0


def test_google_pending_flow_targets_unchecked_establishments(monkeypatch):
    settings = _make_settings(google_enabled=True)
    _patch_settings(monkeypatch, settings)
    _patch_google_stack(monkeypatch)

    with _session_scope() as session:
        _seed_google_retry_config(session)

        departments = list_departments(session)
        paris_department = next(department for department in departments if department.code == "75")
        client = models.Client(
            name="Client IDF",
            start_date=date(2024, 1, 1),
            listing_statuses=["recent_creation"],
        )
        session.add(client)
        session.flush()
        session.add(models.ClientDepartment(client_id=client.id, department_id=paris_department.id))
        session.commit()

        pending = models.Establishment(
            siret="55555555555555",
            siren="555555555",
            nic="55555",
            naf_code="56.10A",
            etat_administratif="A",
            name="Pending Cafe",
            code_postal="75001",
            libelle_commune="Paris",
            categorie_entreprise="ME",
            categorie_juridique="1000",
            google_check_status="pending",
            google_last_checked_at=None,
        )
        session.add(pending)
        session.commit()

        _patch_sirene_client(monkeypatch, [])

        service = SyncService()
        run = service._start_run(
            session,
            scope_key=settings.sync.scope_key,
            run_type="google_sync",
            initial_status="running",
            mode=SyncMode.GOOGLE_PENDING,
        )
        state = service._get_or_create_state(session, settings.sync.scope_key)
        run.started_at = utcnow()
        session.commit()

        context = service._build_context(session, run, state)
        result = service._collect_sync(context)
        service._finish_run(
            run,
            state,
            last_treated_max=result.last_treated,
            last_creation_date=result.max_creation_date,
            mode=result.mode,
        )
        session.commit()

        refreshed = session.get(models.Establishment, "55555555555555")

        assert run.status == "success"
        assert run.created_records == 0
        assert run.fetched_records == 0
        assert run.google_matched_count == 1
        assert refreshed.google_check_status == "found"


def test_google_pending_flow_marks_insufficient_without_clients(monkeypatch):
    settings = _make_settings(google_enabled=True)
    _patch_settings(monkeypatch, settings)
    _patch_google_client(monkeypatch)

    with _session_scope() as session:
        _seed_google_retry_config(session)

        pending = models.Establishment(
            siret="66666666666666",
            siren="666666666",
            nic="66666",
            naf_code="56.10A",
            etat_administratif="A",
            name=None,
            code_postal=None,
            libelle_commune=None,
            categorie_entreprise="ME",
            categorie_juridique="1000",
            google_check_status="pending",
            google_last_checked_at=None,
        )
        session.add(pending)
        session.commit()

        _patch_sirene_client(monkeypatch, [])

        service = SyncService()
        run = service._start_run(
            session,
            scope_key=settings.sync.scope_key,
            run_type="google_sync",
            initial_status="running",
            mode=SyncMode.GOOGLE_PENDING,
        )
        state = service._get_or_create_state(session, settings.sync.scope_key)
        run.started_at = utcnow()
        session.commit()

        context = service._build_context(session, run, state)
        result = service._collect_sync(context)
        service._finish_run(
            run,
            state,
            last_treated_max=result.last_treated,
            last_creation_date=result.max_creation_date,
            mode=result.mode,
        )
        session.commit()

        refreshed = session.get(models.Establishment, "66666666666666")

        assert run.status == "success"
        assert run.google_queue_count == 1
        assert run.google_matched_count == 0
        assert refreshed.google_check_status == "insufficient"


def test_google_pending_flow_marks_insufficient_without_name(monkeypatch):
    settings = _make_settings(google_enabled=True)
    _patch_settings(monkeypatch, settings)
    _patch_google_client(monkeypatch)

    with _session_scope() as session:
        _seed_google_retry_config(session)

        departments = list_departments(session)
        paris_department = next(department for department in departments if department.code == "75")
        client = models.Client(
            name="Client IDF",
            start_date=date(2024, 1, 1),
            listing_statuses=["recent_creation"],
        )
        session.add(client)
        session.flush()
        session.add(models.ClientDepartment(client_id=client.id, department_id=paris_department.id))
        session.commit()

        pending = models.Establishment(
            siret="88888888888888",
            siren="888888888",
            nic="88888",
            naf_code="56.10A",
            etat_administratif="A",
            name=None,
            code_postal="75001",
            libelle_commune="Paris",
            categorie_entreprise="ME",
            categorie_juridique="1000",
            google_check_status="pending",
            google_last_checked_at=None,
        )
        session.add(pending)
        session.commit()

        _patch_sirene_client(monkeypatch, [])

        service = SyncService()
        run = service._start_run(
            session,
            scope_key=settings.sync.scope_key,
            run_type="google_sync",
            initial_status="running",
            mode=SyncMode.GOOGLE_PENDING,
        )
        state = service._get_or_create_state(session, settings.sync.scope_key)
        run.started_at = utcnow()
        session.commit()

        context = service._build_context(session, run, state)
        result = service._collect_sync(context)
        service._finish_run(
            run,
            state,
            last_treated_max=result.last_treated,
            last_creation_date=result.max_creation_date,
            mode=result.mode,
        )
        session.commit()

        refreshed = session.get(models.Establishment, "88888888888888")

        assert run.status == "success"
        assert run.google_queue_count == 1
        assert run.google_matched_count == 0
        assert refreshed.google_check_status == "insufficient"


def test_google_pending_flow_marks_insufficient_for_non_diffusible_name(monkeypatch):
    settings = _make_settings(google_enabled=True)
    _patch_settings(monkeypatch, settings)
    _patch_google_client(monkeypatch)

    with _session_scope() as session:
        _seed_google_retry_config(session)

        departments = list_departments(session)
        paris_department = next(department for department in departments if department.code == "75")
        client = models.Client(
            name="Client IDF",
            start_date=date(2024, 1, 1),
            listing_statuses=["recent_creation"],
        )
        session.add(client)
        session.flush()
        session.add(models.ClientDepartment(client_id=client.id, department_id=paris_department.id))
        session.commit()

        pending = models.Establishment(
            siret="99999999999999",
            siren="999999999",
            nic="99999",
            naf_code="56.10A",
            etat_administratif="A",
            name="[ND]",
            code_postal="75001",
            libelle_commune="Paris",
            categorie_entreprise="ME",
            categorie_juridique="1000",
            google_check_status="pending",
            google_last_checked_at=None,
        )
        session.add(pending)
        session.commit()

        _patch_sirene_client(monkeypatch, [])

        service = SyncService()
        run = service._start_run(
            session,
            scope_key=settings.sync.scope_key,
            run_type="google_sync",
            initial_status="running",
            mode=SyncMode.GOOGLE_PENDING,
        )
        state = service._get_or_create_state(session, settings.sync.scope_key)
        run.started_at = utcnow()
        session.commit()

        context = service._build_context(session, run, state)
        result = service._collect_sync(context)
        service._finish_run(
            run,
            state,
            last_treated_max=result.last_treated,
            last_creation_date=result.max_creation_date,
            mode=result.mode,
        )
        session.commit()

        refreshed = session.get(models.Establishment, "99999999999999")

        assert run.status == "success"
        assert run.google_queue_count == 0
        assert run.google_matched_count == 0
        assert refreshed.google_check_status == "insufficient"


def test_day_replay_cached_admin_email_includes_linkedin_only_establishments(monkeypatch):
    """Day replay with Google-found + LinkedIn-only establishments sends admin email with both.

    Reproduces user scenario: replay on a date with some Google-found establishments
    and some establishments where only LinkedIn profiles were found (no Google listing).
    The admin email must contain both types.
    """
    settings = _make_settings(google_enabled=True)
    settings.email.enabled = True
    settings.email.smtp_host = "localhost"
    _patch_settings(monkeypatch, settings)
    _patch_sirene_client(monkeypatch, [])

    sent_emails: list[dict[str, object]] = []

    def _capture_send(self, subject, body, recipients, *, html_body=None, reply_to=None, attachments=None):
        sent_emails.append(
            {
                "subject": subject,
                "body": body,
                "recipients": list(recipients),
                "html_body": html_body,
            }
        )

    import app.services.email_service as email_service

    monkeypatch.setattr(email_service.EmailService, "send", _capture_send)

    with _session_scope() as session:
        replay_date = date(2026, 1, 15)

        session.add(models.AdminRecipient(email="admin@example.com"))

        # Establishment with Google listing found
        google_found = models.Establishment(
            siret="77777777777777",
            siren="777777777",
            nic="77777",
            naf_code="56.10A",
            etat_administratif="A",
            name="Google Bistro",
            code_postal="75001",
            libelle_commune="Paris",
            categorie_entreprise="ME",
            categorie_juridique="1000",
            date_creation=replay_date,
            google_check_status="found",
            google_place_url="https://maps.google.com/?q=77777777777777",
            google_place_id="ChIJgoogle123",
        )
        # Establishment WITHOUT Google listing but WITH LinkedIn profile on director
        linkedin_only = models.Establishment(
            siret="78787878787878",
            siren="787878787",
            nic="87878",
            naf_code="56.10A",
            etat_administratif="A",
            name="LinkedIn Bistro",
            code_postal="75001",
            libelle_commune="Paris",
            categorie_entreprise="ME",
            categorie_juridique="1000",
            date_creation=replay_date,
            google_check_status="not_found",
        )
        # Establishment without Google AND without LinkedIn (should NOT appear in email)
        neither = models.Establishment(
            siret="79797979797979",
            siren="797979797",
            nic="97979",
            naf_code="56.10A",
            etat_administratif="A",
            name="Neither Bistro",
            code_postal="75001",
            libelle_commune="Paris",
            categorie_entreprise="ME",
            categorie_juridique="1000",
            date_creation=replay_date,
            google_check_status="not_found",
        )
        session.add_all([google_found, linkedin_only, neither])
        session.flush()

        # Add LinkedIn-found director to the linkedin_only establishment
        session.add(
            models.Director(
                establishment_siret=linkedin_only.siret,
                type_dirigeant="personne physique",
                first_names="Jane",
                last_name="Doe",
                linkedin_profile_url="https://linkedin.com/in/jane-doe",
                linkedin_profile_data={"title": "Dirigeante"},
                linkedin_check_status="found",
            )
        )
        # Add director WITHOUT linkedin to the "neither" establishment
        session.add(
            models.Director(
                establishment_siret=neither.siret,
                type_dirigeant="personne physique",
                first_names="Jean",
                last_name="Martin",
                linkedin_check_status="not_found",
            )
        )
        session.commit()

        # --- Crucial: new service, fresh context (simulates background task) ---
        service = SyncService()
        run = service._start_run(
            session,
            scope_key=settings.sync.scope_key,
            run_type="sync_replay",
            initial_status="running",
            mode=SyncMode.DAY_REPLAY,
        )
        run.replay_for_date = replay_date
        run.day_replay_force_google = False
        state = service._get_or_create_state(session, settings.sync.scope_key)
        run.started_at = utcnow()
        session.commit()  # Expire all objects (simulates background task session)

        context = service._build_context(session, run, state)
        result = service._collect_sync(context)
        service._finish_run(
            run,
            state,
            last_treated_max=result.last_treated,
            last_creation_date=result.max_creation_date,
            mode=result.mode,
        )
        session.commit()

        assert run.status == "success"

        # Verify alerts were created for Google-found AND LinkedIn-only (but NOT "neither")
        alerts = session.execute(select(models.Alert).where(models.Alert.run_id == run.id)).scalars().all()
        alert_sirets = {alert.siret for alert in alerts}
        assert "77777777777777" in alert_sirets, "Google-found establishment must have an alert"
        assert "78787878787878" in alert_sirets, "LinkedIn-only establishment must have an alert"
        assert "79797979797979" not in alert_sirets, "Establishment without Google/LinkedIn must NOT have an alert"

        # Verify admin email was sent and contains both Google and LinkedIn info
        assert sent_emails, "At least one email must be sent"
        admin_mails = [email for email in sent_emails if "admin@example.com" in email["recipients"]]
        assert admin_mails, "Admin email must be sent"
        html_body = admin_mails[0]["html_body"] or ""
        assert "Google Bistro" in html_body, "Google establishment name must appear in admin email"
        assert "LinkedIn Bistro" in html_body, "LinkedIn establishment name must appear in admin email"
        assert "https://linkedin.com/in/jane-doe" in html_body, "LinkedIn profile URL must appear in admin email"
        assert "Neither Bistro" not in html_body, "Establishment without Google/LinkedIn must NOT appear"


def test_day_replay_insertion_date_reference_includes_linkedin(monkeypatch):
    """Day replay with INSERTION_DATE reference correctly loads LinkedIn-only establishments."""
    settings = _make_settings(google_enabled=True)
    settings.email.enabled = True
    settings.email.smtp_host = "localhost"
    _patch_settings(monkeypatch, settings)
    _patch_sirene_client(monkeypatch, [])

    sent_emails: list[dict[str, object]] = []

    def _capture_send(self, subject, body, recipients, *, html_body=None, reply_to=None, attachments=None):
        sent_emails.append({"recipients": list(recipients), "html_body": html_body})

    import app.services.email_service as email_service

    monkeypatch.setattr(email_service.EmailService, "send", _capture_send)

    from datetime import datetime as dt

    with _session_scope() as session:
        insertion_datetime = dt(2026, 1, 15, 10, 30, 0)
        replay_date = date(2026, 1, 15)

        session.add(models.AdminRecipient(email="admin@example.com"))

        google_found = models.Establishment(
            siret="80808080808080",
            siren="808080808",
            nic="08080",
            naf_code="56.10A",
            etat_administratif="A",
            name="Insertion Google",
            code_postal="75001",
            libelle_commune="Paris",
            categorie_entreprise="ME",
            categorie_juridique="1000",
            date_creation=date(2025, 12, 1),
            first_seen_at=insertion_datetime,
            google_check_status="found",
            google_place_url="https://maps.google.com/?q=80808080808080",
        )
        linkedin_only = models.Establishment(
            siret="81818181818181",
            siren="818181818",
            nic="18181",
            naf_code="56.10A",
            etat_administratif="A",
            name="Insertion LinkedIn",
            code_postal="75002",
            libelle_commune="Paris",
            categorie_entreprise="ME",
            categorie_juridique="1000",
            date_creation=date(2025, 12, 1),
            first_seen_at=insertion_datetime,
            google_check_status="not_found",
        )
        session.add_all([google_found, linkedin_only])
        session.flush()
        session.add(
            models.Director(
                establishment_siret=linkedin_only.siret,
                type_dirigeant="personne physique",
                first_names="Alice",
                last_name="Durand",
                linkedin_profile_url="https://linkedin.com/in/alice-durand",
                linkedin_profile_data={"title": "CEO"},
                linkedin_check_status="found",
            )
        )
        session.commit()

        service = SyncService()
        run = service._start_run(
            session,
            scope_key=settings.sync.scope_key,
            run_type="sync_replay",
            initial_status="running",
            mode=SyncMode.DAY_REPLAY,
        )
        run.replay_for_date = replay_date
        run.day_replay_reference = "insertion_date"
        run.day_replay_force_google = False
        state = service._get_or_create_state(session, settings.sync.scope_key)
        run.started_at = utcnow()
        session.commit()

        context = service._build_context(session, run, state)
        result = service._collect_sync(context)
        service._finish_run(
            run,
            state,
            last_treated_max=result.last_treated,
            last_creation_date=result.max_creation_date,
            mode=result.mode,
        )
        session.commit()

        assert run.status == "success"

        alerts = session.execute(select(models.Alert).where(models.Alert.run_id == run.id)).scalars().all()
        alert_sirets = {alert.siret for alert in alerts}
        assert "80808080808080" in alert_sirets
        assert "81818181818181" in alert_sirets

        admin_mails = [email for email in sent_emails if "admin@example.com" in email["recipients"]]
        assert admin_mails
        html_body = admin_mails[0]["html_body"] or ""
        assert "https://linkedin.com/in/alice-durand" in html_body


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
