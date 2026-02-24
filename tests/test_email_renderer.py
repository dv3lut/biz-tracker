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

    def _make_client(self, *, use_subcategory_label: bool = False):
        return SimpleNamespace(use_subcategory_label_in_client_alerts=use_subcategory_label)

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

        text_body, html_body = render_client_email(
            self.formatter,
            establishments,
            client=self._make_client(),
        )

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

    def test_admin_email_handles_missing_google_link(self) -> None:
        establishment = self._make_establishment(
            name="Sans Google",
            status="recent_creation",
            google_url=None,
        )
        establishment.google_place_id = None

        _, html_body = render_admin_email(self.formatter, [establishment])

        self.assertIn("Lien indisponible", html_body)
        self.assertIn("Statut", html_body)

    def test_client_email_summary_with_filters_and_missing_links(self) -> None:
        establishment = self._make_establishment(name="Sans URL", status="recent_creation_missing_contact", google_url=None)
        filters = ClientFilterSummary(listing_statuses=["recent_creation"], naf_codes=["5610A"])

        text_body, html_body = render_client_email(
            self.formatter,
            [establishment],
            client=self._make_client(),
            filters=filters,
        )

        self.assertNotIn("Statuts Google surveillés", text_body)
        self.assertNotIn("Codes NAF ciblés", text_body)
        self.assertIn("Lien Google indisponible", html_body)
        self.assertNotIn("Statut fiche Google", text_body)
        self.assertNotIn("Statut fiche Google", html_body)
        self.assertNotIn("5610A", text_body)
        self.assertNotIn("Statuts Google surveillés", html_body)

    def test_client_email_handles_empty_listing_statuses_filter(self) -> None:
        establishment = self._make_establishment(
            name="Sans filtre",
            status="recent_creation",
            google_url="https://maps.google.com/?cid=5",
        )
        filters = ClientFilterSummary(listing_statuses=[], naf_codes=[])

        text_body, html_body = render_client_email(
            self.formatter,
            [establishment],
            client=self._make_client(),
            filters=filters,
        )

        self.assertIn("Création récente", text_body)
        self.assertIn("Statut :", html_body)

    def test_client_email_includes_linkedin_buttons(self) -> None:
        establishment = self._make_establishment(
            name="LinkedIn Bistro",
            status="recent_creation",
            google_url="https://maps.google.com/?cid=7",
        )
        establishment.directors = [
            SimpleNamespace(
                is_physical_person=True,
                linkedin_profile_url="https://linkedin.com/in/jane",
                linkedin_profile_data={"title": "CEO"},
                quality=None,
            )
        ]

        text_body, html_body = render_client_email(
            self.formatter,
            [establishment],
            client=self._make_client(),
        )

        self.assertIn("LinkedIn : https://linkedin.com/in/jane", text_body)
        self.assertIn("Contacter le CEO sur LinkedIn", html_body)

    def test_client_email_fallbacks_when_filter_has_unknown_status(self) -> None:
        establishment = self._make_establishment(
            name="Filtre inconnu",
            status="recent_creation",
            google_url="https://maps.google.com/?cid=8",
        )
        filters = ClientFilterSummary(listing_statuses=["unknown_status"], naf_codes=[])

        text_body, html_body = render_client_email(
            self.formatter,
            [establishment],
            client=self._make_client(),
            filters=filters,
        )

        self.assertIn("Création récente", text_body)
        self.assertIn("Statut :", html_body)

    def test_client_email_use_subcategory_label_without_label(self) -> None:
        establishment = self._make_establishment(
            name="Sans catégorie",
            status="recent_creation",
            google_url="https://maps.google.com/?cid=9",
        )
        establishment.naf_code = None
        establishment.naf_libelle = None

        text_body, _ = render_client_email(
            self.formatter,
            [establishment],
            client=self._make_client(use_subcategory_label=True),
        )

        self.assertIn("- Sans catégorie", text_body)

    def test_client_email_zero_matches_prompts_future_notification(self) -> None:
        text_body, html_body = render_client_email(self.formatter, [], client=self._make_client())

        self.assertIn("Aucun nouvel établissement", text_body)
        self.assertIn("Nous vous notifierons", text_body)
        self.assertIn("Aucun nouvel établissement", html_body)
        self.assertNotIn("0 nouvel établissement détecté", text_body)
        self.assertNotIn("0 nouvel établissement détecté", html_body)

    def test_client_email_mentions_alerts_outside_departments(self) -> None:
        establishment = self._make_establishment(
            name="Bistrot Local",
            status="recent_creation",
            google_url="https://maps.google.com/?cid=10",
        )

        text_body, html_body = render_client_email(
            self.formatter,
            [establishment],
            client=self._make_client(),
            outside_google_count=19,
            outside_no_google_count=5,
        )

        self.assertIn("territoire", text_body)
        self.assertIn("19", text_body)
        self.assertIn("5", text_body)
        self.assertIn("territoire", html_body)
        self.assertIn("19", html_body)
        self.assertIn("5", html_body)

    def test_client_email_scope_summary_shows_region_groups(self) -> None:
        """Le bloc périmètre regroupe les départements par région avec accordéon <details>."""
        establishment = self._make_establishment(
            name="Bistrot Régional",
            status="recent_creation",
            google_url="https://maps.google.com/?cid=42",
        )
        region_idf = SimpleNamespace(name="Île-de-France", code="11")
        region_bretagne = SimpleNamespace(name="Bretagne", code="53")
        dept_75 = SimpleNamespace(code="75", name="Paris", region=region_idf)
        dept_77 = SimpleNamespace(code="77", name="Seine-et-Marne", region=region_idf)
        dept_29 = SimpleNamespace(code="29", name="Finistère", region=region_bretagne)

        client = SimpleNamespace(
            use_subcategory_label_in_client_alerts=False,
            departments=[dept_75, dept_77, dept_29],
            subscriptions=[],
            category_ids=[],
        )

        text_body, html_body = render_client_email(
            self.formatter,
            [establishment],
            client=client,
        )

        # Texte : les régions et le nombre de depts
        self.assertIn("Île-de-France (2)", text_body)
        self.assertIn("Bretagne (1)", text_body)
        self.assertIn("75 Paris", text_body)
        self.assertIn("29 Finistère", text_body)
        self.assertIn("Périmètre :", text_body)
        # HTML : les <details> avec les noms de région
        self.assertIn("Île-de-France", html_body)
        self.assertIn("Bretagne", html_body)
        self.assertNotIn("<details", html_body)
        self.assertNotIn("<summary", html_body)
        self.assertIn("Périmètre surveillé", html_body)
        self.assertNotIn("France entière", html_body)

    def test_client_email_scope_summary_all_france(self) -> None:
        """Si aucun département sélectionné → pas de bloc périmètre (sans catégories)."""
        establishment = self._make_establishment(
            name="Bistrot National",
            status="recent_creation",
            google_url="https://maps.google.com/?cid=99",
        )
        client = SimpleNamespace(
            use_subcategory_label_in_client_alerts=False,
            departments=[],  # vide = France entière
            subscriptions=[],
            category_ids=[],
        )

        text_body, html_body = render_client_email(
            self.formatter,
            [establishment],
            client=client,
        )

        # Sans catégories ni depts → pas de bloc périmètre
        self.assertNotIn("Périmètre surveillé", text_body)
        self.assertNotIn("Périmètre surveillé", html_body)

    def test_client_email_scope_summary_all_depts_explicit(self) -> None:
        """Si 95+ départements configurés → affiche 'France entière' sans liste de régions."""
        establishment = self._make_establishment(
            name="Bistrot Ubiquitaire",
            status="recent_creation",
            google_url="https://maps.google.com/?cid=200",
        )
        # Simuler 95 départements
        region_all = SimpleNamespace(name="France", code="00")
        many_depts = [
            SimpleNamespace(code=str(i).zfill(2), name=f"Dept {i}", region=region_all)
            for i in range(1, 96)
        ]
        # Ajouter une catégorie pour que le bloc s'affiche
        subcategory = SimpleNamespace(
            is_active=True,
            naf_code="5610A",
            categories=[SimpleNamespace(id="cat-1", name="Restauration")],
        )
        subscription = SimpleNamespace(subcategory=subcategory)
        client = SimpleNamespace(
            use_subcategory_label_in_client_alerts=False,
            departments=many_depts,
            subscriptions=[subscription],
            category_ids=[],
        )

        text_body, html_body = render_client_email(
            self.formatter,
            [establishment],
            client=client,
        )

        self.assertIn("France entière", text_body)
        self.assertIn("France entière", html_body)
        # Pas de liste de régions individuelles
        self.assertNotIn("<details", html_body)
        self.assertNotIn("Périmètre :", text_body)

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
            client=self._make_client(),
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
            client=self._make_client(),
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

    def test_client_email_uses_subcategory_label_when_enabled(self) -> None:
        session = MagicMock()
        session.execute.return_value.all.return_value = [
            ("56.10A", "Restauration rapide", "Restauration")
        ]
        formatter = EstablishmentFormatter(session)
        establishment = self._make_establishment(
            name="Food Express",
            status="recent_creation",
            google_url="https://maps.google.com/?cid=3",
        )
        establishment.naf_code = "56.10A"

        text_body, html_body = render_client_email(
            formatter,
            [establishment],
            client=self._make_client(use_subcategory_label=True),
        )

        self.assertIn("Catégorie : Restauration rapide (56.10A)", text_body)
        self.assertIn("Catégorie :</span> Restauration rapide (56.10A)", html_body)

    def test_client_email_lists_multiple_categories_for_same_naf(self) -> None:
        formatter = EstablishmentFormatter(MagicMock())
        establishment = self._make_establishment(
            name="Food Express",
            status="recent_creation",
            google_url="https://maps.google.com/?cid=3",
        )
        establishment.naf_code = "56.10A"

        category_one = SimpleNamespace(id="cat-1", name="Restauration")
        category_two = SimpleNamespace(id="cat-2", name="Traiteur")
        subcategory_one = SimpleNamespace(
            name="Restauration rapide",
            naf_code="56.10A",
            is_active=True,
            categories=[category_one],
        )
        subcategory_two = SimpleNamespace(
            name="Restauration rapide",
            naf_code="56.10A",
            is_active=True,
            categories=[category_two],
        )
        client = SimpleNamespace(
            use_subcategory_label_in_client_alerts=False,
            category_ids=["cat-1", "cat-2"],
            subscriptions=[
                SimpleNamespace(subcategory=subcategory_one),
                SimpleNamespace(subcategory=subcategory_two),
            ],
        )

        text_body, html_body = render_client_email(
            formatter,
            [establishment],
            client=client,
        )

        self.assertIn("Catégorie : Restauration, Traiteur", text_body)
        self.assertIn("Catégorie :</span> Restauration, Traiteur", html_body)

    def test_client_email_shows_directors_info(self) -> None:
        """Les dirigeants personnes physiques doivent apparaître dans la carte."""
        establishment = self._make_establishment(
            name="Bistrot des Dirigeants",
            status="recent_creation",
            google_url="https://maps.google.com/?cid=100",
        )
        establishment.directors = [
            SimpleNamespace(
                is_physical_person=True,
                first_names="Jean",
                last_name="Martin",
                quality="Gérant",
                birth_month=3,
                birth_year=1978,
                linkedin_profile_url=None,
                linkedin_profile_data=None,
            ),
            SimpleNamespace(
                is_physical_person=False,
                first_names=None,
                last_name=None,
                quality="SAS",
                birth_month=None,
                birth_year=None,
                linkedin_profile_url=None,
                linkedin_profile_data=None,
            ),
        ]

        text_body, html_body = render_client_email(
            self.formatter,
            [establishment],
            client=self._make_client(),
        )

        self.assertIn("Jean MARTIN", text_body)
        self.assertIn("(Gérant)", text_body)
        self.assertIn("né(e) en mars 1978", text_body)
        self.assertIn("Jean", html_body)  # prénoms en casse normale
        self.assertIn("MARTIN", html_body)  # NOM en majuscules/gras
        self.assertIn("Dirigeant(s)", html_body)
        # Le dirigeant personne morale ne doit pas apparaître
        self.assertNotIn("SAS", text_body)

    def test_client_email_shows_sole_proprietorship_badge(self) -> None:
        """Un badge 'Entreprise individuelle' doit s'afficher si applicable."""
        establishment = self._make_establishment(
            name="Auto-entrepreneur Express",
            status="recent_creation",
            google_url="https://maps.google.com/?cid=101",
        )
        establishment.is_sole_proprietorship = True

        text_body, html_body = render_client_email(
            self.formatter,
            [establishment],
            client=self._make_client(),
        )

        self.assertIn("Entreprise individuelle", text_body)
        self.assertIn("Entreprise individuelle", html_body)

    def test_client_email_shows_no_google_section(self) -> None:
        """Les établissements sans fiche Google doivent apparaître dans une section dédiée violet."""
        google_est = self._make_establishment(
            name="Avec Google",
            status="recent_creation",
            google_url="https://maps.google.com/?cid=200",
        )
        no_google_est = self._make_establishment(
            name="Sans Google",
            status="recent_creation",
            google_url=None,
        )

        text_body, html_body = render_client_email(
            self.formatter,
            [google_est],
            client=self._make_client(),
            no_google_establishments=[no_google_est],
        )

        # Doit afficher les deux établissements
        self.assertIn("Avec Google", text_body)
        self.assertIn("Sans Google", text_body)
        # Section sans Google avec bon libellé
        self.assertIn("Modification administrative récente", text_body)
        # Le statut violet doit apparaître dans le HTML
        self.assertIn("8b5cf6", html_body)
        # Total dans l'intro
        self.assertIn("2", text_body)

    def test_client_email_no_google_only_shows_total(self) -> None:
        """Quand il n'y a que des établissements sans Google, le total doit être mis en avant."""
        no_google_est = self._make_establishment(
            name="Administratif Seulement",
            status="recent_creation",
            google_url=None,
        )

        text_body, html_body = render_client_email(
            self.formatter,
            [],
            client=self._make_client(),
            no_google_establishments=[no_google_est],
        )

        self.assertIn("Administratif Seulement", text_body)
        self.assertIn("Modification administrative récente", text_body)
        self.assertIn("identifié", text_body)
        # Pas de message "Aucun établissement"
        self.assertNotIn("Aucun nouvel établissement n'a été détecté", text_body)

    def test_client_email_intro_has_bold_total(self) -> None:
        """Le total doit apparaître en gras dans le HTML."""
        establishment = self._make_establishment(
            name="Bistrot Test",
            status="recent_creation",
            google_url="https://maps.google.com/?cid=300",
        )

        _, html_body = render_client_email(
            self.formatter,
            [establishment],
            client=self._make_client(),
        )

        # Le total doit être dans un tag <strong>
        self.assertIn("<strong", html_body)
        self.assertIn("identifi", html_body)

    def test_client_email_includes_linkedin_only_establishment(self) -> None:
        """Test that establishments with LinkedIn but no Google are included in client email."""
        # Create establishment with no Google
        establishment = self._make_establishment(
            name="LinkedIn Only Bistro",
            status="not_recent_creation",
            google_url=None,
        )
        establishment.google_check_status = "not_found"
        
        # Add director with LinkedIn profile
        director = SimpleNamespace(
            is_physical_person=True,
            linkedin_profile_url="https://linkedin.com/in/john-smith",
            linkedin_profile_data={"name": "John Smith"},
            first_name="John",
            last_name="Smith",
            quality="P",
        )
        establishment.directors = [director]
        
        text_body, html_body = render_client_email(
            self.formatter,
            [establishment],
            client=self._make_client(),
        )
        
        # Should show the establishment
        self.assertIn("LinkedIn Only Bistro", text_body)
        # Should show that Google link is unavailable (in progress of being available)
        self.assertIn("en cours de disponibilité", text_body)
        # Should show LinkedIn link
        self.assertIn("linkedin.com/in/john-smith", text_body)
        # Nouvelle intro avec emoji et total
        self.assertIn("identifié", text_body)
        # HTML should also contain LinkedIn info
        self.assertIn("linkedin.com/in/john-smith", html_body)


if __name__ == "__main__":
    unittest.main()
