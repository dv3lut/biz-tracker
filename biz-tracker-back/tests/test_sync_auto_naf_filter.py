"""Tests: automatic sync skips NAF subcategories with no client subscriptions."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.db import models
from app.db.base import Base
from app.services.sync.mode import SyncMode
from app.services.sync_service import SyncService
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


def _make_settings():
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
            enabled=False,
            api_key=None,
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


def _seed_naf(session, *, naf_code="56.10A", name="Restaurants"):
    category = models.NafCategory(
        name=f"Cat-{naf_code}",
        description=None,
        keywords=[],
    )
    session.add(category)
    session.flush()
    subcategory = models.NafSubCategory(
        name=name,
        description=None,
        naf_code=naf_code,
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


def _seed_client_with_subscription(session, subcategory, *, department_codes=None):
    client = models.Client(
        name=f"Client-{subcategory.naf_code}",
        start_date=date.today(),
        end_date=None,
        listing_statuses=["recent_creation"],
    )
    session.add(client)
    session.flush()
    session.add(models.ClientRecipient(client_id=client.id, email="c@example.com"))
    session.add(models.ClientSubscription(client_id=client.id, subcategory_id=subcategory.id))
    if department_codes:
        for code in department_codes:
            department = models.Department(
                region_id=_ensure_region(session).id,
                code=code,
                name=f"Dept {code}",
            )
            session.add(department)
            session.flush()
            session.add(models.ClientDepartment(client_id=client.id, department_id=department.id))
    session.flush()
    return client


def _ensure_region(session):
    from sqlalchemy import select as _select

    instance = session.execute(
        _select(models.Region).where(models.Region.code == "TEST")
    ).scalars().first()
    if instance is not None:
        return instance
    instance = models.Region(code="TEST", name="Test region")
    session.add(instance)
    session.flush()
    return instance


# ---------------------------------------------------------------------------
# Unit tests: _load_subscribed_naf_codes
# ---------------------------------------------------------------------------


def test_load_subscribed_naf_codes_returns_only_subscribed(monkeypatch):
    settings = _make_settings()
    _patch_settings(monkeypatch, settings)

    with _session_scope() as session:
        sub_a = _seed_naf(session, naf_code="56.10A", name="Restaurants")
        _seed_naf(session, naf_code="56.21Z", name="Traiteurs")  # no subscription
        _seed_client_with_subscription(session, sub_a)
        session.commit()

        service = SyncService()
        result = service._load_subscribed_naf_codes(session)
        assert result == ["56.10A"]


def test_load_subscribed_naf_codes_empty_when_no_subscriptions(monkeypatch):
    settings = _make_settings()
    _patch_settings(monkeypatch, settings)

    with _session_scope() as session:
        _seed_naf(session, naf_code="56.10A")
        _seed_naf(session, naf_code="56.21Z")
        session.commit()

        service = SyncService()
        result = service._load_subscribed_naf_codes(session)
        assert result == []


def test_load_subscribed_naf_codes_excludes_inactive(monkeypatch):
    settings = _make_settings()
    _patch_settings(monkeypatch, settings)

    with _session_scope() as session:
        sub = _seed_naf(session, naf_code="56.10A")
        sub.is_active = False
        session.flush()
        _seed_client_with_subscription(session, sub)
        session.commit()

        service = SyncService()
        result = service._load_subscribed_naf_codes(session)
        assert result == []


# ---------------------------------------------------------------------------
# Integration tests: _collect_sync behaviour for sync_auto
# ---------------------------------------------------------------------------


def _make_establishment_payload(*, siret, name, naf_code, code_postal="75001", libelle_commune="PARIS"):
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
        "adresseEtablissement": {
            "codePostalEtablissement": code_postal,
            "libelleCommuneEtablissement": libelle_commune,
            "numeroVoieEtablissement": "1",
            "typeVoieEtablissement": "RUE",
            "libelleVoieEtablissement": "DU TEST",
        },
        "periodesEtablissement": [
            {
                "activitePrincipaleEtablissement": naf_code.replace(".", ""),
                "etatAdministratifEtablissement": "A",
                "denominationUsuelleEtablissement": name,
                "enseigne1Etablissement": None,
            }
        ],
    }


def test_collect_sync_auto_skips_when_no_subscriptions(monkeypatch):
    """sync_auto returns empty SyncResult when no client subscribes to any NAF code."""
    settings = _make_settings()
    _patch_settings(monkeypatch, settings)
    _patch_sirene_client(monkeypatch, [])

    with _session_scope() as session:
        _seed_naf(session, naf_code="56.10A")
        session.commit()

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

        assert result.new_establishments == []
        assert "aucun" in (run.notes or "").lower()


def test_collect_sync_auto_uses_only_subscribed_codes(monkeypatch):
    """sync_auto builds Sirene query with only subscribed NAF codes."""
    settings = _make_settings()
    _patch_settings(monkeypatch, settings)

    page = {
        "header": {"curseur": "*", "curseurSuivant": None, "total": 1},
        "etablissements": [
            _make_establishment_payload(siret="12345678901234", name="Test", naf_code="56.10A"),
        ],
    }
    _patch_sirene_client(monkeypatch, [page])

    with _session_scope() as session:
        sub_a = _seed_naf(session, naf_code="56.10A", name="Restaurants")
        _seed_naf(session, naf_code="56.21Z", name="Traiteurs")
        _seed_client_with_subscription(session, sub_a)
        session.commit()

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

        notes = run.notes or ""
        # 56.21Z should be noted as skipped (no subscriber)
        assert "56.21Z" in notes
        assert "ignorée" in notes
        assert len(result.new_establishments) == 1


def test_load_subscribed_naf_department_pairs_restricts_to_client_departments(monkeypatch):
    """Subscriber with a department filter restricts allowed departments for that NAF."""
    settings = _make_settings()
    _patch_settings(monkeypatch, settings)

    with _session_scope() as session:
        sub = _seed_naf(session, naf_code="56.10A", name="Restaurants")
        _seed_client_with_subscription(session, sub, department_codes=["75", "92"])
        session.commit()

        service = SyncService()
        result = service._load_subscribed_naf_department_pairs(session)
        assert result == {"56.10A": {"75", "92"}}


def test_load_subscribed_naf_department_pairs_unrestricted_when_client_has_no_departments(monkeypatch):
    """A subscriber without any department configured covers every department for that NAF."""
    settings = _make_settings()
    _patch_settings(monkeypatch, settings)

    with _session_scope() as session:
        sub = _seed_naf(session, naf_code="56.10A", name="Restaurants")
        _seed_client_with_subscription(session, sub)  # no department_codes
        session.commit()

        service = SyncService()
        result = service._load_subscribed_naf_department_pairs(session)
        assert result == {"56.10A": None}


def test_collect_sync_auto_skips_establishments_outside_subscribed_departments(monkeypatch):
    """sync_auto must drop establishments whose département has no subscriber for the NAF."""
    settings = _make_settings()
    _patch_settings(monkeypatch, settings)

    page = {
        "header": {"curseur": "*", "curseurSuivant": None, "total": 2},
        "etablissements": [
            _make_establishment_payload(
                siret="11111111111111",
                name="Paris-Restau",
                naf_code="56.10A",
                code_postal="75001",
                libelle_commune="PARIS",
            ),
            _make_establishment_payload(
                siret="22222222222222",
                name="Lyon-Restau",
                naf_code="56.10A",
                code_postal="69001",
                libelle_commune="LYON",
            ),
        ],
    }
    _patch_sirene_client(monkeypatch, [page])

    with _session_scope() as session:
        sub = _seed_naf(session, naf_code="56.10A", name="Restaurants")
        _seed_client_with_subscription(session, sub, department_codes=["75"])
        session.commit()

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

        sirets = sorted(est.siret for est in result.new_establishments)
        assert sirets == ["11111111111111"]


def test_collect_sync_auto_keeps_establishments_when_subscriber_targets_all_departments(monkeypatch):
    """sync_auto keeps every establishment when at least one subscriber has no département filter."""
    settings = _make_settings()
    _patch_settings(monkeypatch, settings)

    page = {
        "header": {"curseur": "*", "curseurSuivant": None, "total": 2},
        "etablissements": [
            _make_establishment_payload(
                siret="11111111111111",
                name="Paris-Restau",
                naf_code="56.10A",
                code_postal="75001",
                libelle_commune="PARIS",
            ),
            _make_establishment_payload(
                siret="22222222222222",
                name="Lyon-Restau",
                naf_code="56.10A",
                code_postal="69001",
                libelle_commune="LYON",
            ),
        ],
    }
    _patch_sirene_client(monkeypatch, [page])

    with _session_scope() as session:
        sub = _seed_naf(session, naf_code="56.10A", name="Restaurants")
        _seed_client_with_subscription(session, sub)  # no department restriction
        session.commit()

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

        assert {est.siret for est in result.new_establishments} == {
            "11111111111111",
            "22222222222222",
        }


def test_collect_sync_manual_does_not_apply_department_filter(monkeypatch):
    """Manual sync runs ignore the (NAF, département) subscription filter."""
    settings = _make_settings()
    _patch_settings(monkeypatch, settings)

    page = {
        "header": {"curseur": "*", "curseurSuivant": None, "total": 1},
        "etablissements": [
            _make_establishment_payload(
                siret="22222222222222",
                name="Lyon-Restau",
                naf_code="56.10A",
                code_postal="69001",
                libelle_commune="LYON",
            ),
        ],
    }
    _patch_sirene_client(monkeypatch, [page])

    with _session_scope() as session:
        sub = _seed_naf(session, naf_code="56.10A", name="Restaurants")
        _seed_client_with_subscription(session, sub, department_codes=["75"])
        session.commit()

        service = SyncService()
        run = service._start_run(
            session,
            scope_key=settings.sync.scope_key,
            run_type="sync",  # manual run
            initial_status="running",
            mode=SyncMode.FULL,
        )
        state = service._get_or_create_state(session, settings.sync.scope_key)
        run.started_at = utcnow()
        session.commit()

        context = service._build_context(session, run, state)
        result = service._collect_sync(context)

        assert len(result.new_establishments) == 1


def test_collect_sync_manual_uses_all_active_codes(monkeypatch):
    """Non-auto sync uses all active NAF codes regardless of subscriptions."""
    settings = _make_settings()
    _patch_settings(monkeypatch, settings)

    page = {
        "header": {"curseur": "*", "curseurSuivant": None, "total": 1},
        "etablissements": [
            _make_establishment_payload(siret="12345678901234", name="Test", naf_code="56.10A"),
        ],
    }
    _patch_sirene_client(monkeypatch, [page])

    with _session_scope() as session:
        _seed_naf(session, naf_code="56.10A", name="Restaurants")
        _seed_naf(session, naf_code="56.21Z", name="Traiteurs")
        # No subscriptions at all
        session.commit()

        service = SyncService()
        run = service._start_run(
            session,
            scope_key=settings.sync.scope_key,
            run_type="sync",
            initial_status="running",
            mode=SyncMode.FULL,
        )
        state = service._get_or_create_state(session, settings.sync.scope_key)
        run.started_at = utcnow()
        session.commit()

        context = service._build_context(session, run, state)
        result = service._collect_sync(context)

        # Manual sync should use all active codes, even without subscriptions
        assert len(result.new_establishments) == 1
        # No "ignorée" note since manual sync doesn't filter
        assert "ignorée" not in (run.notes or "")
