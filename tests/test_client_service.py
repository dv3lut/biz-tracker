"""Tests for helpers in client_service handling listing status filters."""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from uuid import UUID, uuid4

from app.services.client_service import assign_establishments_to_clients, filter_clients_by_listing_status


def _make_client(
    *,
    listing_statuses: list[str] | None = None,
    subscriptions: list[object] | None = None,
    identifier: UUID | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=identifier or uuid4(),
        listing_statuses=listing_statuses if listing_statuses is not None else ["recent_creation"],
        subscriptions=subscriptions or [],
        recipients=[],
    )


def _make_subscription(naf_code: str, *, is_active: bool = True) -> SimpleNamespace:
    return SimpleNamespace(subcategory=SimpleNamespace(naf_code=naf_code, is_active=is_active))


def _make_establishment(naf_code: str, status: str, *, siret: str) -> SimpleNamespace:
    return SimpleNamespace(
        naf_code=naf_code,
        google_listing_age_status=status,
        siret=siret,
    )


class ClientServiceListingStatusTests(unittest.TestCase):
    def test_assignments_filter_by_status_without_subscriptions(self) -> None:
        clients = [
            _make_client(listing_statuses=["recent_creation"], identifier=uuid4()),
            _make_client(listing_statuses=["not_recent_creation"], identifier=uuid4()),
        ]
        establishments = [
            _make_establishment("56.10A", "recent_creation", siret="00000000000001"),
            _make_establishment("56.10A", "not_recent_creation", siret="00000000000002"),
        ]

        assignments, filters_enabled = assign_establishments_to_clients(clients, establishments)

        self.assertTrue(filters_enabled)
        self.assertEqual({est.siret for est in assignments[clients[0].id]}, {"00000000000001"})
        self.assertEqual({est.siret for est in assignments[clients[1].id]}, {"00000000000002"})

    def test_assignments_honor_status_with_subscriptions(self) -> None:
        client_recent = _make_client(
            listing_statuses=["recent_creation"],
            subscriptions=[_make_subscription("5610A")],
            identifier=uuid4(),
        )
        client_not_recent = _make_client(
            listing_statuses=["not_recent_creation"],
            subscriptions=[_make_subscription("5610B")],
            identifier=uuid4(),
        )
        establishments = [
            _make_establishment("5610A", "recent_creation", siret="10000000000000"),
            _make_establishment("5610B", "not_recent_creation", siret="20000000000000"),
            _make_establishment("5610A", "not_recent_creation", siret="30000000000000"),
        ]

        assignments, filters_enabled = assign_establishments_to_clients(
            [client_recent, client_not_recent],
            establishments,
        )

        self.assertTrue(filters_enabled)
        self.assertEqual({est.siret for est in assignments[client_recent.id]}, {"10000000000000"})
        self.assertEqual({est.siret for est in assignments[client_not_recent.id]}, {"20000000000000"})

    def test_filter_clients_by_listing_status(self) -> None:
        clients = [
            _make_client(listing_statuses=["recent_creation", "not_recent_creation"], identifier=uuid4()),
            _make_client(listing_statuses=["not_recent_creation"], identifier=uuid4()),
        ]

        filtered, applied = filter_clients_by_listing_status(clients, "recent_creation")

        self.assertTrue(applied)
        self.assertEqual(len(filtered), 1)
        self.assertIn("recent_creation", filtered[0].listing_statuses)


if __name__ == "__main__":
    unittest.main()
