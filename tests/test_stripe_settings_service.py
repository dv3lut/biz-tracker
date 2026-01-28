from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

from app.db import models
from app.services.stripe import stripe_settings_service


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        return self._value


def test_get_billing_settings_creates_default():
    added = []

    session = SimpleNamespace(
        execute=lambda stmt: _FakeResult(None),
        add=lambda obj: added.append(obj),
        flush=lambda: None,
    )

    settings = stripe_settings_service.get_billing_settings(session)

    assert settings.trial_period_days == stripe_settings_service.DEFAULT_TRIAL_PERIOD_DAYS
    assert added


def test_update_trial_period_days_updates_value():
    existing = models.StripeBillingSettings(trial_period_days=10)
    session = SimpleNamespace(
        execute=lambda stmt: _FakeResult(existing),
        add=lambda obj: None,
        flush=lambda: None,
    )

    updated = stripe_settings_service.update_trial_period_days(session, 21)

    assert updated.trial_period_days == 21


def test_get_trial_period_days_reads_setting():
    existing = models.StripeBillingSettings(trial_period_days=30)
    session = SimpleNamespace(
        execute=lambda stmt: _FakeResult(existing),
        add=lambda obj: None,
        flush=lambda: None,
    )

    assert stripe_settings_service.get_trial_period_days(session) == 30


def test_apply_trial_subscription_update_sets_plan_key():
    client = SimpleNamespace(
        stripe_subscription_status=None,
        stripe_current_period_end=None,
        stripe_cancel_at=None,
        stripe_price_id=None,
        stripe_plan_key=None,
    )
    app_settings = SimpleNamespace(stripe=SimpleNamespace(price_ids={"starter": "price_starter"}))
    subscription = {
        "status": "trialing",
        "current_period_end": 1700000000,
        "items": {"data": [{"price": {"id": "price_starter"}}]},
    }

    stripe_settings_service._apply_trial_subscription_update(client, subscription, app_settings)

    assert client.stripe_plan_key == "starter"


def test_resolve_price_id_returns_none_when_missing():
    assert stripe_settings_service._resolve_price_id({"items": {"data": []}}) is None


def test_resolve_plan_key_returns_none_when_unknown():
    app_settings = SimpleNamespace(stripe=SimpleNamespace(price_ids={"starter": "price_starter"}))
    assert stripe_settings_service._resolve_plan_key(app_settings, "price_other") is None


def test_to_datetime_returns_none_when_missing():
    assert stripe_settings_service._to_datetime(None) is None


def test_resolve_price_id_returns_none_when_non_dict():
    assert stripe_settings_service._resolve_price_id({"items": {"data": [{"price": "price_123"}]}}) is None


def test_apply_trial_period_to_existing_trials_updates_clients(monkeypatch):
    client_ok = SimpleNamespace(
        stripe_subscription_status="trialing",
        stripe_subscription_id="sub_ok",
        stripe_price_id=None,
        stripe_plan_key=None,
        stripe_current_period_end=None,
        stripe_cancel_at=None,
    )
    client_fail = SimpleNamespace(
        stripe_subscription_status="trialing",
        stripe_subscription_id="sub_fail",
        stripe_price_id=None,
        stripe_plan_key=None,
        stripe_current_period_end=None,
        stripe_cancel_at=None,
    )

    session = SimpleNamespace(
        execute=lambda stmt: _FakeResult([client_ok, client_fail]),
        flush=lambda: None,
    )

    def modify(subscription_id, **_kwargs):
        if subscription_id == "sub_fail":
            raise stripe_settings_service.stripe.error.StripeError("boom")
        return {
            "status": "trialing",
            "current_period_end": 1700000000,
            "items": {"data": [{"price": {"id": "price_starter"}}]},
        }

    monkeypatch.setattr(stripe_settings_service.stripe, "Subscription", SimpleNamespace(modify=modify))
    monkeypatch.setattr(stripe_settings_service, "upsert_subscription_history", lambda *args, **kwargs: None)

    app_settings = SimpleNamespace(stripe=SimpleNamespace(secret_key="sk_test", price_ids={"starter": "price_starter"}))

    updated, failed = stripe_settings_service.apply_trial_period_to_existing_trials(
        session,
        app_settings,
        7,
    )

    assert updated == 1
    assert failed == 1
    assert isinstance(client_ok.stripe_current_period_end, datetime)
