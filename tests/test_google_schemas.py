from __future__ import annotations

import pytest

from app.api.schemas.google import GoogleRetryConfigOut, GoogleRetryConfigUpdate, GoogleRetryRule


def _rule(**kwargs) -> GoogleRetryRule:
    payload = {"max_age_days": 90, "frequency_days": 7}
    payload.update(kwargs)
    return GoogleRetryRule(**payload)


def test_retry_weekdays_are_validated_and_deduplicated():
    payload = {
        "retry_weekdays": [0, 2, 8, 2, -1, 6],
        "default_rules": [_rule()],
        "micro_rules": [_rule(max_age_days=None)],
    }

    config = GoogleRetryConfigOut(**payload)

    assert config.retry_weekdays == [0, 2, 6]


def test_retry_weekdays_fallback_to_monday_when_empty():
    config = GoogleRetryConfigOut(
        retry_weekdays=[],
        default_rules=[_rule()],
        micro_rules=[_rule()],
    )

    assert config.retry_weekdays == [0]


def test_missing_rules_raise_validation_error():
    with pytest.raises(ValueError):
        GoogleRetryConfigOut(retry_weekdays=[0], default_rules=[], micro_rules=[_rule()])
    with pytest.raises(ValueError):
        GoogleRetryConfigOut(retry_weekdays=[0], default_rules=[_rule()], micro_rules=[])


def test_update_schema_inherits_validations():
    payload = GoogleRetryConfigUpdate(
        retry_weekdays=[1, 1],
        default_rules=[_rule(max_age_days=60)],
        micro_rules=[_rule(max_age_days=15, frequency_days=3)],
    )

    assert payload.retry_weekdays == [1]
    assert payload.micro_rules[0].frequency_days == 3
