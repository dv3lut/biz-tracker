"""Unit tests for the AlertService filtering logic."""
from __future__ import annotations

from contextlib import contextmanager, ExitStack
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from app.services.alert_service import AlertService


class AlertServiceFilteringTests(unittest.TestCase):
    """Ensure alert creation honours the recent-only toggle."""

    def setUp(self) -> None:
        self.session = MagicMock()
        self.run = SimpleNamespace(id="run-1", scope_key="restaurants")

    @contextmanager
    def _patched_dependencies(self, recent_only: bool):
        stack = ExitStack()
        settings = SimpleNamespace(google=SimpleNamespace(alerts_only_recent_creations=recent_only))
        email_service = MagicMock()
        email_service.is_enabled.return_value = False
        email_service.is_configured.return_value = False
        stack.enter_context(patch("app.services.alert_service.get_settings", return_value=settings))
        stack.enter_context(patch("app.services.alert_service.EmailService", return_value=email_service))
        stack.enter_context(patch("app.services.alert_service.get_active_clients", return_value=[]))
        stack.enter_context(patch("app.services.alert_service.get_admin_emails", return_value=[]))
        stack.enter_context(
            patch("app.services.alert_service.assign_establishments_to_clients", return_value=({}, False))
        )
        stack.enter_context(patch("app.services.alert_service.collect_client_emails", return_value=[]))
        stack.enter_context(
            patch(
                "app.services.alert_service.dispatch_email_to_clients",
                return_value=SimpleNamespace(delivered=[], failed=[]),
            )
        )
        stack.enter_context(patch("app.services.alert_service.log_event"))
        try:
            yield
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

    def test_returns_empty_when_no_recent_listing_and_flag_enabled(self) -> None:
        establishments = [
            self._make_establishment("not_recent_creation", suffix="1"),
            self._make_establishment("unknown", suffix="2"),
        ]

        with self._patched_dependencies(recent_only=True):
            service = AlertService(self.session, self.run)
            alerts = service.create_google_alerts(establishments)

        self.assertEqual(alerts, [])
        self.session.add.assert_not_called()

    def test_keeps_only_recent_listing_when_flag_enabled(self) -> None:
        establishments = [
            self._make_establishment("not_recent_creation", suffix="1"),
            self._make_establishment("recent_creation", suffix="2"),
        ]

        with self._patched_dependencies(recent_only=True):
            service = AlertService(self.session, self.run)
            alerts = service.create_google_alerts(establishments)

        self.assertEqual(len(alerts), 1)
        self.session.add.assert_called_once()

    def test_keeps_all_listings_when_flag_disabled(self) -> None:
        establishments = [
            self._make_establishment("not_recent_creation", suffix="1"),
            self._make_establishment("recent_creation", suffix="2"),
        ]

        with self._patched_dependencies(recent_only=False):
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

        with self._patched_dependencies(recent_only=False):
            service = AlertService(self.session, self.run)
            alerts = service.create_google_alerts(establishments)

        self.assertEqual(len(alerts), 1)
        self.assertEqual(self.session.add.call_count, 1)


if __name__ == "__main__":
    unittest.main()
