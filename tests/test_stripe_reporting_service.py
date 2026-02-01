from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from app.services.stripe import stripe_reporting_service


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        return self._value


def test_is_weekly_summary_due_when_never_sent(monkeypatch):
    monday = datetime(2026, 1, 26, 9, 0, 0)
    monkeypatch.setattr(stripe_reporting_service, "utcnow", lambda: monday)
    monkeypatch.setattr(
        stripe_reporting_service,
        "_get_billing_settings",
        lambda session: SimpleNamespace(last_weekly_summary_at=None),
    )

    assert stripe_reporting_service._is_weekly_summary_due(SimpleNamespace()) is True


def test_is_weekly_summary_due_false_same_day(monkeypatch):
    monday = datetime(2026, 1, 26, 9, 0, 0)
    monkeypatch.setattr(stripe_reporting_service, "utcnow", lambda: monday)
    monkeypatch.setattr(
        stripe_reporting_service,
        "_get_billing_settings",
        lambda session: SimpleNamespace(last_weekly_summary_at=monday),
    )

    assert stripe_reporting_service._is_weekly_summary_due(SimpleNamespace()) is False


def test_build_weekly_summary_includes_upcoming(monkeypatch):
    now = datetime(2026, 1, 26, 9, 0, 0)
    monkeypatch.setattr(stripe_reporting_service, "utcnow", lambda: now)

    subscription = SimpleNamespace(
        client_id="client-1",
        status="active",
        plan_key="starter",
        current_period_end=now,
        trial_end_at=None,
    )

    session = SimpleNamespace(
        execute=lambda stmt: _FakeResult([subscription]),
        get=lambda model, client_id: SimpleNamespace(name="ACME"),
    )

    summary = stripe_reporting_service._build_weekly_summary(session)

    assert "Abonnements suivis: 1" in summary
    assert "Paiements à venir" in summary
    assert "ACME" in summary


def test_send_weekly_stripe_summary_if_due_sends(monkeypatch):
    sent = {}

    class DummyEmail:
        def is_enabled(self):
            return True

        def is_configured(self):
            return True

        def send(self, subject, body, recipients, **_kwargs):
            sent["subject"] = subject
            sent["body"] = body
            sent["recipients"] = recipients

    settings_row = SimpleNamespace(last_weekly_summary_at=None)

    monkeypatch.setattr(stripe_reporting_service, "EmailService", lambda: DummyEmail())
    monkeypatch.setattr(stripe_reporting_service, "get_admin_emails", lambda session: ["ops@example.com"])
    monkeypatch.setattr(stripe_reporting_service, "_build_weekly_summary", lambda session: "summary")
    monkeypatch.setattr(stripe_reporting_service, "_get_billing_settings", lambda session: settings_row)
    monkeypatch.setattr(stripe_reporting_service, "_is_weekly_summary_due", lambda session: True)

    session = SimpleNamespace(flush=lambda: None)

    result = stripe_reporting_service.send_weekly_stripe_summary_if_due(session, SimpleNamespace())

    assert result is True
    assert sent.get("recipients") == ["ops@example.com"]
    assert "Récap" in sent.get("subject", "")
    assert settings_row.last_weekly_summary_at is not None


def test_send_weekly_stripe_summary_if_due_skips_when_not_due(monkeypatch):
    monkeypatch.setattr(stripe_reporting_service, "_is_weekly_summary_due", lambda session: False)
    assert stripe_reporting_service.send_weekly_stripe_summary_if_due(SimpleNamespace(), SimpleNamespace()) is False


def test_send_weekly_stripe_summary_if_due_skips_when_email_disabled(monkeypatch):
    class DummyEmail:
        def is_enabled(self):
            return False

        def is_configured(self):
            return True

    monkeypatch.setattr(stripe_reporting_service, "EmailService", lambda: DummyEmail())
    monkeypatch.setattr(stripe_reporting_service, "_is_weekly_summary_due", lambda session: True)

    assert stripe_reporting_service.send_weekly_stripe_summary_if_due(SimpleNamespace(), SimpleNamespace()) is False


def test_send_weekly_stripe_summary_if_due_skips_when_no_recipients(monkeypatch):
    class DummyEmail:
        def is_enabled(self):
            return True

        def is_configured(self):
            return True

    monkeypatch.setattr(stripe_reporting_service, "EmailService", lambda: DummyEmail())
    monkeypatch.setattr(stripe_reporting_service, "_is_weekly_summary_due", lambda session: True)
    monkeypatch.setattr(stripe_reporting_service, "get_admin_emails", lambda session: [])

    assert stripe_reporting_service.send_weekly_stripe_summary_if_due(SimpleNamespace(), SimpleNamespace()) is False


def test_is_weekly_summary_due_false_when_wrong_day(monkeypatch):
    sunday = datetime(2026, 1, 25, 9, 0, 0)
    monkeypatch.setattr(stripe_reporting_service, "utcnow", lambda: sunday)
    monkeypatch.setattr(
        stripe_reporting_service,
        "_get_billing_settings",
        lambda session: SimpleNamespace(last_weekly_summary_at=None),
    )

    assert stripe_reporting_service._is_weekly_summary_due(SimpleNamespace()) is False


def test_is_weekly_summary_due_true_when_last_sent_old(monkeypatch):
    monday = datetime(2026, 1, 26, 9, 0, 0)
    last_sent = datetime(2026, 1, 19, 9, 0, 0)
    monkeypatch.setattr(stripe_reporting_service, "utcnow", lambda: monday)
    monkeypatch.setattr(
        stripe_reporting_service,
        "_get_billing_settings",
        lambda session: SimpleNamespace(last_weekly_summary_at=last_sent),
    )

    assert stripe_reporting_service._is_weekly_summary_due(SimpleNamespace()) is True


def test_client_label_returns_placeholder_when_missing():
    session = SimpleNamespace(get=lambda model, client_id: None)
    assert stripe_reporting_service._client_label(session, "missing") == "Client inconnu"


def test_client_label_returns_name_when_found():
    session = SimpleNamespace(get=lambda model, client_id: SimpleNamespace(name="ACME"))
    assert stripe_reporting_service._client_label(session, "client-1") == "ACME"


def test_get_billing_settings_returns_existing():
    existing = SimpleNamespace(trial_period_days=7, last_weekly_summary_at=None)
    session = SimpleNamespace(execute=lambda stmt: _FakeResult(existing))
    assert stripe_reporting_service._get_billing_settings(session) is existing


def test_get_billing_settings_creates_when_missing():
    created = []

    session = SimpleNamespace(
        execute=lambda stmt: _FakeResult(None),
        add=lambda obj: created.append(obj),
        flush=lambda: None,
    )

    settings = stripe_reporting_service._get_billing_settings(session)

    assert settings.trial_period_days == 14
    assert created


def test_build_weekly_summary_includes_trials(monkeypatch):
    now = datetime(2026, 1, 26, 9, 0, 0)
    monkeypatch.setattr(stripe_reporting_service, "utcnow", lambda: now)

    subscription = SimpleNamespace(
        client_id="client-2",
        status="trialing",
        plan_key="starter",
        current_period_end=None,
        trial_end_at=now,
    )

    session = SimpleNamespace(
        execute=lambda stmt: _FakeResult([subscription]),
        get=lambda model, client_id: SimpleNamespace(name="BETA"),
    )

    summary = stripe_reporting_service._build_weekly_summary(session)

    assert "Fins d'essai" in summary
    assert "BETA" in summary
