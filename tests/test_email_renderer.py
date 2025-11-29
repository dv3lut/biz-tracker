"""Tests for alert email rendering helpers."""
from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from app.services.alerts.email_renderer import render_admin_email, render_client_email
from app.services.alerts.formatter import EstablishmentFormatter


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
        self.assertIn("Création récente sans contact", text_body)
        self.assertIn("Création ancienne", text_body)
        self.assertNotIn("Non déterminé", text_body)
        self.assertGreaterEqual(text_body.count("0 nouvel établissement détecté."), 1)
        self.assertIn(
            "<h3 style=\"font-size:18px;margin:24px 0 8px;\">Création récente sans contact</h3>",
            html_body,
        )
        self.assertIn("0 nouvel établissement détecté.", html_body)
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


if __name__ == "__main__":
    unittest.main()
