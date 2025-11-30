from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.routers.admin import common
from app.services.sync.mode import SyncMode
from app.utils.dates import utcnow


def _make_sync_run(*, mode: SyncMode = SyncMode.FULL, status: str = "running") -> SimpleNamespace:
    now = utcnow()
    return SimpleNamespace(
        id=uuid4(),
        scope_key="restaurants",
        run_type="full",
        status=status,
        mode=mode,
        replay_for_date=None,
        started_at=now - timedelta(seconds=30),
        finished_at=None,
        api_call_count=10,
        google_api_call_count=5,
        fetched_records=50,
        created_records=10,
        google_queue_count=0,
        google_eligible_count=0,
        google_matched_count=0,
        google_pending_count=0,
        google_immediate_matched_count=0,
        google_late_matched_count=0,
        updated_records=0,
        summary=None,
        last_cursor=None,
        query_checksum=None,
        resumed_from_run_id=None,
        notes=None,
        target_naf_codes=None,
        target_client_ids=None,
        notify_admins=True,
        day_replay_force_google=False,
        day_replay_reference="creation_date",
    )


def _make_state(last_total: int | None) -> SimpleNamespace:
    return SimpleNamespace(last_total=last_total)


def test_compute_run_metrics_calculates_progress_and_eta():
    run = _make_sync_run()
    run.max_records = 200
    state = _make_state(last_total=None)

    total_expected, progress, remaining, eta = common.compute_run_metrics(run, state)

    assert total_expected == 200
    assert 0.0 < progress < 1.0
    assert remaining is not None and remaining >= 0
    assert eta is not None and eta >= utcnow()


def test_compute_run_metrics_handles_missing_totals():
    run = _make_sync_run(status="pending")
    run.max_records = "not-a-number"
    state = _make_state(last_total="unknown")

    total_expected, progress, remaining, eta = common.compute_run_metrics(run, state)

    assert total_expected is None
    assert progress is None
    assert remaining is None
    assert eta is None


def test_serialize_run_resets_progress_for_google_only_modes():
    run = _make_sync_run(mode=SyncMode.GOOGLE_PENDING)
    run.max_records = 120
    state = _make_state(last_total=120)

    enriched = common.serialize_run(run, state=state)

    assert enriched is not None
    assert enriched.progress is None
    assert enriched.total_expected_records is None
    assert enriched.estimated_completion_at is None


def test_format_establishment_summary_includes_google_fields():
    establishment = SimpleNamespace(
        name="Test",
        siret="12345678901234",
        naf_code="5610A",
        numero_voie="10",
        type_voie="Rue",
        libelle_voie="du Test",
        code_postal="75000",
        libelle_commune="Paris",
        libelle_commune_etranger=None,
        date_creation=datetime(2020, 5, 1).date(),
        google_place_url="https://maps.google.com/123",
        google_place_id="place-id",
        google_match_confidence=0.9876,
    )

    lines = common.format_establishment_summary(establishment)

    assert any("SIRET" in line for line in lines)
    assert any("Google" in line for line in lines)
    assert any("Score" in line for line in lines)


def test_normalize_emails_deduplicates_and_trims():
    normalized = common.normalize_emails([
        " ADMIN@Example.com ",
        "",
        "admin@example.com",
        "Ops@example.com",
    ])

    assert normalized == ["admin@example.com", "ops@example.com"]