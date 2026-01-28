from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.db import models
from app.services.stripe.stripe_subscription_history import upsert_subscription_history


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


def _settings():
    return SimpleNamespace(stripe=SimpleNamespace(price_ids={"starter": "price_123"}))


def test_upsert_subscription_history_creates_record():
    client = SimpleNamespace(id=uuid4())
    subscription = {
        "id": "sub_123",
        "customer": "cus_123",
        "status": "trialing",
        "metadata": {"plan_key": "starter"},
        "created": 1700000000,
        "trial_end": 1700600000,
        "current_period_start": 1700000000,
        "current_period_end": 1702600000,
        "items": {"data": [{"price": {"id": "price_123"}}]},
    }

    session = SimpleNamespace(
        execute=lambda stmt: _FakeResult(None),
        add=lambda record: None,
        flush=lambda: None,
    )

    record = upsert_subscription_history(
        session,
        client=client,
        subscription=subscription,
        settings=_settings(),
    )

    assert record is not None
    assert record.stripe_subscription_id == "sub_123"
    assert record.plan_key == "starter"
    assert record.price_id == "price_123"
    assert record.purchased_at == datetime.fromtimestamp(1700000000, tz=timezone.utc).replace(tzinfo=None)
    assert record.paid_start_at == datetime.fromtimestamp(1700600000, tz=timezone.utc).replace(tzinfo=None)


def test_upsert_subscription_history_keeps_earliest_purchase_date():
    existing = models.ClientStripeSubscription(
        client_id=uuid4(),
        stripe_subscription_id="sub_456",
        purchased_at=datetime(2023, 1, 1),
    )
    subscription = {
        "id": "sub_456",
        "created": 1700000000,
        "items": {"data": [{"price": {"id": "price_123"}}]},
    }

    session = SimpleNamespace(
        execute=lambda stmt: _FakeResult(existing),
        add=lambda record: None,
        flush=lambda: None,
    )

    record = upsert_subscription_history(
        session,
        client=SimpleNamespace(id=uuid4()),
        subscription=subscription,
        settings=_settings(),
    )

    assert record.purchased_at == datetime(2023, 1, 1)


def test_upsert_subscription_history_resolves_plan_from_price():
    client = SimpleNamespace(id=uuid4())
    subscription = {
        "id": "sub_789",
        "current_period_start": 1700000000,
        "items": {"data": [{"price": {"id": "price_123"}}]},
    }

    session = SimpleNamespace(
        execute=lambda stmt: _FakeResult(None),
        add=lambda record: None,
        flush=lambda: None,
    )

    record = upsert_subscription_history(
        session,
        client=client,
        subscription=subscription,
        settings=_settings(),
    )

    assert record.plan_key == "starter"
    assert record.paid_start_at == datetime.fromtimestamp(1700000000, tz=timezone.utc).replace(tzinfo=None)


def test_upsert_subscription_history_returns_none_when_missing_subscription():
    session = SimpleNamespace(execute=lambda stmt: _FakeResult(None), add=lambda record: None, flush=lambda: None)
    assert (
        upsert_subscription_history(
            session,
            client=SimpleNamespace(id=uuid4()),
            subscription=None,
            settings=_settings(),
        )
        is None
    )


def test_upsert_subscription_history_returns_none_when_missing_id():
    session = SimpleNamespace(execute=lambda stmt: _FakeResult(None), add=lambda record: None, flush=lambda: None)
    assert (
        upsert_subscription_history(
            session,
            client=SimpleNamespace(id=uuid4()),
            subscription={"status": "active"},
            settings=_settings(),
        )
        is None
    )


def test_upsert_subscription_history_handles_missing_price_items():
    client = SimpleNamespace(id=uuid4())
    subscription = {
        "id": "sub_empty",
        "items": {"data": []},
    }

    session = SimpleNamespace(
        execute=lambda stmt: _FakeResult(None),
        add=lambda record: None,
        flush=lambda: None,
    )

    record = upsert_subscription_history(
        session,
        client=client,
        subscription=subscription,
        settings=_settings(),
    )

    assert record.price_id is None


def test_upsert_subscription_history_handles_non_dict_price():
    client = SimpleNamespace(id=uuid4())
    subscription = {
        "id": "sub_price_str",
        "items": {"data": [{"price": "price_123"}]},
    }

    session = SimpleNamespace(
        execute=lambda stmt: _FakeResult(None),
        add=lambda record: None,
        flush=lambda: None,
    )

    record = upsert_subscription_history(
        session,
        client=client,
        subscription=subscription,
        settings=_settings(),
    )

    assert record.price_id is None


def test_upsert_subscription_history_leaves_plan_key_none_when_unknown():
    client = SimpleNamespace(id=uuid4())
    subscription = {
        "id": "sub_unknown",
        "items": {"data": [{"price": {"id": "price_other"}}]},
    }

    session = SimpleNamespace(
        execute=lambda stmt: _FakeResult(None),
        add=lambda record: None,
        flush=lambda: None,
    )

    record = upsert_subscription_history(
        session,
        client=client,
        subscription=subscription,
        settings=_settings(),
    )

    assert record.plan_key is None
