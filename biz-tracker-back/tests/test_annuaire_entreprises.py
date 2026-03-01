"""Tests for the annuaire-entreprises client and enrichment."""
from __future__ import annotations

from unittest.mock import MagicMock, patch, PropertyMock
import json

import pytest

from app.clients.annuaire_entreprises_client import (
    AnnuaireEntreprisesClient,
    AnnuaireResult,
    DirectorInfo,
    _extract_directors,
    _parse_birth_date,
)
from app.services.sync.annuaire_enrichment import (
    _apply_annuaire_result,
    enrich_establishments_from_annuaire,
)


# ---------------------------------------------------------------------------
# _parse_birth_date
# ---------------------------------------------------------------------------

class TestParseBirthDate:
    def test_full_date(self):
        month, year = _parse_birth_date("1975-10")
        assert month == 10
        assert year == 1975

    def test_year_only(self):
        month, year = _parse_birth_date("1981")
        assert month is None
        assert year == 1981

    def test_none(self):
        month, year = _parse_birth_date(None)
        assert month is None
        assert year is None

    def test_empty_string(self):
        month, year = _parse_birth_date("")
        assert month is None
        assert year is None

    def test_invalid(self):
        month, year = _parse_birth_date("abc-xy")
        assert month is None
        assert year is None


# ---------------------------------------------------------------------------
# _extract_directors
# ---------------------------------------------------------------------------

class TestExtractDirectors:
    def test_extracts_all_directors(self):
        dirigeants = [
            {
                "siren": "123456789",
                "denomination": "SOME CORP",
                "qualite": "Commissaire",
                "type_dirigeant": "personne morale",
            },
            {
                "nom": "BARBET",
                "prenoms": "Cédric",
                "date_de_naissance": "1981-12",
                "qualite": "Gérant",
                "type_dirigeant": "personne physique",
            },
            {
                "nom": "DUPONT",
                "prenoms": "Jean",
                "date_de_naissance": "1990-01",
                "qualite": "Directeur",
                "type_dirigeant": "personne physique",
            },
        ]
        directors = _extract_directors(dirigeants)
        assert len(directors) == 3
        # First: personne morale
        assert directors[0].type_dirigeant == "personne morale"
        assert directors[0].denomination == "SOME CORP"
        assert directors[0].quality == "Commissaire"
        assert directors[0].siren == "123456789"
        # Second: BARBET
        assert directors[1].last_name == "BARBET"
        assert directors[1].first_names == "Cédric"
        assert directors[1].birth_month == 12
        assert directors[1].birth_year == 1981
        assert directors[1].quality == "Gérant"
        assert directors[1].type_dirigeant == "personne physique"
        # Third: DUPONT
        assert directors[2].last_name == "DUPONT"
        assert directors[2].first_names == "Jean"
        assert directors[2].quality == "Directeur"

    def test_no_physical_person(self):
        dirigeants = [
            {
                "siren": "123456789",
                "denomination": "SOME CORP",
                "qualite": "Commissaire",
                "type_dirigeant": "personne morale",
            },
        ]
        directors = _extract_directors(dirigeants)
        assert len(directors) == 1
        assert directors[0].type_dirigeant == "personne morale"

    def test_empty_list(self):
        assert _extract_directors([]) == []

    def test_multiple_first_names(self):
        dirigeants = [
            {
                "nom": "LANFRANCHI",
                "prenoms": "Lisandru, Petru, Maria",
                "date_de_naissance": "2005-09",
                "qualite": "Gérant",
                "type_dirigeant": "personne physique",
            },
        ]
        directors = _extract_directors(dirigeants)
        assert len(directors) == 1
        assert directors[0].first_names == "Lisandru, Petru, Maria"
        assert directors[0].last_name == "LANFRANCHI"
        assert directors[0].birth_month == 9
        assert directors[0].birth_year == 2005

    def test_nationality_included(self):
        dirigeants = [
            {
                "nom": "MULLER",
                "prenoms": "Hans",
                "date_de_naissance": "1970-03",
                "qualite": "Président",
                "type_dirigeant": "personne physique",
                "nationalite": "Allemande",
            },
        ]
        directors = _extract_directors(dirigeants)
        assert len(directors) == 1
        assert directors[0].nationality == "Allemande"


# ---------------------------------------------------------------------------
# AnnuaireEntreprisesClient._parse_response
# ---------------------------------------------------------------------------

class TestParseResponse:
    def _make_client(self):
        with patch("app.clients.annuaire_entreprises_client.get_settings") as mock_settings:
            annuaire_cfg = MagicMock()
            annuaire_cfg.api_base_url = "https://test.example.com"
            annuaire_cfg.request_timeout_seconds = 5
            annuaire_cfg.max_retries = 2
            annuaire_cfg.backoff_factor = 0.1
            annuaire_cfg.max_workers = 2
            annuaire_cfg.max_calls_per_second = 7
            annuaire_cfg.enabled = True
            mock_settings.return_value.annuaire = annuaire_cfg
            return AnnuaireEntreprisesClient()

    def test_valid_response_with_director(self):
        client = self._make_client()
        payload = {
            "results": [
                {
                    "siren": "443061841",
                    "nom_complet": "GOOGLE FRANCE",
                    "nom_raison_sociale": "GOOGLE FRANCE",
                    "dirigeants": [
                        {
                            "nom": "MANICLE",
                            "prenoms": "PAUL",
                            "date_de_naissance": "1975-10",
                            "qualite": "Gérant",
                            "type_dirigeant": "personne physique",
                        },
                    ],
                }
            ]
        }
        response = MagicMock()
        response.json.return_value = payload
        result = client._parse_response("443061841", response)
        assert result.success is True
        assert result.legal_unit_name == "GOOGLE FRANCE"
        assert len(result.directors) == 1
        assert result.directors[0].last_name == "MANICLE"
        assert result.directors[0].first_names == "PAUL"
        assert result.directors[0].birth_month == 10
        assert result.directors[0].birth_year == 1975
        assert result.directors[0].quality == "Gérant"

    def test_empty_results(self):
        client = self._make_client()
        response = MagicMock()
        response.json.return_value = {"results": []}
        result = client._parse_response("000000000", response)
        assert result.success is True
        assert result.legal_unit_name is None
        assert result.directors == []

    def test_no_dirigeants(self):
        client = self._make_client()
        payload = {
            "results": [
                {
                    "siren": "100863844",
                    "nom_complet": "CAFFE LANFRANCHI",
                    "dirigeants": [],
                }
            ]
        }
        response = MagicMock()
        response.json.return_value = payload
        result = client._parse_response("100863844", response)
        assert result.success is True
        assert result.legal_unit_name == "CAFFE LANFRANCHI"
        assert result.directors == []

    def test_invalid_json(self):
        client = self._make_client()
        response = MagicMock()
        response.json.side_effect = ValueError("bad json")
        result = client._parse_response("123456789", response)
        assert result.success is False
        assert "invalid JSON" in result.error


# ---------------------------------------------------------------------------
# AnnuaireEntreprisesClient.fetch_siren (with mocked HTTP)
# ---------------------------------------------------------------------------

class TestFetchSiren:
    def _make_client(self):
        with patch("app.clients.annuaire_entreprises_client.get_settings") as mock_settings:
            annuaire_cfg = MagicMock()
            annuaire_cfg.api_base_url = "https://test.example.com"
            annuaire_cfg.request_timeout_seconds = 5
            annuaire_cfg.max_retries = 2
            annuaire_cfg.backoff_factor = 0.01
            annuaire_cfg.max_workers = 2
            annuaire_cfg.max_calls_per_second = 7
            annuaire_cfg.enabled = True
            mock_settings.return_value.annuaire = annuaire_cfg
            return AnnuaireEntreprisesClient()

    @patch("app.clients.annuaire_entreprises_client.log_event")
    def test_success(self, mock_log):
        client = self._make_client()
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "results": [
                {
                    "siren": "552032534",
                    "nom_complet": "DANONE",
                    "dirigeants": [
                        {
                            "nom": "DUPONT",
                            "prenoms": "JEAN",
                            "date_de_naissance": "1970-05",
                            "qualite": "DG",
                            "type_dirigeant": "personne physique",
                        }
                    ],
                }
            ]
        }
        client._session = MagicMock()
        client._session.get.return_value = response

        result = client.fetch_siren("552032534")
        assert result.success is True
        assert result.legal_unit_name == "DANONE"
        assert len(result.directors) == 1
        assert result.directors[0].last_name == "DUPONT"

    @patch("app.clients.annuaire_entreprises_client.log_event")
    def test_retry_on_500(self, mock_log):
        client = self._make_client()
        fail_response = MagicMock()
        fail_response.status_code = 500
        fail_response.headers = {}

        ok_response = MagicMock()
        ok_response.status_code = 200
        ok_response.json.return_value = {
            "results": [{"siren": "111111111", "nom_complet": "TEST", "dirigeants": []}]
        }

        client._session = MagicMock()
        client._session.get.side_effect = [fail_response, ok_response]

        result = client.fetch_siren("111111111")
        assert result.success is True
        assert result.legal_unit_name == "TEST"
        assert client._session.get.call_count == 2

    @patch("app.clients.annuaire_entreprises_client.log_event")
    def test_non_retryable_error(self, mock_log):
        client = self._make_client()
        response = MagicMock()
        response.status_code = 403
        response.headers = {}

        client._session = MagicMock()
        client._session.get.return_value = response

        result = client.fetch_siren("999999999")
        assert result.success is False
        assert "403" in result.error
        assert client._session.get.call_count == 1


# ---------------------------------------------------------------------------
# fetch_batch (parallel execution)
# ---------------------------------------------------------------------------

class TestFetchBatch:
    @patch("app.clients.annuaire_entreprises_client.log_event")
    def test_batch_deduplicates_sirens(self, mock_log):
        with patch("app.clients.annuaire_entreprises_client.get_settings") as mock_settings:
            annuaire_cfg = MagicMock()
            annuaire_cfg.api_base_url = "https://test.example.com"
            annuaire_cfg.request_timeout_seconds = 5
            annuaire_cfg.max_retries = 1
            annuaire_cfg.backoff_factor = 0.01
            annuaire_cfg.max_workers = 2
            annuaire_cfg.max_calls_per_second = 7
            annuaire_cfg.enabled = True
            mock_settings.return_value.annuaire = annuaire_cfg
            client = AnnuaireEntreprisesClient()

        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "results": [{"siren": "111111111", "nom_complet": "ACME", "dirigeants": []}]
        }
        client._session = MagicMock()
        client._session.get.return_value = response

        results = client.fetch_batch(["111111111", "111111111", "111111111"])
        assert len(results) == 1
        assert "111111111" in results

    @patch("app.clients.annuaire_entreprises_client.log_event")
    def test_batch_empty(self, mock_log):
        with patch("app.clients.annuaire_entreprises_client.get_settings") as mock_settings:
            annuaire_cfg = MagicMock()
            annuaire_cfg.api_base_url = "https://test.example.com"
            annuaire_cfg.request_timeout_seconds = 5
            annuaire_cfg.max_retries = 1
            annuaire_cfg.backoff_factor = 0.01
            annuaire_cfg.max_workers = 2
            annuaire_cfg.max_calls_per_second = 7
            annuaire_cfg.enabled = True
            mock_settings.return_value.annuaire = annuaire_cfg
            client = AnnuaireEntreprisesClient()

        results = client.fetch_batch([])
        assert results == {}


# ---------------------------------------------------------------------------
# _apply_annuaire_result
# ---------------------------------------------------------------------------

class TestApplyAnnuaireResult:
    def test_applies_all_fields(self):
        class FakeEstablishment:
            siret = "12345678901234"
            legal_unit_name = None
            directors = []
        est = FakeEstablishment()
        session = MagicMock()
        result = AnnuaireResult(
            siren="123456789",
            legal_unit_name="SOME COMPANY",
            directors=[
                DirectorInfo(
                    first_names="Jean, Pierre",
                    last_name="DUPONT",
                    birth_month=3,
                    birth_year=1985,
                    quality="Gérant",
                    type_dirigeant="personne physique",
                ),
                DirectorInfo(
                    first_names=None,
                    last_name=None,
                    birth_month=None,
                    birth_year=None,
                    quality="Commissaire",
                    type_dirigeant="personne morale",
                    siren="999888777",
                    denomination="HOLDING SA",
                ),
            ],
            success=True,
        )
        with patch("app.services.sync.annuaire_enrichment.models") as mock_models:
            mock_models.Director = MagicMock()
            mock_models.Director.side_effect = lambda **kwargs: MagicMock(**kwargs)
            _apply_annuaire_result(session, est, result)
        assert est.legal_unit_name == "SOME COMPANY"
        assert len(est.directors) == 2

    def test_no_directors(self):
        """When directors is empty, the directors list should be cleared."""
        class FakeEstablishment:
            siret = "12345678901234"
            legal_unit_name = None
            directors = [MagicMock()]  # pre-existing director
        est = FakeEstablishment()
        session = MagicMock()
        result = AnnuaireResult(
            siren="123456789",
            legal_unit_name="SOLO CORP",
            directors=[],
            success=True,
        )
        _apply_annuaire_result(session, est, result)
        assert est.legal_unit_name == "SOLO CORP"
        assert len(est.directors) == 0

    def test_no_legal_name(self):
        class FakeEstablishment:
            siret = "12345678901234"
            legal_unit_name = "ORIGINAL"
            directors = []
        est = FakeEstablishment()
        session = MagicMock()
        result = AnnuaireResult(
            siren="123456789",
            legal_unit_name=None,
            directors=[
                DirectorInfo(
                    first_names="Alice",
                    last_name="MARTIN",
                    birth_month=7,
                    birth_year=1992,
                    quality="Gérante",
                    type_dirigeant="personne physique",
                ),
            ],
            success=True,
        )
        with patch("app.services.sync.annuaire_enrichment.models") as mock_models:
            mock_models.Director = MagicMock()
            mock_models.Director.side_effect = lambda **kwargs: MagicMock(**kwargs)
            _apply_annuaire_result(session, est, result)
        # legal_unit_name should not be overwritten when None
        assert est.legal_unit_name == "ORIGINAL"
        assert len(est.directors) == 1


# ---------------------------------------------------------------------------
# enrich_establishments_from_annuaire (integration-level)
# ---------------------------------------------------------------------------

class TestEnrichEstablishments:
    @patch("app.services.sync.annuaire_enrichment.AnnuaireEntreprisesClient")
    @patch("app.services.sync.annuaire_enrichment.log_event")
    def test_disabled(self, mock_log, MockClient):
        instance = MockClient.return_value
        instance.enabled = False
        session = MagicMock()
        result = enrich_establishments_from_annuaire(session, [MagicMock()])
        assert result["skipped"] is True

    @patch("app.services.sync.annuaire_enrichment.AnnuaireEntreprisesClient")
    @patch("app.services.sync.annuaire_enrichment.log_event")
    def test_empty_establishments(self, mock_log, MockClient):
        instance = MockClient.return_value
        instance.enabled = True
        session = MagicMock()
        result = enrich_establishments_from_annuaire(session, [])
        assert result["skipped"] is True

    @patch("app.services.sync.annuaire_enrichment.models")
    @patch("app.services.sync.annuaire_enrichment.AnnuaireEntreprisesClient")
    @patch("app.services.sync.annuaire_enrichment.log_event")
    def test_enriches_establishments(self, mock_log, MockClient, mock_models):
        instance = MockClient.return_value
        instance.enabled = True
        instance.fetch_batch.return_value = {
            "111222333": AnnuaireResult(
                siren="111222333",
                legal_unit_name="ACME CORP",
                directors=[DirectorInfo("Jean", "DUPONT", 5, 1980, quality="Gérant")],
                success=True,
            ),
        }
        instance.close = MagicMock()
        mock_models.Director = MagicMock()
        mock_models.Director.side_effect = lambda **kwargs: MagicMock(**kwargs)

        est = MagicMock()
        est.siren = "111222333"
        est.directors = []
        session = MagicMock()

        result = enrich_establishments_from_annuaire(session, [est])
        assert result["enriched_count"] == 1
        assert result["director_found_count"] == 1
        assert result["legal_name_found_count"] == 1
        assert est.legal_unit_name == "ACME CORP"
        assert len(est.directors) == 1
        session.flush.assert_called_once()
        instance.close.assert_called_once()

    @patch("app.services.sync.annuaire_enrichment.models")
    @patch("app.services.sync.annuaire_enrichment.AnnuaireEntreprisesClient")
    @patch("app.services.sync.annuaire_enrichment.log_event")
    def test_multiple_establishments_same_siren(self, mock_log, MockClient, mock_models):
        instance = MockClient.return_value
        instance.enabled = True
        instance.fetch_batch.return_value = {
            "111222333": AnnuaireResult(
                siren="111222333",
                legal_unit_name="SHARED CORP",
                directors=[DirectorInfo("Alice", "MARTIN", 1, 1990, quality="Gérante")],
                success=True,
            ),
        }
        instance.close = MagicMock()
        mock_models.Director = MagicMock()
        mock_models.Director.side_effect = lambda **kwargs: MagicMock(**kwargs)

        est1 = MagicMock()
        est1.siren = "111222333"
        est1.directors = []
        est2 = MagicMock()
        est2.siren = "111222333"
        est2.directors = []
        session = MagicMock()

        result = enrich_establishments_from_annuaire(session, [est1, est2])
        # Both establishments share the same SIREN, both should be enriched
        assert result["enriched_count"] == 2
        assert est1.legal_unit_name == "SHARED CORP"
        assert est2.legal_unit_name == "SHARED CORP"
