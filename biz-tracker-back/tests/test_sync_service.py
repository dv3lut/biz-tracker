from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.config import Settings
from app.services.sync_service import SyncService


def test_sync_service_exposes_settings() -> None:
    service = SyncService()
    assert isinstance(service.settings, Settings)


def test_run_sync_sends_admin_email_when_run_fails(monkeypatch) -> None:
    monkeypatch.setattr("app.services.sync.runner.serialize_sync_run", lambda _run: {})
    monkeypatch.setattr("app.services.sync.runner.log_event", lambda *_args, **_kwargs: None)

    service = SyncService()
    session = Mock()
    session.rollback = Mock()
    session.commit = Mock()

    run = SimpleNamespace(
        id=uuid4(),
        scope_key="scope-1",
        status="running",
        mode="full",
        started_at=None,
        finished_at=None,
    )
    state = SimpleNamespace()
    client = SimpleNamespace(close=Mock())
    context = SimpleNamespace(client=client, mode=SimpleNamespace(value="full"))

    service._initialize_sync_run = Mock(return_value=(run, state))  # type: ignore[method-assign]
    service._build_context = Mock(return_value=context)  # type: ignore[method-assign]
    service._collect_sync = Mock(  # type: ignore[method-assign]
        side_effect=AttributeError("'GoogleBusinessService' object has no attribute '_serialize_establishment'")
    )
    service._send_run_failure_email = Mock(return_value={"sent": True})  # type: ignore[method-assign]

    with pytest.raises(AttributeError) as exc_info:
        service.run_sync(session)

    assert "_serialize_establishment" in str(exc_info.value)

    assert run.status == "failed"
    assert run.finished_at is not None
    service._send_run_failure_email.assert_called_once()
    client.close.assert_called_once()
