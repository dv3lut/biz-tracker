from __future__ import annotations

from datetime import date
from unittest import TestCase
from unittest.mock import patch

from app.api.routers.admin.tools_router import (
    debug_annuaire_api,
    fetch_sirene_new_establishments,
    _build_leader_name,
    _enrich_tools_results_from_annuaire,
    _parse_int,
)
from app.api.schemas.tools import SireneNewBusinessesRequest, SireneNewBusinessOut


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

    @patch("app.api.routers.admin.tools_router.log_event")
    @patch("app.api.routers.admin.tools_router.extract_fields")
    @patch("app.api.routers.admin.tools_router.SireneClient")
    @patch("app.api.routers.admin.tools_router.SyncService")
    def test_fetch_new_establishments_filters_by_department(
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
            "header": {"total": "2"},
            "etablissements": [{"dummy": True}, {"dummy": True}],
        }

        mock_extract_fields.side_effect = [
            {
                "siret": "11111111100011",
                "siren": "111111111",
                "nic": "00011",
                "name": "Paris Cafe",
                "naf_code": "5610A",
                "naf_libelle": "Restauration traditionnelle",
                "date_creation": date(2025, 1, 10),
                "categorie_juridique": "1000",
                "code_postal": "75001",
                "libelle_commune": "Paris",
            },
            {
                "siret": "22222222200022",
                "siren": "222222222",
                "nic": "00022",
                "name": "Bordeaux Bar",
                "naf_code": "5610A",
                "naf_libelle": "Restauration traditionnelle",
                "date_creation": date(2025, 1, 10),
                "categorie_juridique": "1000",
                "code_postal": "33000",
                "libelle_commune": "Bordeaux",
            },
        ]

        payload = SireneNewBusinessesRequest(
            start_date=date(2025, 1, 10),
            end_date=None,
            naf_codes=["56.10A"],
            limit=10,
            department_codes=["75"],
        )

        response = fetch_sirene_new_establishments(payload)

        self.assertEqual(response.returned, 1)
        self.assertEqual(response.establishments[0].siret, "11111111100011")
        mock_log_event.assert_called_once()

    @patch("app.api.routers.admin.tools_router.log_event")
    @patch("app.api.routers.admin.tools_router.SireneClient")
    @patch("app.api.routers.admin.tools_router.SyncService")
    def test_fetch_new_establishments_handles_invalid_response(
        self,
        mock_sync_service,
        mock_sirene_client,
        mock_log_event,
    ) -> None:
        mock_service = mock_sync_service.return_value
        mock_service._build_restaurant_query.return_value = "QUERY"

        mock_client = mock_sirene_client.return_value
        mock_client.search_establishments.return_value = "invalid"

        payload = SireneNewBusinessesRequest(
            start_date=date(2025, 1, 10),
            end_date=None,
            naf_codes=["56.10A"],
            limit=10,
        )

        response = fetch_sirene_new_establishments(payload)

        self.assertEqual(response.total, 0)
        self.assertEqual(response.returned, 0)
        self.assertEqual(response.establishments, [])
        mock_log_event.assert_called_once()

    @patch("app.api.routers.admin.tools_router.log_event")
    @patch("app.api.routers.admin.tools_router.SireneClient")
    @patch("app.api.routers.admin.tools_router.SyncService")
    def test_fetch_new_establishments_handles_non_list_payload(
        self,
        mock_sync_service,
        mock_sirene_client,
        mock_log_event,
    ) -> None:
        mock_service = mock_sync_service.return_value
        mock_service._build_restaurant_query.return_value = "QUERY"

        mock_client = mock_sirene_client.return_value
        mock_client.search_establishments.return_value = {
            "header": {"total": "1"},
            "etablissements": "invalid",
        }

        payload = SireneNewBusinessesRequest(
            start_date=date(2025, 1, 10),
            end_date=None,
            naf_codes=["56.10A"],
            limit=10,
        )

        response = fetch_sirene_new_establishments(payload)

        self.assertEqual(response.total, 1)
        self.assertEqual(response.returned, 0)
        self.assertEqual(response.establishments, [])
        mock_log_event.assert_called_once()

    @patch("app.api.routers.admin.tools_router.log_event")
    @patch("app.api.routers.admin.tools_router.extract_fields")
    @patch("app.api.routers.admin.tools_router.SireneClient")
    @patch("app.api.routers.admin.tools_router.SyncService")
    def test_fetch_new_establishments_skips_invalid_items(
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
            "header": {"total": "2"},
            "etablissements": ["invalid", {"dummy": True}, {"dummy": True}],
        }

        mock_extract_fields.side_effect = [
            {
                "siret": None,
                "categorie_juridique": "1000",
            },
            {
                "siret": "33333333300033",
                "categorie_juridique": "1000",
            },
        ]

        payload = SireneNewBusinessesRequest(
            start_date=date(2025, 1, 10),
            end_date=None,
            naf_codes=["56.10A"],
            limit=10,
            department_codes=["75"],
        )

        response = fetch_sirene_new_establishments(payload)

        self.assertEqual(response.returned, 0)
        self.assertEqual(response.establishments, [])
        mock_log_event.assert_called_once()

    @patch("app.api.routers.admin.tools_router.log_event")
    @patch("app.api.routers.admin.tools_router.extract_fields")
    @patch("app.api.routers.admin.tools_router.SireneClient")
    @patch("app.api.routers.admin.tools_router.SyncService")
    def test_fetch_new_establishments_accepts_corsica_alias(
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
            "siret": "44444444400044",
            "siren": "444444444",
            "nic": "00044",
            "name": "Ajaccio",
            "naf_code": "5610A",
            "naf_libelle": "Restauration traditionnelle",
            "date_creation": date(2025, 1, 10),
            "categorie_juridique": "1000",
            "code_postal": "20000",
            "libelle_commune": "Ajaccio",
        }

        payload = SireneNewBusinessesRequest(
            start_date=date(2025, 1, 10),
            end_date=None,
            naf_codes=["56.10A"],
            limit=10,
            department_codes=["2A"],
        )

        response = fetch_sirene_new_establishments(payload)

        self.assertEqual(response.returned, 1)
        self.assertEqual(response.establishments[0].siret, "44444444400044")
        mock_log_event.assert_called_once()


class EnrichToolsResultsTests(TestCase):
    """Tests for _enrich_tools_results_from_annuaire."""

    def _make_establishment(self, siret: str = "12345678900010", siren: str = "123456789") -> SireneNewBusinessOut:
        return SireneNewBusinessOut(
            siret=siret,
            siren=siren,
            nic="00010",
            name="Test",
            naf_code="56.10A",
            naf_libelle="Restauration",
            etat_administratif="A",
            date_creation=date(2025, 1, 1),
            leader_name="Jean Dupont",
            categorie_juridique="5710",
            is_individual=False,
            code_postal="75001",
            libelle_commune="Paris",
        )

    @patch("app.api.routers.admin.tools_router.AnnuaireEntreprisesClient")
    def test_enriches_with_directors_and_legal_name(self, MockClient) -> None:
        from app.clients.annuaire_entreprises_client import AnnuaireResult, DirectorInfo

        instance = MockClient.return_value
        instance.enabled = True
        instance.fetch_batch.return_value = {
            "123456789": AnnuaireResult(
                siren="123456789",
                legal_unit_name="ACME SARL",
                directors=[DirectorInfo("Jean", "DUPONT", 5, 1980, quality="Gérant")],
                success=True,
            ),
        }
        instance.close = lambda: None

        est = self._make_establishment()
        _enrich_tools_results_from_annuaire([est])

        self.assertEqual(est.legal_unit_name, "ACME SARL")
        self.assertEqual(len(est.directors), 1)
        self.assertEqual(est.directors[0].last_name, "DUPONT")
        self.assertEqual(est.directors[0].quality, "Gérant")

    @patch("app.api.routers.admin.tools_router.AnnuaireEntreprisesClient")
    def test_disabled_client_does_nothing(self, MockClient) -> None:
        instance = MockClient.return_value
        instance.enabled = False
        instance.close = lambda: None

        est = self._make_establishment()
        _enrich_tools_results_from_annuaire([est])

        self.assertEqual(est.directors, [])
        self.assertIsNone(est.legal_unit_name)

    @patch("app.api.routers.admin.tools_router.AnnuaireEntreprisesClient")
    def test_no_siren_skips(self, MockClient) -> None:
        instance = MockClient.return_value
        instance.enabled = True
        instance.close = lambda: None

        est = self._make_establishment(siren="")
        _enrich_tools_results_from_annuaire([est])

        instance.fetch_batch.assert_not_called()

    @patch("app.api.routers.admin.tools_router.AnnuaireEntreprisesClient")
    def test_failed_result_ignored(self, MockClient) -> None:
        from app.clients.annuaire_entreprises_client import AnnuaireResult

        instance = MockClient.return_value
        instance.enabled = True
        instance.fetch_batch.return_value = {
            "123456789": AnnuaireResult(
                siren="123456789",
                legal_unit_name=None,
                directors=[],
                success=False,
            ),
        }
        instance.close = lambda: None

        est = self._make_establishment()
        _enrich_tools_results_from_annuaire([est])

        self.assertIsNone(est.legal_unit_name)
        self.assertEqual(est.directors, [])


class AnnuaireDebugRouteTests(TestCase):
    @patch("app.api.routers.admin.tools_router.AnnuaireEntreprisesClient")
    def test_debug_annuaire_returns_payload(self, MockClient) -> None:
        instance = MockClient.return_value
        instance.enabled = True
        instance.fetch_debug.return_value = {
            "siret": "12345678901234",
            "siren": "123456789",
            "success": True,
            "status_code": 200,
            "duration_ms": 12.5,
            "error": None,
            "payload": {"results": []},
        }

        response = debug_annuaire_api("12345678901234")

        self.assertTrue(response.success)
        self.assertEqual(response.siret, "12345678901234")
        self.assertEqual(response.siren, "123456789")
        self.assertEqual(response.status_code, 200)
        instance.close.assert_called_once()

    @patch("app.api.routers.admin.tools_router.AnnuaireEntreprisesClient")
    def test_debug_annuaire_disabled(self, MockClient) -> None:
        instance = MockClient.return_value
        instance.enabled = False

        response = debug_annuaire_api("12345678901234")

        self.assertFalse(response.success)
        self.assertEqual(response.error, "annuaire disabled")
        instance.close.assert_called_once()
