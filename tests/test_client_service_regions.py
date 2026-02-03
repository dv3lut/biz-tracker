from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.services import client_service


def _client(*, active: bool, departments: list[object] | None = None):
    start_date = date(2024, 1, 1) if active else date(2024, 2, 1)
    end_date = None
    return SimpleNamespace(
        id="client",
        start_date=start_date,
        end_date=end_date,
        departments=departments or [],
        listing_statuses=["recent_creation"],
        recipients=[],
        subscriptions=[],
        stripe_subscriptions=[],
    )


def test_resolve_enabled_department_codes_returns_none_when_all_departments(monkeypatch):
    clients = [_client(active=True, departments=[])]
    monkeypatch.setattr(client_service, "get_all_clients", lambda session: clients)

    codes = client_service.resolve_enabled_department_codes(SimpleNamespace())

    assert codes is None


def test_resolve_enabled_department_codes_aggregates_active_clients(monkeypatch):
    clients = [
        _client(active=True, departments=[SimpleNamespace(code="75")]),
        _client(active=True, departments=[SimpleNamespace(code="33")]),
        _client(active=False, departments=[SimpleNamespace(code="31")]),
    ]
    monkeypatch.setattr(client_service, "get_all_clients", lambda session: clients)

    codes = client_service.resolve_enabled_department_codes(SimpleNamespace(), on_date=date(2024, 1, 1))

    assert codes == {"75", "33"}


def test_resolve_enabled_department_codes_empty_when_no_active(monkeypatch):
    clients = [_client(active=False, departments=[SimpleNamespace(code="75")])]
    monkeypatch.setattr(client_service, "get_all_clients", lambda session: clients)

    codes = client_service.resolve_enabled_department_codes(SimpleNamespace(), on_date=date(2024, 1, 3))

    assert codes == set()
