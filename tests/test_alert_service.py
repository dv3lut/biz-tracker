"""Unit tests for the AlertService filtering logic."""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
from datetime import date
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services.alert_service import AlertService


class AlertServiceFilteringTests(unittest.TestCase):
    """Ensure alert creation filters correctly based on Google status."""

    def setUp(self) -> None:
        self.session = MagicMock()
        self.run = SimpleNamespace(id="run-1", scope_key="restaurants")

    @contextmanager
    def _patched_dependencies(
        self,
        *,
        active_clients: list[SimpleNamespace] | None = None,
        admin_recipients: list[str] | None = None,
        client_emails: list[str] | None = None,
        assignment_map: dict | None = None,
        filters_configured: bool = False,
    ):
        stack = ExitStack()
        email_service = MagicMock()
        email_service.is_enabled.return_value = True
        email_service.is_configured.return_value = True
        stack.enter_context(patch("app.services.alert_service.EmailService", return_value=email_service))
        stack.enter_context(
            patch(
                "app.services.alert_service.get_active_clients",
                return_value=active_clients or [],
            )
        )
        stack.enter_context(
            patch(
                "app.services.alert_service.get_admin_emails",
                return_value=admin_recipients or [],
            )
        )
        stack.enter_context(
            patch(
                "app.services.alert_service.assign_establishments_to_clients",
                return_value=(assignment_map or {}, filters_configured),
            )
        )
        stack.enter_context(
            patch(
                "app.services.alert_service.collect_client_emails",
                return_value=client_emails or [],
            )
        )
        dispatch_mock = MagicMock(
            return_value=SimpleNamespace(delivered=[], failed=[], sent_at=None)
        )
        stack.enter_context(
            patch(
                "app.services.alert_service.dispatch_email_to_clients",
                dispatch_mock,
            )
        )
        log_mock = stack.enter_context(patch("app.services.alert_service.log_event"))
        try:
            yield SimpleNamespace(dispatch_mock=dispatch_mock, log_mock=log_mock, email_service=email_service)
        finally:
            stack.close()

    def _make_establishment(self, status: str, *, suffix: str) -> SimpleNamespace:
        return SimpleNamespace(
            siret=f"0000000000000{suffix}",
            siren=f"0000000000{suffix}",
            name=f"Etablissement {suffix}",
            google_check_status="found",
            naf_code=None,
            naf_libelle=None,
            date_creation=None,
            google_listing_origin_at=None,
            google_listing_age_status=status,
            numero_voie=None,
            type_voie=None,
            libelle_voie=None,
            complement_adresse=None,
            indice_repetition=None,
            code_postal="75000",
            libelle_commune="Paris",
            libelle_commune_etranger=None,
            code_commune="75101",
            code_pays="FR",
            libelle_pays="France",
            google_place_url="https://maps.google.com/?cid=123",
            google_place_id="ChIJ123",
            google_match_confidence=0.95,
            date_dernier_traitement_etablissement=None,
        )

    def test_returns_empty_when_no_found_listing(self) -> None:
        establishments = [
            self._make_establishment("not_recent_creation", suffix="1"),
            self._make_establishment("recent_creation", suffix="2"),
        ]
        establishments[0].google_check_status = "pending"
        establishments[1].google_check_status = "not_found"

        with self._patched_dependencies():
            service = AlertService(self.session, self.run)
            alerts = service.create_google_alerts(establishments)

        self.assertEqual(alerts, [])
        self.session.add.assert_not_called()

    def test_keeps_all_found_listings(self) -> None:
        establishments = [
            self._make_establishment("not_recent_creation", suffix="1"),
            self._make_establishment("recent_creation", suffix="2"),
        ]

        with self._patched_dependencies():
            service = AlertService(self.session, self.run)
            alerts = service.create_google_alerts(establishments)

        self.assertEqual(len(alerts), 2)
        self.assertEqual(self.session.add.call_count, 2)

    def test_excludes_type_mismatch_from_alerts(self) -> None:
        establishments = [
            self._make_establishment("recent_creation", suffix="1"),
            self._make_establishment("recent_creation", suffix="2"),
        ]
        establishments[1].google_check_status = "type_mismatch"

        with self._patched_dependencies():
            service = AlertService(self.session, self.run)
            alerts = service.create_google_alerts(establishments)

        self.assertEqual(len(alerts), 1)
        self.assertEqual(self.session.add.call_count, 1)

    def test_client_notifications_can_be_disabled(self) -> None:
        establishments = [self._make_establishment("recent_creation", suffix="1")]

        with self._patched_dependencies() as deps:
            service = AlertService(
                self.session,
                self.run,
                client_notifications_enabled=False,
            )
            alerts = service.create_google_alerts(establishments)

        self.assertEqual(len(alerts), 1)
        deps.dispatch_mock.assert_not_called()
        reasons = [kwargs.get("reason") for _, kwargs in deps.log_mock.call_args_list]
        self.assertIn("client_notifications_disabled", [reason for reason in reasons if reason])

    def test_sends_digest_when_no_establishments(self) -> None:
        client = SimpleNamespace(
            id="client-1",
            name="Client A",
            recipients=[SimpleNamespace(email="client@example.com")],
            subscriptions=[],
            listing_statuses=None,
            start_date=date.today(),
            end_date=None,
        )

        with self._patched_dependencies(active_clients=[client]) as deps:
            service = AlertService(self.session, self.run)
            alerts = service.create_google_alerts([])

        self.assertEqual(alerts, [])
        deps.dispatch_mock.assert_called_once()
        payloads = deps.dispatch_mock.call_args[0][1]
        self.assertEqual(len(payloads), 1)
        self.assertEqual(payloads[0].subject, "[restaurants] 0 fiche(s) Google détectée(s)")

    def test_targeted_clients_receive_zero_digest(self) -> None:
        client_a = SimpleNamespace(
            id=uuid4(),
            name="Client A",
            recipients=[SimpleNamespace(email="a@example.com")],
            subscriptions=[],
            listing_statuses=None,
            start_date=date.today(),
            end_date=None,
        )
        client_b = SimpleNamespace(
            id=uuid4(),
            name="Client B",
            recipients=[SimpleNamespace(email="b@example.com")],
            subscriptions=[],
            listing_statuses=None,
            start_date=date.today(),
            end_date=None,
        )

        with self._patched_dependencies(active_clients=[client_a, client_b]) as deps:
            service = AlertService(
                self.session,
                self.run,
                target_client_ids=[client_a.id],
            )
            service.create_google_alerts([])

        deps.dispatch_mock.assert_called_once()
        payloads = deps.dispatch_mock.call_args[0][1]
        self.assertEqual(len(payloads), 1)
        self.assertEqual(payloads[0].client.id, client_a.id)

    def test_targeted_clients_receive_zero_digest_even_when_other_matches_exist(self) -> None:
        client_a = SimpleNamespace(
            id=uuid4(),
            name="Client A",
            recipients=[SimpleNamespace(email="a@example.com")],
            subscriptions=[],
            listing_statuses=None,
            start_date=date.today(),
            end_date=None,
        )
        client_b = SimpleNamespace(
            id=uuid4(),
            name="Client B",
            recipients=[SimpleNamespace(email="b@example.com")],
            subscriptions=[],
            listing_statuses=None,
            start_date=date.today(),
            end_date=None,
        )
        establishment = self._make_establishment("recent_creation", suffix="5")

        with self._patched_dependencies(
            active_clients=[client_a, client_b],
            assignment_map={},
            filters_configured=True,
        ) as deps:
            service = AlertService(
                self.session,
                self.run,
                target_client_ids=[client_a.id],
            )
            service.create_google_alerts([establishment])

        deps.dispatch_mock.assert_called_once()
        payloads = deps.dispatch_mock.call_args[0][1]
        self.assertEqual(len(payloads), 1)
        self.assertEqual(payloads[0].client.id, client_a.id)
        self.assertEqual(payloads[0].subject, "[restaurants] 0 fiche(s) Google détectée(s)")

    def test_admin_notifications_can_be_disabled(self) -> None:
        establishment = self._make_establishment("recent_creation", suffix="9")

        with self._patched_dependencies(admin_recipients=["admin@example.com"]) as deps:
            service = AlertService(
                self.session,
                self.run,
                admin_notifications_enabled=False,
            )
            service.create_google_alerts([establishment])

        deps.email_service.send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
