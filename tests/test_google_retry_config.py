from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.db import models
from app.services.google import google_retry_config as grc


def _make_session(record: models.GoogleRetryConfig | None):
    scalar_result = SimpleNamespace(
        scalar_one_or_none=lambda: record,
        scalars=lambda: SimpleNamespace(all=lambda: [record] if record else []),
    )
    session = SimpleNamespace(
        execute=lambda stmt: scalar_result,
        add=lambda obj: None,
        flush=lambda: None,
    )
    return session


def test_load_runtime_config_inserts_defaults_when_missing():
    session = _make_session(None)

    runtime = grc.load_runtime_google_retry_config(session)

    assert runtime.retry_weekdays == {0}
    assert all(rule.frequency_days > 0 for rule in runtime.default_rules)
    assert all(rule.frequency_days > 0 for rule in runtime.micro_rules)
    assert runtime.retry_missing_contact_enabled is True
    assert runtime.retry_missing_contact_frequency_days == 14


def test_update_runtime_config_sanitizes_weekdays(monkeypatch):
    record = models.GoogleRetryConfig(
        retry_weekdays=[0],
        default_rules=[{"max_age_days": 10, "frequency_days": 5}],
        micro_rules=[{"max_age_days": None, "frequency_days": 30}],
        retry_missing_contact_enabled=False,
        retry_missing_contact_frequency_days=7,
    )
    session = _make_session(record)

    updated = grc.update_google_retry_config(
        session,
        retry_weekdays=[-1, 2, 2, 99],
        default_rules=[{"max_age_days": "15", "frequency_days": "7"}],
        micro_rules=[{"max_age_days": 0, "frequency_days": 21}],
        retry_missing_contact_enabled=True,
        retry_missing_contact_frequency_days=14,
    )

    assert updated.retry_weekdays == [2]
    assert updated.default_rules[0]["frequency_days"] == 7
    assert updated.micro_rules[0]["max_age_days"] == 0
    assert updated.retry_missing_contact_enabled is True
    assert updated.retry_missing_contact_frequency_days == 14


def test_normalize_rules_falls_back_on_invalid_entries():
    fallback = [{"max_age_days": 10, "frequency_days": 5}]
    normalized = grc._normalize_rules(
        [
            {"max_age_days": "bad", "frequency_days": 0},
            {"max_age_days": 5, "frequency_days": "3"},
        ],
        fallback,
    )

    assert len(normalized) == 1
    assert normalized[0].max_age_days == 5
    assert normalized[0].frequency_days == 3


def test_serialize_google_retry_config_returns_defaults_when_empty():
    record = models.GoogleRetryConfig(
        retry_weekdays=[],
        default_rules=[],
        micro_rules=[],
        retry_missing_contact_enabled=None,
        retry_missing_contact_frequency_days=0,
    )
    serialized = grc.serialize_google_retry_config(record)
    assert serialized["retry_weekdays"]
    assert serialized["default_rules"]
    assert serialized["micro_rules"]
    assert serialized["retry_missing_contact_enabled"] is True
    assert serialized["retry_missing_contact_frequency_days"] == 14


def test_serialize_rules_for_storage_falls_back_to_defaults():
    serialized = grc._serialize_rules_for_storage([], grc._DEFAULT_DEFAULT_RULES)

    assert serialized == grc._DEFAULT_DEFAULT_RULES


def test_load_runtime_config_sanitizes_invalid_weekdays():
    record = models.GoogleRetryConfig(
        retry_weekdays=[-1, 9],
        default_rules=[{"max_age_days": 10, "frequency_days": 5}],
        micro_rules=[{"max_age_days": 20, "frequency_days": 10}],
        retry_missing_contact_enabled=None,
        retry_missing_contact_frequency_days=-5,
    )
    session = _make_session(record)

    runtime = grc.load_runtime_google_retry_config(session)

    assert runtime.retry_weekdays == {0}
    assert runtime.retry_missing_contact_enabled is True
    assert runtime.retry_missing_contact_frequency_days == 14
