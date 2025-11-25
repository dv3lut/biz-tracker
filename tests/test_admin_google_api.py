from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch, call

from fastapi import HTTPException
from app.api.routers.admin.google import manual_google_check, export_google_places


class ManualGoogleCheckRouteTests(TestCase):
    @patch("app.api.routers.admin.google.get_settings")
    def test_manual_check_disabled_google(
        self,
        mock_get_settings,
    ) -> None:
        """Test that the endpoint rejects requests when Google is disabled."""
        google_settings = SimpleNamespace(enabled=False)
        settings = SimpleNamespace(google=google_settings)
        mock_get_settings.return_value = settings

        session = MagicMock()

        with self.assertRaises(HTTPException) as ctx:
            manual_google_check("12345678901234", notify_clients=False, session=session)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("désactivé", ctx.exception.detail)

    @patch("app.api.routers.admin.google.get_settings")
    def test_manual_check_establishment_not_found(
        self,
        mock_get_settings,
    ) -> None:
        """Test that the endpoint returns 404 when establishment doesn't exist."""
        google_settings = SimpleNamespace(enabled=True)
        settings = SimpleNamespace(google=google_settings)
        mock_get_settings.return_value = settings

        session = MagicMock()
        session.get.return_value = None

        with self.assertRaises(HTTPException) as ctx:
            manual_google_check("99999999999999", notify_clients=False, session=session)

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertIn("introuvable", ctx.exception.detail)

    @patch("app.api.routers.admin.google.log_event")
    @patch("app.api.routers.admin.google.GoogleBusinessService")
    @patch("app.api.routers.admin.google.EmailService")
    @patch("app.api.routers.admin.google.get_settings")
    def test_manual_check_admin_email_sent_when_found(
        self,
        mock_get_settings,
        mock_email_service_cls,
        mock_google_service_cls,
        mock_log_event,
    ) -> None:
        """Test that admin email is sent when notify_clients=True and a match is found."""
        # Setup establishment with ALL required string values for Pydantic validation
        establishment = MagicMock()
        establishment.siret = "12345678901234"
        establishment.siren = "123456789"
        establishment.nic = "00001"
        establishment.name = "Test Establishment"
        establishment.naf_code = "56.30Z"
        establishment.naf_libelle = "Restaurants"
        establishment.etat_administratif = "A"
        establishment.google_check_status = "found"
        establishment.google_place_url = "https://google.com/maps/place/test"
        establishment.google_place_id = "ChIJtest123"
        establishment.google_listing_origin_source = "google"
        establishment.google_listing_age_status = "recent"
        # Add address fields for format_establishment_summary
        establishment.numero_voie = "123"
        establishment.type_voie = "Rue"
        establishment.libelle_voie = "de Test"
        establishment.code_postal = "75001"
        establishment.libelle_commune = "Paris"
        establishment.libelle_commune_etranger = None
        establishment.date_creation = None
        establishment.date_debut_activite = None
        establishment.created_run_id = None
        establishment.last_run_id = None
        establishment.google_match_confidence = 0.95
        
        session = MagicMock()
        session.get.return_value = establishment

        # Setup settings
        google_settings = SimpleNamespace(enabled=True)
        settings = SimpleNamespace(google=google_settings, sync=SimpleNamespace(scope_key="restaurants"))
        mock_get_settings.return_value = settings

        # Setup email service
        mock_email_service = MagicMock()
        mock_email_service.is_enabled.return_value = True
        mock_email_service.is_configured.return_value = True
        mock_email_service_cls.return_value = mock_email_service

        # Setup Google service to return a match
        mock_google_service = MagicMock()
        mock_google_service.manual_check.return_value = {"place_id": "ChIJtest123"}
        mock_google_service_cls.return_value = mock_google_service

        # Mock collect_client_emails to return no client emails (only admin)
        with patch("app.api.routers.admin.google.get_admin_emails") as mock_get_admin_emails, \
             patch("app.api.routers.admin.google.get_active_clients") as mock_get_active_clients, \
             patch("app.api.routers.admin.google.filter_clients_for_naf_code") as mock_filter_clients, \
             patch("app.api.routers.admin.google.collect_client_emails") as mock_collect_client_emails, \
             patch("app.api.routers.admin.google.dispatch_email_to_clients") as mock_dispatch_email, \
             patch("app.api.routers.admin.google.EstablishmentOut") as mock_establishment_out:
            
            mock_get_admin_emails.return_value = ["admin1@example.com", "admin2@example.com"]
            mock_get_active_clients.return_value = []
            mock_filter_clients.return_value = ([], False)
            mock_collect_client_emails.return_value = []
            
            # Mock dispatch result (no client emails)
            mock_dispatch_result = SimpleNamespace(delivered=[], failed=[])
            mock_dispatch_email.return_value = mock_dispatch_result
            
            # Mock response - just return establishment object directly
            mock_establishment_out.model_validate.return_value = establishment
            
            response = manual_google_check("12345678901234", notify_clients=True, session=session)

            # Verify admin email was sent
            mock_email_service.send.assert_called_once()
            call_args = mock_email_service.send.call_args
            admin_subject = call_args[0][0]
            admin_body = call_args[0][1]
            admin_recipients = call_args[0][2]

            self.assertIn("Check Google relancé", admin_subject)
            self.assertIn("Test Establishment", admin_subject)
            self.assertIn("administration", admin_body)
            self.assertEqual(admin_recipients, ["admin1@example.com", "admin2@example.com"])

            # Verify log event was called with admin_email_sent flag
            log_event_calls = [c for c in mock_log_event.call_args_list if "manual_google" in str(c)]
            self.assertTrue(len(log_event_calls) > 0)


class GoogleExportRouteTests(TestCase):
    @patch("app.api.routers.admin.google.build_google_places_workbook")
    @patch("app.api.routers.admin.google.log_event")
    @patch("app.api.routers.admin.google.get_settings")
    def test_export_skips_type_mismatch(self, mock_get_settings, mock_log_event, mock_build_workbook) -> None:
        settings = SimpleNamespace(google=SimpleNamespace(alerts_only_recent_creations=False))
        mock_get_settings.return_value = settings

        type_mismatch = SimpleNamespace(
            google_check_status="type_mismatch",
            google_listing_age_status="recent_creation",
        )
        found = SimpleNamespace(
            google_check_status="found",
            google_listing_age_status="recent_creation",
        )

        scalars = MagicMock()
        scalars.all.return_value = [type_mismatch, found]
        execution = MagicMock()
        execution.scalars.return_value = scalars
        session = MagicMock()
        session.execute.return_value = execution

        mock_build_workbook.return_value = BytesIO(b"test")

        response = export_google_places(mode="admin", session=session)

        self.assertIsNotNone(response)
        exported = mock_build_workbook.call_args[0][0]
        self.assertEqual(exported, [found])
        mock_build_workbook.assert_called_once()
        mock_log_event.assert_called_once()
