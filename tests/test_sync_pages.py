from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

import app.services.sync.pages as pages_module
from app.services.sync.pages import collect_pages


class _DummyCollector:
    def __init__(self) -> None:
        self._settings = SimpleNamespace(sirene=SimpleNamespace(page_size=1000, current_period_date=None))
        self._logger = logging.getLogger("tests.sync.pages")
        self.last_upsert_payload: list[dict[str, object]] | None = None

    def _upsert_establishments(self, _session, etablissements, *_args):
        self.last_upsert_payload = list(etablissements)
        return [], [], []


def _build_context(payload: object) -> SimpleNamespace:
    run = SimpleNamespace(
        id=uuid4(),
        scope_key="default",
        api_call_count=0,
        fetched_records=0,
        created_records=0,
        updated_records=0,
        last_cursor=None,
    )
    state = SimpleNamespace(last_creation_date=None, last_cursor=None, last_total=None, last_synced_at=None, cursor_completed=False)
    session = SimpleNamespace(flush=lambda: None, commit=lambda: None)
    client = SimpleNamespace(search_establishments=lambda **_kwargs: payload)
    return SimpleNamespace(state=state, run=run, session=session, client=client)


def _stub_email(monkeypatch: pytest.MonkeyPatch) -> Mock:
    send_mock = Mock()

    class _FakeEmailService:
        def is_enabled(self) -> bool:
            return True

        def is_configured(self) -> bool:
            return True

        def send(self, subject: str, body: str, recipients: list[str]) -> None:
            send_mock(subject, body, recipients)

    monkeypatch.setattr(pages_module, "EmailService", _FakeEmailService)
    monkeypatch.setattr(pages_module, "get_admin_emails", lambda _session: ["admin@example.com"])
    return send_mock


def test_collect_pages_raises_explicit_error_when_payload_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    collector = _DummyCollector()
    context = _build_context(None)
    send_mock = _stub_email(monkeypatch)

    with pytest.raises(RuntimeError, match="Réponse Sirene invalide") as exc_info:
        collect_pages(
            collector=collector,
            context=context,
            query="etatAdministratifEtablissement:A",
            champs="siret",
            cursor_value="*",
            tri="dateCreationEtablissement",
            months_back=1,
            since_creation=None,
            creation_range=None,
            persist_state=False,
        )

    assert "type=NoneType" in str(exc_info.value)
    send_mock.assert_called_once()
    args = send_mock.call_args.args
    assert "Alerte payload Sirene invalide" in args[0]
    assert "invalid_payload" in args[1]
    assert args[2] == ["admin@example.com"]


def test_collect_pages_ignores_non_mapping_establishments_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    collector = _DummyCollector()
    send_mock = _stub_email(monkeypatch)
    payload = {
        "header": {"curseur": "*", "curseurSuivant": None, "total": 3},
        "etablissements": [
            {"siret": "11111111111111", "dateDernierTraitementEtablissement": "2026-02-23T00:00:00"},
            None,
            "not-a-dict",
            {"siret": "22222222222222"},
        ],
    }
    context = _build_context(payload)

    result = collect_pages(
        collector=collector,
        context=context,
        query="etatAdministratifEtablissement:A",
        champs="siret",
        cursor_value="*",
        tri="dateCreationEtablissement",
        months_back=1,
        since_creation=None,
        creation_range=None,
        persist_state=False,
    )

    assert result.page_count == 1
    assert context.run.fetched_records == 2
    assert collector.last_upsert_payload is not None
    assert len(collector.last_upsert_payload) == 2
    assert [item.get("siret") for item in collector.last_upsert_payload] == ["11111111111111", "22222222222222"]
    send_mock.assert_called_once()
    args = send_mock.call_args.args
    assert "invalid_payload_items" in args[1]
