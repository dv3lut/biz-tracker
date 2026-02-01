from __future__ import annotations

from types import SimpleNamespace

from app.api.routers.admin import stripe_router as stripe
from app.api.schemas import AdminStripeSettingsUpdate


def test_get_stripe_settings_returns_settings(monkeypatch):
    session = SimpleNamespace()
    monkeypatch.setattr(stripe, "get_billing_settings", lambda sess: SimpleNamespace(trial_period_days=21))

    result = stripe.get_stripe_settings(session=session)

    assert result.trial_period_days == 21


def test_update_stripe_settings_applies_trials(monkeypatch):
    session = SimpleNamespace()
    called = {}

    monkeypatch.setattr(
        stripe,
        "update_trial_period_days",
        lambda sess, days: SimpleNamespace(trial_period_days=days),
    )
    monkeypatch.setattr(
        stripe,
        "apply_trial_period_to_existing_trials",
        lambda sess, settings, days: (2, 1),
    )
    monkeypatch.setattr(stripe, "get_settings", lambda: SimpleNamespace())

    payload = AdminStripeSettingsUpdate(trial_period_days=10, apply_to_existing_trials=True)

    result = stripe.update_stripe_settings(payload=payload, session=session)

    assert result.trial_period_days == 10
    assert result.updated_trials == 2
    assert result.failed_trials == 1


def test_update_stripe_settings_skips_trials_when_disabled(monkeypatch):
    session = SimpleNamespace()

    monkeypatch.setattr(
        stripe,
        "update_trial_period_days",
        lambda sess, days: SimpleNamespace(trial_period_days=days),
    )
    monkeypatch.setattr(stripe, "apply_trial_period_to_existing_trials", lambda *args, **kwargs: (99, 99))

    payload = AdminStripeSettingsUpdate(trial_period_days=5, apply_to_existing_trials=False)

    result = stripe.update_stripe_settings(payload=payload, session=session)

    assert result.updated_trials == 0
    assert result.failed_trials == 0
