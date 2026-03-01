"""Utilities to load and persist Google retry configuration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models

_DEFAULT_RETRY_WEEKDAYS = [0]  # Monday
_DEFAULT_RETRY_MISSING_CONTACT_ENABLED = True
_DEFAULT_RETRY_MISSING_CONTACT_FREQUENCY_DAYS = 14
_DEFAULT_RETRY_NO_WEBSITE_FREQUENCY_DAYS = 14
_DEFAULT_DEFAULT_RULES = [
    {"max_age_days": 60, "frequency_days": 7},
    {"max_age_days": 120, "frequency_days": 14},
    {"max_age_days": None, "frequency_days": 30},
]
_DEFAULT_MICRO_RULES = [
    {"max_age_days": 120, "frequency_days": 21},
    {"max_age_days": None, "frequency_days": 60},
]


@dataclass(frozen=True)
class RetryRule:
    max_age_days: int | None
    frequency_days: int


@dataclass(frozen=True)
class GoogleRetryRuntimeConfig:
    retry_weekdays: set[int]
    default_rules: tuple[RetryRule, ...]
    micro_rules: tuple[RetryRule, ...]
    retry_missing_contact_enabled: bool
    retry_missing_contact_frequency_days: int
    retry_no_website_frequency_days: int


def ensure_google_retry_config(session: Session) -> models.GoogleRetryConfig:
    config = session.execute(
        select(models.GoogleRetryConfig).order_by(models.GoogleRetryConfig.id.asc()).limit(1)
    ).scalar_one_or_none()
    if config is None:
        config = models.GoogleRetryConfig(
            retry_weekdays=list(_DEFAULT_RETRY_WEEKDAYS),
            default_rules=list(_DEFAULT_DEFAULT_RULES),
            micro_rules=list(_DEFAULT_MICRO_RULES),
            retry_missing_contact_enabled=_DEFAULT_RETRY_MISSING_CONTACT_ENABLED,
            retry_missing_contact_frequency_days=_DEFAULT_RETRY_MISSING_CONTACT_FREQUENCY_DAYS,
            retry_no_website_frequency_days=_DEFAULT_RETRY_NO_WEBSITE_FREQUENCY_DAYS,
        )
        session.add(config)
        session.flush()
    return config


def _normalize_rules(rules: Iterable[dict[str, object]] | None, fallback: list[dict[str, object]]) -> list[RetryRule]:
    normalized: list[RetryRule] = []
    rule_dicts = list(rules or []) or fallback
    for item in rule_dicts:
        max_age = item.get("max_age_days") if isinstance(item, dict) else None
        frequency = item.get("frequency_days") if isinstance(item, dict) else None
        if frequency is None:
            continue
        try:
            freq_value = int(frequency)
        except (TypeError, ValueError):
            continue
        if freq_value <= 0:
            continue
        if max_age is None:
            normalized.append(RetryRule(max_age_days=None, frequency_days=freq_value))
            continue
        try:
            age_value = int(max_age)
        except (TypeError, ValueError):
            continue
        if age_value < 0:
            continue
        normalized.append(RetryRule(max_age_days=age_value, frequency_days=freq_value))
    if not normalized:
        return [RetryRule(max_age_days=rule["max_age_days"], frequency_days=rule["frequency_days"]) for rule in fallback]
    normalized.sort(key=lambda rule: (rule.max_age_days is None, rule.max_age_days or 0))
    return normalized


def load_runtime_google_retry_config(session: Session) -> GoogleRetryRuntimeConfig:
    record = ensure_google_retry_config(session)
    weekdays = record.retry_weekdays or []
    weekday_set = {int(day) for day in weekdays if isinstance(day, int)}
    weekday_set = {day for day in weekday_set if 0 <= day <= 6}
    if not weekday_set:
        weekday_set = set(_DEFAULT_RETRY_WEEKDAYS)
    missing_contact_enabled = record.retry_missing_contact_enabled
    if missing_contact_enabled is None:
        missing_contact_enabled = _DEFAULT_RETRY_MISSING_CONTACT_ENABLED
    missing_contact_frequency = record.retry_missing_contact_frequency_days
    if not isinstance(missing_contact_frequency, int) or missing_contact_frequency <= 0:
        missing_contact_frequency = _DEFAULT_RETRY_MISSING_CONTACT_FREQUENCY_DAYS
    no_website_frequency = record.retry_no_website_frequency_days
    if not isinstance(no_website_frequency, int) or no_website_frequency <= 0:
        no_website_frequency = _DEFAULT_RETRY_NO_WEBSITE_FREQUENCY_DAYS
    default_rules = tuple(_normalize_rules(record.default_rules, _DEFAULT_DEFAULT_RULES))
    micro_rules = tuple(_normalize_rules(record.micro_rules, _DEFAULT_MICRO_RULES))
    return GoogleRetryRuntimeConfig(
        retry_weekdays=weekday_set,
        default_rules=default_rules,
        micro_rules=micro_rules,
        retry_missing_contact_enabled=bool(missing_contact_enabled),
        retry_missing_contact_frequency_days=missing_contact_frequency,
        retry_no_website_frequency_days=no_website_frequency,
    )


def serialize_google_retry_config(record: models.GoogleRetryConfig) -> dict[str, object]:
    return {
        "retry_weekdays": record.retry_weekdays or list(_DEFAULT_RETRY_WEEKDAYS),
        "default_rules": record.default_rules or list(_DEFAULT_DEFAULT_RULES),
        "micro_rules": record.micro_rules or list(_DEFAULT_MICRO_RULES),
        "retry_missing_contact_enabled": (
            record.retry_missing_contact_enabled
            if record.retry_missing_contact_enabled is not None
            else _DEFAULT_RETRY_MISSING_CONTACT_ENABLED
        ),
        "retry_missing_contact_frequency_days": (
            record.retry_missing_contact_frequency_days
            if isinstance(record.retry_missing_contact_frequency_days, int)
            and record.retry_missing_contact_frequency_days > 0
            else _DEFAULT_RETRY_MISSING_CONTACT_FREQUENCY_DAYS
        ),
        "retry_no_website_frequency_days": (
            record.retry_no_website_frequency_days
            if isinstance(record.retry_no_website_frequency_days, int)
            and record.retry_no_website_frequency_days > 0
            else _DEFAULT_RETRY_NO_WEBSITE_FREQUENCY_DAYS
        ),
    }


def update_google_retry_config(
    session: Session,
    *,
    retry_weekdays: list[int],
    default_rules: list[dict[str, object]],
    micro_rules: list[dict[str, object]],
    retry_missing_contact_enabled: bool,
    retry_missing_contact_frequency_days: int,
    retry_no_website_frequency_days: int | None = None,
) -> models.GoogleRetryConfig:
    record = ensure_google_retry_config(session)
    sanitized_weekdays = (
        sorted({day for day in retry_weekdays if isinstance(day, int) and 0 <= day <= 6})
        or list(_DEFAULT_RETRY_WEEKDAYS)
    )
    record.retry_weekdays = sanitized_weekdays
    record.default_rules = _serialize_rules_for_storage(default_rules, _DEFAULT_DEFAULT_RULES)
    record.micro_rules = _serialize_rules_for_storage(micro_rules, _DEFAULT_MICRO_RULES)
    record.retry_missing_contact_enabled = bool(retry_missing_contact_enabled)
    frequency_days = retry_missing_contact_frequency_days
    if not isinstance(frequency_days, int) or frequency_days <= 0:
        frequency_days = _DEFAULT_RETRY_MISSING_CONTACT_FREQUENCY_DAYS
    record.retry_missing_contact_frequency_days = frequency_days
    no_website_freq = retry_no_website_frequency_days
    if not isinstance(no_website_freq, int) or no_website_freq is None or no_website_freq <= 0:
        no_website_freq = _DEFAULT_RETRY_NO_WEBSITE_FREQUENCY_DAYS
    record.retry_no_website_frequency_days = no_website_freq
    session.flush()
    return record


def _serialize_rules_for_storage(
    rules: Iterable[dict[str, object]] | None,
    fallback: list[dict[str, object]],
) -> list[dict[str, object]]:
    normalized = _normalize_rules(rules, fallback)
    return [
        {
            "max_age_days": rule.max_age_days,
            "frequency_days": rule.frequency_days,
        }
        for rule in normalized
    ]
