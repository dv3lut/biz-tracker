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


def _department(*, identifier: str):
    return SimpleNamespace(id=identifier, code=identifier)


def _subcategory(*, identifier: str, is_active: bool = True):
    return SimpleNamespace(id=identifier, is_active=is_active)


def _subscription(subcategory):
    return SimpleNamespace(subcategory=subcategory)


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


def test_build_subcategory_department_index_collects_departments():
    subcategory = _subcategory(identifier="sub-1")
    clients = [
        SimpleNamespace(departments=[_department(identifier="dep-75")], subscriptions=[_subscription(subcategory)]),
        SimpleNamespace(departments=[_department(identifier="dep-33")], subscriptions=[_subscription(subcategory)]),
    ]

    mapping, all_departments = client_service.build_subcategory_department_index(clients)

    assert all_departments == set()
    assert mapping == {"sub-1": {"dep-75", "dep-33"}}


def test_build_subcategory_department_index_marks_all_departments():
    subcategory = _subcategory(identifier="sub-1")
    clients = [SimpleNamespace(departments=[], subscriptions=[_subscription(subcategory)])]

    mapping, all_departments = client_service.build_subcategory_department_index(clients)

    assert all_departments == {"sub-1"}
    assert mapping == {}


def test_build_subcategory_department_index_skips_inactive_subcategory():
    subcategory = _subcategory(identifier="sub-1", is_active=False)
    clients = [
        SimpleNamespace(departments=[_department(identifier="dep-75")], subscriptions=[_subscription(subcategory)])
    ]

    mapping, all_departments = client_service.build_subcategory_department_index(clients)

    assert mapping == {}
    assert all_departments == set()
