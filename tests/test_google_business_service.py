"""Tests unitaires pour l'évaluation de l'âge des fiches Google."""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from app.services.google_business_service import GoogleBusinessService


class GoogleListingAgeStatusTests(unittest.TestCase):
    """Couvre les scénarios d'absence d'avis pour la détection de fiche récente."""

    def setUp(self) -> None:
        # On instancie la classe sans __init__ car la méthode testée n'utilise aucun attribut.
        self.service = GoogleBusinessService.__new__(GoogleBusinessService)

    def test_assumes_recent_when_reviews_empty(self) -> None:
        details = {"reviews": []}

        self.assertTrue(self.service._should_assume_recent_listing(details))

    def test_assumes_recent_when_reviews_missing_and_no_ratings(self) -> None:
        details = {}

        self.assertTrue(self.service._should_assume_recent_listing(details))

    def test_does_not_assume_recent_when_ratings_positive(self) -> None:
        details = {"user_ratings_total": 5}

        self.assertFalse(self.service._should_assume_recent_listing(details))

    def test_assumes_recent_when_ratings_zero(self) -> None:
        details = {"user_ratings_total": 0}

        self.assertTrue(self.service._should_assume_recent_listing(details))

    def test_recent_status_when_reviews_are_fresh(self) -> None:
        now = datetime(2024, 1, 15, 12, 0, 0)
        review_dates = [now - timedelta(days=3)]

        status = self.service._compute_listing_age_status(
            review_dates,
            ratings_total=None,
            assumed_recent=False,
            now=now,
        )

        self.assertEqual(status, "recent_creation")

    def test_not_recent_status_when_reviews_are_old(self) -> None:
        now = datetime(2024, 1, 15, 12, 0, 0)
        review_dates = [now - timedelta(days=30)]

        status = self.service._compute_listing_age_status(
            review_dates,
            ratings_total=None,
            assumed_recent=False,
            now=now,
        )

        self.assertEqual(status, "not_recent_creation")

    def test_not_recent_status_when_only_positive_ratings(self) -> None:
        now = datetime(2024, 1, 15, 12, 0, 0)

        status = self.service._compute_listing_age_status(
            [],
            ratings_total=15,
            assumed_recent=False,
            now=now,
        )

        self.assertEqual(status, "not_recent_creation")


class GoogleCategoryMatchingTests(unittest.TestCase):
    """Vérifie que la comparaison de catégories reste générique et fiable."""

    def setUp(self) -> None:
        self.service = GoogleBusinessService.__new__(GoogleBusinessService)
        self.service._category_similarity_threshold = 0.72
        self.service._neutral_google_types = {"point_of_interest", "establishment", "store", "food"}

    def test_rejects_unrelated_google_categories(self) -> None:
        keywords = {"restaurant", "restauration"}
        google_types = ["beauty_salon", "point_of_interest", "establishment"]

        match, similarity = self.service._matches_expected_google_category(google_types, keywords)

        self.assertFalse(match)
        self.assertLess(similarity or 0, 0.72)

    def test_accepts_close_google_categories(self) -> None:
        keywords = {"restauration"}
        google_types = ["restaurant", "food"]

        match, similarity = self.service._matches_expected_google_category(google_types, keywords)

        self.assertTrue(match)
        self.assertGreaterEqual(similarity or 0, 0.72)


class GoogleConfidenceScoringTests(unittest.TestCase):
    """Couvre les variations d'adresse dans le calcul de confiance d'une fiche."""

    def setUp(self) -> None:
        self.service = GoogleBusinessService.__new__(GoogleBusinessService)

    def _establishment(self, **overrides: object) -> SimpleNamespace:
        defaults: dict[str, object] = {
            "name": "Le Bistro Parisien",
            "code_postal": "75001",
            "libelle_commune": "Paris",
            "libelle_commune_etranger": None,
        }
        defaults.update(overrides)
        return SimpleNamespace(**defaults)

    def test_penalizes_city_mismatch_even_with_same_name(self) -> None:
        establishment = self._establishment()
        score = self.service._compute_confidence(
            establishment,
            "Le Bistro Parisien",
            "45 Rue de Marseille 69002 Lyon",
        )

        self.assertLess(score, 0.6)

    def test_rewards_when_name_and_locality_align(self) -> None:
        establishment = self._establishment()
        score = self.service._compute_confidence(
            establishment,
            "Le Bistro Parisien",
            "12 Rue du Louvre 75001 Paris",
        )

        self.assertGreater(score, 0.85)


class GoogleConfidencePersistenceTests(unittest.TestCase):
    """S'assure que les confiances sont stockées même sans correspondance finale."""

    def setUp(self) -> None:
        self.service = GoogleBusinessService.__new__(GoogleBusinessService)
        self.service._session = Mock()
        self.service._session.flush = Mock()
        self.service._rate_limiter = SimpleNamespace(acquire=lambda: None)
        self.service._record_api_call = lambda: None
        self.service._naf_keyword_map = {}
        self.service._category_similarity_threshold = 0.72
        self.service._neutral_google_types = {"point_of_interest", "establishment", "store", "food"}
        self.service._resolve_expected_keywords = lambda est: {"restaurant"}

    def _establishment(self) -> SimpleNamespace:
        return SimpleNamespace(
            siret="12345678901234",
            name="Chez Paul",
            libelle_commune="Paris",
            libelle_commune_etranger=None,
            code_postal="75001",
            google_place_url=None,
            google_check_status="pending",
            google_last_checked_at=None,
            google_match_confidence=None,
            google_category_match_confidence=None,
            naf_libelle="Restauration",
            naf_code=None,
        )

    def test_persists_name_confidence_even_below_threshold(self) -> None:
        establishment = self._establishment()

        class DummyClient:
            def find_place(self, query: str, fields: str) -> list[dict[str, object]]:
                return [
                    {"place_id": "place1", "name": "Chez Paul Bistro", "formatted_address": "Paris"},
                ]

        self.service._client = DummyClient()
        self.service._settings = SimpleNamespace(min_match_confidence=0.95)
        self.service._compute_confidence = lambda est, name, addr: 0.6

        def _should_not_fetch(place_id: str) -> None:
            raise AssertionError("Les détails ne devraient pas être consultés en dessous du seuil")

        self.service._fetch_details = _should_not_fetch

        result = self.service._lookup(establishment, now=datetime(2024, 1, 1))

        self.assertIsNone(result)
        self.assertAlmostEqual(establishment.google_match_confidence or 0, 0.6)
        self.assertIsNone(establishment.google_category_match_confidence)

    def test_persists_category_confidence_on_type_mismatch(self) -> None:
        establishment = self._establishment()

        class DummyClient:
            def find_place(self, query: str, fields: str) -> list[dict[str, object]]:
                return [{"place_id": "place1", "name": "Chez Paul", "formatted_address": "Paris"}]

            def get_place_details(self, place_id: str, fields: str) -> dict[str, object]:
                return {
                    "types": ["beauty_salon"],
                    "url": "https://maps.google.com/?cid=123",
                    "reviews": [],
                    "user_ratings_total": 0,
                }

        self.service._client = DummyClient()
        self.service._settings = SimpleNamespace(min_match_confidence=0.5)
        self.service._compute_confidence = lambda est, name, addr: 0.92
        self.service._matches_expected_google_category = lambda types, keywords: (False, 0.81)

        now = datetime(2024, 1, 1)
        result = self.service._lookup(establishment, now=now)

        self.assertIsNotNone(result)
        assert result is not None  # For type checkers
        self.assertEqual(result.status_override, "type_mismatch")

        self.service._apply_lookup_result(establishment, result, now)

        self.assertEqual(establishment.google_check_status, "type_mismatch")
        self.assertAlmostEqual(establishment.google_match_confidence or 0, 0.92)
        self.assertAlmostEqual(establishment.google_category_match_confidence or 0, 0.81)
        self.assertEqual(establishment.google_place_id, "place1")
        self.assertEqual(establishment.google_place_url, "https://maps.google.com/?cid=123")
        self.assertEqual(establishment.google_listing_age_status, "recent_creation")


if __name__ == "__main__":
    unittest.main()
