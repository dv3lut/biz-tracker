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


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
