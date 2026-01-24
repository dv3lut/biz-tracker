from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.services import client_service
from app.services.client_service import ClientEmailPayload


def _client(
    *,
    start: date = date(2024, 1, 1),
    end: date | None = None,
    listing_statuses: list[str] | None = None,
    recipients: list[SimpleNamespace] | None = None,
    subscriptions: list[SimpleNamespace] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        name="Client",
        start_date=start,
        end_date=end,
        listing_statuses=listing_statuses or ["recent_creation", "not_recent_creation"],
        recipients=recipients or [],
        subscriptions=subscriptions or [],
        emails_sent_count=0,
        last_email_sent_at=None,
        categorie_juridique="5498",
        categorie_entreprise="PME",
    )


def _subscription(naf_code: str, *, active: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        subcategory=SimpleNamespace(id=uuid4(), naf_code=naf_code, is_active=active),
        subcategory_id=uuid4(),
    )


def _establishment(naf_code: str, *, status: str = "recent_creation", **kwargs) -> SimpleNamespace:
    defaults = {
        "siret": str(uuid4().int)[:14],
        "naf_code": naf_code,
        "google_listing_age_status": status,
        "google_contact_phone": None,
        "google_contact_email": None,
        "google_contact_website": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_is_client_active_checks_window(monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return date(2024, 1, 10)

    monkeypatch.setattr(client_service, "date", FixedDate)

    active = _client(start=date(2024, 1, 1), end=date(2024, 1, 20))
    not_started = _client(start=date(2024, 1, 20))
    expired = _client(start=date(2023, 1, 1), end=date(2023, 12, 31))

    assert client_service.is_client_active(active)
    assert not client_service.is_client_active(not_started)
    assert not client_service.is_client_active(expired)


def test_collect_and_filter_client_emails():
    clients = [
        _client(recipients=[SimpleNamespace(email="ops@example.com"), SimpleNamespace(email=None)]),
        _client(recipients=[SimpleNamespace(email="ops@example.com"), SimpleNamespace(email="alerts@example.com")]),
    ]
    emails = client_service.collect_client_emails(clients)
    assert emails == ["alerts@example.com", "ops@example.com"]


def test_summarize_client_filters_ignores_inactive_subscriptions():
    client = _client(
        listing_statuses=["recent_creation"],
        subscriptions=[
            _subscription("5610A"),
            _subscription("5610A", active=False),
            _subscription("5610B"),
        ],
    )
    summary = client_service.summarize_client_filters(client)
    assert summary.listing_statuses == ["recent_creation"]
    assert "56.10A" in summary.naf_codes and "56.10B" in summary.naf_codes


def test_summarize_client_filters_deduplicates_codes():
    client = _client(
        subscriptions=[
            _subscription("5610A"),
            _subscription("5610A"),
        ]
    )

    summary = client_service.summarize_client_filters(client)

    assert summary.naf_codes == ["56.10A"]


def test_resolve_client_listing_statuses_falls_back_to_defaults():
    client = SimpleNamespace(listing_statuses=["invalid"])
    statuses = client_service.resolve_client_listing_statuses(client)
    assert len(statuses) >= 1


def test_filter_clients_by_listing_status_flags_changes():
    clients = [_client(), _client(listing_statuses=["not_recent_creation"])]
    filtered, applied = client_service.filter_clients_by_listing_status(clients, "recent_creation")
    assert applied
    assert len(filtered) == 1


def test_filter_clients_by_listing_status_handles_empty_list():
    filtered, applied = client_service.filter_clients_by_listing_status([], "recent_creation")

    assert filtered == []
    assert applied is False


def test_build_subscription_index_and_filter_by_code():
    target_code = "5610A"
    subscribed_client = _client(subscriptions=[_subscription(target_code)])
    other_client = _client(subscriptions=[_subscription("4939B")])
    subscription_map, code_index = client_service.build_subscription_index([subscribed_client, other_client])

    assert subscribed_client.id in subscription_map
    assert "56.10A" in code_index

    filtered, applied = client_service.filter_clients_for_naf_code([subscribed_client, other_client], target_code)
    assert applied and filtered == [subscribed_client]


def test_filter_clients_for_naf_code_no_map_returns_all():
    clients = [_client(subscriptions=[])]

    filtered, applied = client_service.filter_clients_for_naf_code(clients, None)

    assert filtered == clients
    assert applied is False


def test_assign_establishments_to_clients_respects_filters():
    client_a = _client(subscriptions=[_subscription("5610A")])
    client_b = _client(
        subscriptions=[_subscription("4939B")],
        listing_statuses=["recent_creation_missing_contact"],
    )
    establishments = [
        _establishment("5610A", status="recent_creation"),
        _establishment("4939B", status="recent_creation_missing_contact"),
    ]

    assignments, filters_enabled = client_service.assign_establishments_to_clients([client_a, client_b], establishments)

    assert filters_enabled
    assert client_a.id in assignments and client_b.id in assignments
    assert all(est.naf_code == "5610A" for est in assignments[client_a.id])


def test_assign_establishments_to_clients_deduplicates_sirets():
    client = _client(subscriptions=[_subscription("5610A")])
    siret = "12345678901234"
    establishments = [
        _establishment("5610A", status="recent_creation"),
        _establishment("5610A", status="recent_creation"),
    ]
    establishments[1].siret = siret
    establishments[0].siret = siret

    assignments, _ = client_service.assign_establishments_to_clients([client], establishments)

    assert len(assignments[client.id]) == 1


def test_assign_establishments_includes_not_recent_with_contacts():
    """Les créations anciennes avec contacts doivent être incluses si recent_creation est autorisé."""
    client = _client(
        subscriptions=[_subscription("5610A")],
        listing_statuses=["recent_creation"],  # Seulement recent_creation autorisé
    )
    establishments = [
        # Création ancienne sans contact : exclue
        _establishment("5610A", status="not_recent_creation"),
        # Création ancienne avec téléphone : incluse
        _establishment("5610A", status="not_recent_creation", google_contact_phone="+33123456789"),
        # Création ancienne avec email : incluse
        _establishment("5610A", status="not_recent_creation", google_contact_email="contact@example.com"),
        # Création ancienne avec website : incluse
        _establishment("5610A", status="not_recent_creation", google_contact_website="https://example.com"),
        # Création récente : toujours incluse
        _establishment("5610A", status="recent_creation"),
    ]

    assignments, filters_enabled = client_service.assign_establishments_to_clients([client], establishments)

    assert filters_enabled
    assert client.id in assignments
    # On doit avoir 4 établissements : 3 créations anciennes avec contacts + 1 création récente
    assert len(assignments[client.id]) == 4
    # Vérifier que le premier (sans contact) n'est PAS inclus
    assigned_sirets = {est.siret for est in assignments[client.id]}
    assert establishments[0].siret not in assigned_sirets


def test_assign_establishments_to_clients_handles_empty_payload():
    assignments, filters_enabled = client_service.assign_establishments_to_clients([], [])

    assert assignments == {}
    assert filters_enabled is False


def test_dispatch_email_to_clients_sends_once(monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return date(2024, 1, 10)

    monkeypatch.setattr(client_service, "date", FixedDate)
    monkeypatch.setattr(client_service, "utcnow", lambda: datetime(2024, 1, 10, 12, 0, 0))

    client = _client(recipients=[SimpleNamespace(email="ops@example.com")])
    email_service = SimpleNamespace(send=lambda subject, body, recipients, html_body=None, attachments=None: None)
    payload = ClientEmailPayload(client=client, subject="Hi", text_body="Body")

    result = client_service.dispatch_email_to_clients(email_service, [payload])

    assert result.delivered == [client]
    assert result.sent_at == datetime(2024, 1, 10, 12, 0, 0)
    assert str(client.id) in result.recipients


def test_dispatch_email_to_clients_skips_inactive_or_recipientless(monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return date(2024, 1, 10)

    monkeypatch.setattr(client_service, "date", FixedDate)

    inactive = _client(start=date(2024, 2, 1))
    no_recipient = _client(recipients=[SimpleNamespace(email=None)])
    email_service = SimpleNamespace(send=lambda *args, **kwargs: None)
    payloads = [
        ClientEmailPayload(client=inactive, subject="Hi", text_body="Body"),
        ClientEmailPayload(client=no_recipient, subject="Hi", text_body="Body"),
    ]

    result = client_service.dispatch_email_to_clients(email_service, payloads)

    assert result.delivered == []
    assert result.sent_at is None


def test_dispatch_email_to_clients_collects_failures(monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return date(2024, 1, 10)

    class FixedDateTime(datetime):
        @classmethod
        def utcnow(cls):
            return datetime(2024, 1, 10, 12, 0, 0)

    monkeypatch.setattr(client_service, "date", FixedDate)
    monkeypatch.setattr(client_service, "datetime", FixedDateTime)

    client = _client(recipients=[SimpleNamespace(email="ops@example.com")])

    def failing_send(*args, **kwargs):
        raise RuntimeError("boom")

    email_service = SimpleNamespace(send=failing_send)
    payload = ClientEmailPayload(client=client, subject="Hi", text_body="Body")

    result = client_service.dispatch_email_to_clients(email_service, [payload])

    assert result.delivered == []
    assert len(result.failed) == 1
