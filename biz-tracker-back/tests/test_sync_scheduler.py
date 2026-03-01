from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.db import models
from app.db.base import Base
from app.services.sync_scheduler import count_retryable_auto_runs_for_latest_treated
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


def test_count_retryable_auto_runs_for_latest_treated_counts_failed_and_empty_success():
    now = utcnow()
    latest_treated = datetime(2026, 2, 24, 6, 0, 0)
    previous_treated = datetime(2026, 2, 23, 6, 0, 0)
    notes_for_current_cycle = f"dateDernierTraitementMaximum: {latest_treated.isoformat()}"
    notes_for_previous_cycle = f"dateDernierTraitementMaximum: {previous_treated.isoformat()}"

    with _session_scope() as session:
        session.add_all(
            [
                models.SyncRun(
                    scope_key="default",
                    run_type="sync_auto",
                    status="failed",
                    mode="full",
                    started_at=now,
                    notes=notes_for_current_cycle,
                ),
                models.SyncRun(
                    scope_key="default",
                    run_type="sync_auto",
                    status="success",
                    mode="full",
                    started_at=now,
                    created_records=0,
                    updated_records=0,
                    notes=notes_for_current_cycle,
                ),
                models.SyncRun(
                    scope_key="default",
                    run_type="sync_auto",
                    status="success",
                    mode="full",
                    started_at=now,
                    created_records=1,
                    updated_records=0,
                    notes=notes_for_current_cycle,
                ),
                models.SyncRun(
                    scope_key="default",
                    run_type="sync",
                    status="failed",
                    mode="full",
                    started_at=now,
                    notes=notes_for_current_cycle,
                ),
                models.SyncRun(
                    scope_key="default",
                    run_type="sync_auto",
                    status="failed",
                    mode="full",
                    started_at=now - timedelta(days=1),
                    notes=notes_for_previous_cycle,
                ),
            ]
        )
        session.commit()

        counted = count_retryable_auto_runs_for_latest_treated(
            session,
            scope_key="default",
            latest_treated=latest_treated,
        )

    assert counted == 2


def test_scheduler_tick_skips_when_retry_limit_reached(monkeypatch):
    import app.services.sync_scheduler as scheduler_module

    with _session_scope() as session:
        for _ in range(4):
            session.add(
                models.SyncRun(
                    scope_key="default",
                    run_type="sync_auto",
                    status="failed",
                    mode="full",
                    started_at=utcnow(),
                    notes="dateDernierTraitementMaximum: 2026-02-24T06:00:00",
                )
            )
        session.commit()

        @contextmanager
        def fake_session_scope():
            yield session

        class FakeSyncService:
            def __init__(self) -> None:
                self.settings = SimpleNamespace(
                    sync=SimpleNamespace(
                        scope_key="default",
                        minimum_delay_minutes=0,
                        auto_retry_max_attempts=4,
                        auto_poll_minutes=15,
                    )
                )
                self.prepare_called = False

            def has_active_run(self, _session, _scope_key):
                return False

            def _fetch_latest_treated(self):
                return datetime(2026, 2, 24, 6, 0, 0)

            def prepare_sync_run(self, *_args, **_kwargs):
                self.prepare_called = True
                return None

            def execute_sync_run(self, *_args, **_kwargs):
                return None

        events: list[tuple[str, dict[str, object]]] = []

        monkeypatch.setattr(scheduler_module, "session_scope", fake_session_scope)
        monkeypatch.setattr(scheduler_module, "SyncService", FakeSyncService)
        monkeypatch.setattr(
            scheduler_module,
            "send_weekly_stripe_summary_if_due",
            lambda *_args, **_kwargs: None,
        )
        monkeypatch.setattr(
            scheduler_module,
            "get_settings",
            lambda: SimpleNamespace(
                is_local=False,
                sync=SimpleNamespace(
                    scope_key="default",
                    auto_enabled=True,
                    auto_poll_minutes=15,
                ),
            ),
        )
        monkeypatch.setattr(
            scheduler_module,
            "log_event",
            lambda event_name, **fields: events.append((event_name, fields)),
        )

        scheduler = scheduler_module.SyncScheduler()
        scheduler._tick()

        assert scheduler._service.prepare_called is False
        assert any(
            event_name == "scheduler.skip" and fields.get("reason") == "retry_limit_reached"
            for event_name, fields in events
        )


def test_scheduler_tick_allows_run_when_retry_limit_not_reached(monkeypatch):
    import app.services.sync_scheduler as scheduler_module

    with _session_scope() as session:
        for _ in range(3):
            session.add(
                models.SyncRun(
                    scope_key="default",
                    run_type="sync_auto",
                    status="failed",
                    mode="full",
                    started_at=utcnow(),
                    notes="dateDernierTraitementMaximum: 2026-02-24T06:00:00",
                )
            )
        session.commit()

        @contextmanager
        def fake_session_scope():
            yield session

        class FakeSyncService:
            def __init__(self) -> None:
                self.settings = SimpleNamespace(
                    sync=SimpleNamespace(
                        scope_key="default",
                        minimum_delay_minutes=0,
                        auto_retry_max_attempts=4,
                        auto_poll_minutes=15,
                    )
                )
                self.prepare_called = False

            def has_active_run(self, _session, _scope_key):
                return False

            def _fetch_latest_treated(self):
                return datetime(2026, 2, 24, 6, 0, 0)

            def prepare_sync_run(self, *_args, **_kwargs):
                self.prepare_called = True
                return None

            def execute_sync_run(self, *_args, **_kwargs):
                return None

        monkeypatch.setattr(scheduler_module, "session_scope", fake_session_scope)
        monkeypatch.setattr(scheduler_module, "SyncService", FakeSyncService)
        monkeypatch.setattr(
            scheduler_module,
            "send_weekly_stripe_summary_if_due",
            lambda *_args, **_kwargs: None,
        )
        monkeypatch.setattr(
            scheduler_module,
            "get_settings",
            lambda: SimpleNamespace(
                is_local=False,
                sync=SimpleNamespace(
                    scope_key="default",
                    auto_enabled=True,
                    auto_poll_minutes=15,
                ),
            ),
        )
        monkeypatch.setattr(scheduler_module, "log_event", lambda *_args, **_kwargs: None)

        scheduler = scheduler_module.SyncScheduler()
        scheduler._tick()

        assert scheduler._service.prepare_called is True
