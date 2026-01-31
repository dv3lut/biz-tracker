"""Tests for alert email rendering helpers."""
from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from app.services.alerts.email_renderer import (
    _format_listing_status_labels,
    _section_title_for_status,
    get_client_listing_status_label,
    render_admin_email,
    render_client_email,
)
from app.services.alerts.formatter import EstablishmentFormatter
from app.services.client_service import ClientFilterSummary


class EmailRendererTests(unittest.TestCase):
    """Validate the formatting of client and admin emails."""

    def setUp(self) -> None:
        session = MagicMock()
        session.execute.return_value.all.return_value = []
        self.formatter = EstablishmentFormatter(session)

    def _make_establishment(self, *, name: str, status: str, google_url: str | None = None):
        origin = datetime(2024, 1, 1, 12, 0, 0)
        return SimpleNamespace(
            name=name,
            siret="12345678901234",
            siren="123456789",
            naf_code=None,
            naf_libelle=None,
            date_creation=date(2024, 1, 1),
            numero_voie="10",
            type_voie="Rue",
            libelle_voie="Exemple",
            complement_adresse=None,
            indice_repetition=None,
            code_postal="75000",
            libelle_commune="Paris",
            libelle_commune_etranger=None,
            code_commune="75056",
            code_pays="FR",
            libelle_pays="France",
            google_place_url=google_url,
            google_place_id="place-id" if google_url else "",
            google_listing_age_status=status,
            google_listing_origin_at=origin,
            google_check_status="found",
            google_match_confidence=0.95,
            date_dernier_traitement_etablissement=None,
        )

    def test_client_email_groups_by_status_and_hides_origin(self) -> None:
        establishments = [
            self._make_establishment(
                name="Boulangerie Nova",
                status="recent_creation",
                google_url="https://maps.google.com/?cid=1",
            ),
            self._make_establishment(
                name="Café des Halles",
                status="not_recent_creation",
                google_url="https://maps.google.com/?cid=2",
            ),
        ]

        text_body, html_body = render_client_email(self.formatter, establishments)

        self.assertIn("Création récente", text_body)
        self.assertIn("- Boulangerie Nova", text_body)
        self.assertNotIn("Création récente sans contact", text_body)
        self.assertIn("Modification administrative récente", text_body)
        self.assertNotIn("Création ancienne", text_body)
        self.assertNotIn("Non déterminé", text_body)
        self.assertEqual(text_body.count("0 nouvel établissement détecté."), 0)
        self.assertIn("Statut :", html_body)
        self.assertNotIn("0 nouvel établissement détecté.", html_body)
        self.assertNotIn("origine", text_body)
        self.assertNotIn("origine", html_body)

    def test_admin_email_omits_origin_reference(self) -> None:
        establishments = [
            self._make_establishment(
                name="Admin Bistro",
                status="recent_creation_missing_contact",
                google_url="https://maps.google.com/?cid=3",
            )
        ]

        text_body, html_body = render_admin_email(self.formatter, establishments)

        self.assertIn("Statut fiche Google : Création récente (contact manquant)", text_body)
        self.assertIn("Statut&nbsp;: Création récente (contact manquant)", html_body)
        self.assertNotIn("origine", text_body)
        self.assertNotIn("origine", html_body)

    def test_client_email_summary_with_filters_and_missing_links(self) -> None:
        establishment = self._make_establishment(name="Sans URL", status="recent_creation_missing_contact", google_url=None)
        filters = ClientFilterSummary(listing_statuses=["recent_creation"], naf_codes=["5610A"])

        text_body, html_body = render_client_email(self.formatter, [establishment], filters=filters)

        self.assertNotIn("Statuts Google surveillés", text_body)
        self.assertNotIn("Codes NAF ciblés", text_body)
        self.assertIn("Lien Google indisponible", html_body)
        self.assertNotIn("Statut fiche Google", text_body)
        self.assertNotIn("Statut fiche Google", html_body)
        self.assertNotIn("<h3", html_body)
        self.assertNotIn("5610A", text_body)
        self.assertNotIn("Statuts Google surveillés", html_body)

    def test_client_email_zero_matches_prompts_future_notification(self) -> None:
        text_body, html_body = render_client_email(self.formatter, [])

        self.assertIn("0 nouvel établissement détecté", text_body)
        self.assertIn("Nous vous notifierons", text_body)
        self.assertIn("0 nouvel établissement détecté", html_body)

    def test_client_email_includes_previous_month_day_section(self) -> None:
        establishment = self._make_establishment(
            name="Bistrot du Mois",
            status="recent_creation",
            google_url="https://maps.google.com/?cid=42",
        )
        establishment_second = self._make_establishment(
            name="Ancien Bistro",
            status="not_recent_creation",
            google_url="https://maps.google.com/?cid=99",
        )
        previous_date = date(2024, 12, 16)

        text_body, html_body = render_client_email(
            self.formatter,
            [],
            previous_month_day_establishments=[establishment_second, establishment],
            previous_month_day_date=previous_date,
        )

        self.assertIn("Pour rappel, voici les alertes qui ont été générées le 16 décembre 2024", text_body)
        self.assertIn("Bistrot du Mois", text_body)
        self.assertIn("[Rappel mensuel] Bistrot du Mois", text_body)
        self.assertLess(text_body.find("Bistrot du Mois"), text_body.find("Ancien Bistro"))
        self.assertIn("Rappel mensuel", html_body)

    def test_client_email_previous_month_section_empty(self) -> None:
        previous_date = date(2024, 12, 16)

        text_body, html_body = render_client_email(
            self.formatter,
            [],
            previous_month_day_establishments=[],
            previous_month_day_date=previous_date,
        )

        self.assertIn("Aucune alerte n'a été générée ce jour-là", text_body)
        self.assertIn("Aucune alerte n'a été générée ce jour-là", html_body)

    def test_client_email_helper_labels(self) -> None:
        labels = _format_listing_status_labels(["recent_creation", "unknown"])

        self.assertEqual(labels[0], "Création récente")
        self.assertEqual(labels[1], "Non déterminé")
        self.assertEqual(_section_title_for_status("recent_creation_missing_contact"), "Création récente sans contact")
        self.assertEqual(get_client_listing_status_label(None), "Non déterminé")


if __name__ == "__main__":
    unittest.main()
