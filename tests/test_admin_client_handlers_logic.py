from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.api.routers.admin import client_handlers as handlers
from app.api.schemas import ClientCreate, ClientUpdate
from app.db import models
from app.utils.dates import utcnow


class _FakeResult:
    def __init__(self, value) -> None:
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        return self._value


def test_validate_activation_window_rejects_invalid_range():
    with pytest.raises(HTTPException) as exc:
        handlers._validate_activation_window(date(2024, 1, 2), date(2024, 1, 1))
    assert exc.value.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_normalize_name_strips_and_checks_blank():
    assert handlers._normalize_name("  Biz  ") == "Biz"
    with pytest.raises(HTTPException):
        handlers._normalize_name("   ")


def test_get_client_or_404_raises_when_absent():
    session = SimpleNamespace(execute=lambda stmt: _FakeResult(None))
    with pytest.raises(HTTPException) as exc:
        handlers._get_client_or_404(session, uuid4())
    assert exc.value.status_code == status.HTTP_404_NOT_FOUND


def test_apply_recipients_deduplicates_and_reuses_existing():
    existing = models.ClientRecipient(email="ops@example.com")
    client = SimpleNamespace(recipients=[existing])

    handlers._apply_recipients(client, ["Ops@example.com", "new@example.com"])

    assert len(client.recipients) == 2
    assert client.recipients[0] is existing
    assert client.recipients[1].email == "new@example.com"


def _make_subcategory(label: str):
    return models.NafSubCategory(category_id=uuid4(), name=label, naf_code=label)


def _mock_session_with_subcategories(subcategories):
    scalars = _FakeResult(subcategories)
    return SimpleNamespace(execute=lambda stmt: scalars)


def test_apply_subscriptions_preserves_order_and_deduplicates():
    sub_a = _make_subcategory("5610A")
    sub_b = _make_subcategory("5610B")
    session = _mock_session_with_subcategories([sub_a, sub_b])
    client = SimpleNamespace(subscriptions=[])

    handlers._apply_subscriptions(session, client, [sub_b.id, sub_a.id, sub_a.id])

    assert [subscription.subcategory_id for subscription in client.subscriptions] == [sub_b.id, sub_a.id]


def test_apply_subscriptions_raises_when_missing(monkeypatch):
    sub_a = _make_subcategory("5610A")
    session = _mock_session_with_subcategories([sub_a])
    client = SimpleNamespace(subscriptions=[])

    with pytest.raises(HTTPException) as exc:
        handlers._apply_subscriptions(session, client, [sub_a.id, uuid4()])
    assert exc.value.status_code == status.HTTP_404_NOT_FOUND


def test_create_client_action_success(monkeypatch):
    class SessionStub:
        def add(self, obj):
            obj.id = uuid4()
            obj.created_at = utcnow()
            obj.updated_at = utcnow()
            obj.emails_sent_count = 0
            obj.recipients = []
            obj.subscriptions = []
            obj.stripe_subscriptions = []

        def flush(self):
            return None

        def refresh(self, obj):
            return None

    session = SessionStub()
    recipients_called = []
    subscriptions_called = []
    monkeypatch.setattr(handlers, "_apply_recipients", lambda client, emails: recipients_called.append((client, emails)))
    monkeypatch.setattr(handlers, "_apply_subscriptions", lambda sess, client, ids: subscriptions_called.append(ids))

    payload = ClientCreate(
        name=" Test Client ",
        start_date=date(2024, 1, 1),
        listing_statuses=["recent_creation"],
        recipients=["ops@example.com"],
        subscription_ids=[],
    )

    result = handlers.create_client_action(payload, session)

    assert result.name == "Test Client"
    assert recipients_called and subscriptions_called is not None


def test_create_client_action_converts_integrity_error(monkeypatch):
    class _Session:
        def __init__(self) -> None:
            self.add_called = False
            self.rolled_back = False

        def add(self, obj):
            self.add_called = True

        def flush(self):
            raise IntegrityError("insert", {}, Exception("boom"))

        def refresh(self, obj):
            pass

        def rollback(self):
            self.rolled_back = True

    session = _Session()
    monkeypatch.setattr(handlers, "_apply_recipients", lambda client, emails: None)
    monkeypatch.setattr(handlers, "_apply_subscriptions", lambda sess, client, ids: None)

    payload = ClientCreate(
        name="Client",
        start_date=date(2024, 1, 1),
        listing_statuses=["recent_creation"],
        recipients=[],
        subscription_ids=[],
    )

    with pytest.raises(HTTPException) as exc:
        handlers.create_client_action(payload, session)
    assert exc.value.status_code == status.HTTP_409_CONFLICT
    assert session.rolled_back


def test_update_client_action_applies_optional_sections(monkeypatch):
    client = SimpleNamespace(
        id=uuid4(),
        name="Old",
        start_date=date(2023, 1, 1),
        end_date=None,
        listing_statuses=["recent_creation"],
        emails_sent_count=0,
        last_email_sent_at=None,
    created_at=utcnow(),
    updated_at=utcnow(),
        recipients=[],
        subscriptions=[],
        stripe_subscriptions=[],
    )
    session = SimpleNamespace(flush=lambda: None, refresh=lambda obj: None, rollback=lambda: None)
    monkeypatch.setattr(handlers, "_get_client_or_404", lambda sess, client_id: client)
    recipients_called = []
    subscriptions_called = []
    monkeypatch.setattr(handlers, "_apply_recipients", lambda client_obj, emails: recipients_called.append(emails))
    monkeypatch.setattr(handlers, "_apply_subscriptions", lambda sess, client_obj, ids: subscriptions_called.append(ids))

    payload = ClientUpdate(
        name=" Updated ",
        recipients=["ops@example.com"],
        subscription_ids=[uuid4()],
        listing_statuses=["recent_creation_missing_contact"],
    )

    updated = handlers.update_client_action(client.id, payload, session)

    assert updated.name == "Updated"
    assert recipients_called and subscriptions_called