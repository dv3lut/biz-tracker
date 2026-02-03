from __future__ import annotations

from datetime import date
from unittest import TestCase
from unittest.mock import patch

from app.api.routers.admin.tools_router import fetch_sirene_new_establishments, _build_leader_name, _parse_int
from app.api.schemas.tools import SireneNewBusinessesRequest


class SireneNewBusinessesSchemaTests(TestCase):
    def test_invalid_naf_code_rejected(self) -> None:
        with self.assertRaises(ValueError):
            SireneNewBusinessesRequest(
                start_date=date(2025, 1, 10),
                end_date=None,
                naf_codes=["INVALID"],
            )

    def test_end_date_before_start_rejected(self) -> None:
        with self.assertRaises(ValueError):
            SireneNewBusinessesRequest(
                start_date=date(2025, 1, 10),
                end_date=date(2025, 1, 9),
                naf_codes=["56.10A"],
            )


class SireneToolsRouteTests(TestCase):
    def test_parse_int_invalid_returns_zero(self) -> None:
        self.assertEqual(_parse_int("invalid"), 0)

    def test_build_leader_name_variants(self) -> None:
        self.assertEqual(_build_leader_name({"prenom_usuel": "Anna", "nom_usage": "Martin"}), "Anna Martin")
        self.assertEqual(_build_leader_name({"prenom1": "Paul"}), "Paul")
        self.assertEqual(_build_leader_name({"nom": "Dupont"}), "Dupont")
        self.assertIsNone(_build_leader_name({}))

    @patch("app.api.routers.admin.tools_router.log_event")
    @patch("app.api.routers.admin.tools_router.extract_fields")
    @patch("app.api.routers.admin.tools_router.SireneClient")
    @patch("app.api.routers.admin.tools_router.SyncService")
    def test_fetch_new_establishments_builds_query_and_maps_results(
        self,
        mock_sync_service,
        mock_sirene_client,
        mock_extract_fields,
        mock_log_event,
    ) -> None:
        mock_service = mock_sync_service.return_value
        mock_service._build_restaurant_query.return_value = "QUERY"

        mock_client = mock_sirene_client.return_value
        mock_client.search_establishments.return_value = {
            "header": {"total": "1"},
            "etablissements": [{"dummy": True}],
        }

        mock_extract_fields.return_value = {
            "siret": "12345678900011",
            "siren": "123456789",
            "nic": "00011",
            "name": "Bistrot du Centre",
            "naf_code": "5610A",
            "naf_libelle": "Restauration traditionnelle",
            "date_creation": date(2025, 1, 10),
            "categorie_juridique": "1000",
            "prenom1": "Jeanne",
            "nom": "Dupont",
            "denomination_unite_legale": "Bistrot du Centre",
            "denomination_usuelle_unite_legale": None,
            "denomination_usuelle_etablissement": "Bistrot du Centre",
            "enseigne1": "Bistrot du Centre",
            "enseigne2": None,
            "enseigne3": None,
            "complement_adresse": None,
            "numero_voie": "12",
            "indice_repetition": None,
            "type_voie": "RUE",
            "libelle_voie": "de la Paix",
            "code_postal": "75002",
            "libelle_commune": "Paris",
            "libelle_commune_etranger": None,
        }

        payload = SireneNewBusinessesRequest(
            start_date=date(2025, 1, 10),
            end_date=None,
            naf_codes=["56.10A"],
            limit=10,
        )

        response = fetch_sirene_new_establishments(payload)

        mock_service._build_restaurant_query.assert_called_once_with(
            payload.naf_codes,
            creation_range=(payload.start_date, payload.start_date),
        )
        mock_client.search_establishments.assert_called_once()
        mock_client.close.assert_called_once()
        mock_log_event.assert_called_once()

        self.assertEqual(response.total, 1)
        self.assertEqual(response.returned, 1)
        self.assertEqual(response.establishments[0].siret, "12345678900011")
        self.assertEqual(response.establishments[0].naf_code, "5610A")
        self.assertTrue(response.establishments[0].is_individual)
        self.assertEqual(response.establishments[0].leader_name, "Jeanne Dupont")

    @patch("app.api.routers.admin.tools_router.log_event")
    @patch("app.api.routers.admin.tools_router.extract_fields")
    @patch("app.api.routers.admin.tools_router.SireneClient")
    @patch("app.api.routers.admin.tools_router.SyncService")
    def test_fetch_new_establishments_defaults_total_when_missing(
        self,
        mock_sync_service,
        mock_sirene_client,
        mock_extract_fields,
        mock_log_event,
    ) -> None:
        mock_service = mock_sync_service.return_value
        mock_service._build_restaurant_query.return_value = "QUERY"

        mock_client = mock_sirene_client.return_value
        mock_client.search_establishments.return_value = {
            "header": {"total": "0"},
            "etablissements": ["invalid", {"dummy": True}],
        }

        mock_extract_fields.return_value = {
            "siret": "99999999900011",
            "siren": "999999999",
            "nic": "00011",
            "name": None,
            "naf_code": "5610A",
            "naf_libelle": "Restauration traditionnelle",
            "date_creation": date(2025, 1, 10),
            "categorie_juridique": "5499",
            "prenom1": "Paul",
            "nom": "Martin",
        }

        payload = SireneNewBusinessesRequest(
            start_date=date(2025, 1, 10),
            end_date=None,
            naf_codes=["56.10A"],
            limit=10,
        )

        response = fetch_sirene_new_establishments(payload)

        self.assertEqual(response.total, 1)
        self.assertEqual(response.returned, 1)
        self.assertFalse(response.establishments[0].is_individual)
        self.assertEqual(response.establishments[0].leader_name, "Paul Martin")
