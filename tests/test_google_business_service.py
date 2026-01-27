"""Tests unitaires pour l'évaluation de l'âge des fiches Google."""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from app.services.google_business import (
    adjust_listing_status_for_contacts,
    compute_listing_age_status,
    should_assume_recent_listing,
)
from app.services.google_business import listing as listing_utils
from app.services.google_business.lookup_engine import GoogleLookupEngine
from app.services.google_business_service import GoogleBusinessService
from app.clients.google_places_client import GooglePlacesError


class GoogleListingAgeStatusTests(unittest.TestCase):
    """Couvre les scénarios d'absence d'avis pour la détection de fiche récente."""

    def test_assumes_recent_when_reviews_empty(self) -> None:
        details = {"reviews": []}

        self.assertTrue(should_assume_recent_listing(details))

    def test_assumes_recent_when_reviews_missing_and_no_ratings(self) -> None:
        details = {}

        self.assertTrue(should_assume_recent_listing(details))

    def test_does_not_assume_recent_when_ratings_positive(self) -> None:
        details = {"user_ratings_total": 5}

        self.assertFalse(should_assume_recent_listing(details))

    def test_assumes_recent_when_ratings_zero(self) -> None:
        details = {"user_ratings_total": 0}

        self.assertTrue(should_assume_recent_listing(details))

    def test_recent_status_when_reviews_are_fresh(self) -> None:
        now = datetime(2024, 1, 15, 12, 0, 0)
        review_dates = [now - timedelta(days=3)]

        status = compute_listing_age_status(
            review_dates,
            ratings_total=None,
            assumed_recent=False,
            now=now,
        )

        self.assertEqual(status, "recent_creation")

    def test_recent_listing_without_contacts_is_flagged(self) -> None:
        adjusted = adjust_listing_status_for_contacts(
            "recent_creation",
            contact_phone=None,
            contact_email=None,
            contact_website=None,
        )

        self.assertEqual(adjusted, "recent_creation_missing_contact")

    def test_recent_listing_with_contacts_keeps_status(self) -> None:
        adjusted = adjust_listing_status_for_contacts(
            "recent_creation",
            contact_phone="+33102030405",
            contact_email=None,
            contact_website=None,
        )

        self.assertEqual(adjusted, "recent_creation")

    def test_not_recent_status_when_reviews_are_old(self) -> None:
        now = datetime(2024, 1, 15, 12, 0, 0)
        review_dates = [now - timedelta(days=30)]

        status = compute_listing_age_status(
            review_dates,
            ratings_total=None,
            assumed_recent=False,
            now=now,
        )

        self.assertEqual(status, "not_recent_creation")

    def test_not_recent_status_when_only_positive_ratings(self) -> None:
        now = datetime(2024, 1, 15, 12, 0, 0)

        status = compute_listing_age_status(
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


class GoogleConfidencePersistenceTests(unittest.TestCase):
    """S'assure que les confiances sont stockées même sans correspondance finale."""

    def setUp(self) -> None:
        self.session = Mock()
        self.session.flush = Mock()
        self.rate_limiter = SimpleNamespace(acquire=lambda: None)
        self.neutral_google_types = {"point_of_interest", "establishment", "store", "food"}

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

    def _make_engine(
        self,
        client: object,
        *,
        category_matcher=None,
        api_error_hook=None,
    ) -> GoogleLookupEngine:
        settings = SimpleNamespace()
        return GoogleLookupEngine(
            self.session,
            client,  # type: ignore[arg-type]
            self.rate_limiter,  # type: ignore[arg-type]
            settings,
            naf_keyword_map={},
            neutral_google_types=self.neutral_google_types,
            category_similarity_threshold=0.72,
            api_call_hook=lambda: None,
            api_error_hook=api_error_hook,
            category_matcher=category_matcher,
        )

    def test_persists_name_confidence_even_below_threshold(self) -> None:
        establishment = self._establishment()

        class DummyClient:
            def find_place(self, query: str, fields: str) -> list[dict[str, object]]:
                return [
                    {"place_id": "place1", "name": "Chez Paul Bistro", "formatted_address": "Paris"},
                ]

            def get_place_details(self, place_id: str, fields: str) -> dict[str, object]:
                raise AssertionError("Les détails ne devraient pas être consultés en dessous du seuil")

        engine = self._make_engine(
            DummyClient(),
            category_matcher=lambda types, keywords: (True, 1.0),
        )

        result = engine.lookup(establishment, now=datetime(2024, 1, 1))

        self.assertIsNone(result)
        # On persiste le meilleur score de matching même en cas de rejet (ex: CP manquant côté Google).
        self.assertGreater(establishment.google_match_confidence or 0, 0.5)
        self.assertIsNone(establishment.google_category_match_confidence)

    def test_records_google_api_error_on_find_place_failure(self) -> None:
        establishment = self._establishment()
        calls: list[str] = []

        class DummyClient:
            def find_place(self, query: str, fields: str) -> list[dict[str, object]]:
                raise GooglePlacesError("REQUEST_DENIED", google_status="REQUEST_DENIED")

        engine = self._make_engine(
            DummyClient(),
            category_matcher=lambda types, keywords: (True, 1.0),
            api_error_hook=calls.append,
        )

        result = engine.lookup(establishment, now=datetime(2024, 1, 1))

        self.assertIsNone(result)
        self.assertIn("find_place", calls)

    def test_persists_category_confidence_on_type_mismatch(self) -> None:
        establishment = self._establishment()

        class DummyClient:
            def find_place(self, query: str, fields: str) -> list[dict[str, object]]:
                return [
                    {
                        "place_id": "place1",
                        "name": "Chez Paul",
                        "formatted_address": "10 Rue du Test 75001 Paris",
                    }
                ]

            def get_place_details(self, place_id: str, fields: str) -> dict[str, object]:
                return {
                    "types": ["beauty_salon"],
                    "url": "https://maps.google.com/?cid=123",
                    "reviews": [],
                    "user_ratings_total": 0,
                    "website": "https://chez-paul.fr",
                }

        engine = self._make_engine(
            DummyClient(),
            category_matcher=lambda types, keywords: (False, 0.81),
        )

        now = datetime(2024, 1, 1)
        result = engine.lookup(establishment, now=now)

        self.assertIsNotNone(result)
        assert result is not None  # For type checkers
        self.assertEqual(result.status_override, "type_mismatch")

        engine.apply_lookup_result(establishment, result, now)

        self.assertEqual(establishment.google_check_status, "type_mismatch")
        self.assertAlmostEqual(establishment.google_match_confidence or 0, 1.0)
        self.assertAlmostEqual(establishment.google_category_match_confidence or 0, 0.81)
        self.assertEqual(establishment.google_place_id, "place1")
        self.assertEqual(establishment.google_place_url, "https://maps.google.com/?cid=123")
        self.assertEqual(establishment.google_listing_age_status, "recent_creation")


class GoogleListingHelpersTests(unittest.TestCase):
    def test_iter_period_dates_and_parsing(self) -> None:
        periods = [
            {"open": {"date": "20240115"}},
            {"open": {"date": "bad"}},
            {},
        ]

        dates = [value for value in listing_utils.iter_period_dates(periods) if value]

        self.assertEqual(len(dates), 1)
        self.assertEqual(dates[0].strftime("%Y-%m-%d"), "2024-01-15")

    def test_collect_review_dates_and_ratings(self) -> None:
        details = {
            "reviews": [
                {"time": 1700001000},
                {"time": "invalid"},
                {"time": 1700000000},
            ],
            "user_ratings_total": 5.0,
        }

        review_dates = listing_utils.collect_review_dates(details)

        self.assertEqual(len(review_dates), 2)
        self.assertLess(review_dates[0], review_dates[1])
        self.assertEqual(listing_utils.extract_ratings_total(details), 5)

    def test_extract_listing_origin_prefers_opening_hours(self) -> None:
        details = {
            "current_opening_hours": {
                "periods": [
                    {"open": {"date": "20240102"}},
                    {"open": {"date": "20240105"}},
                ]
            },
            "reviews": [{"time": 1704153600}],
        }

        origin_at, source, assumed_recent, reviews = listing_utils.extract_listing_origin(details)

        self.assertEqual(origin_at.strftime("%Y-%m-%d"), "2024-01-02")
        self.assertEqual(source, "opening_period")
        self.assertFalse(assumed_recent)
        self.assertEqual(len(reviews), 1)

    def test_extract_listing_origin_handles_recent_assumption(self) -> None:
        details = {"user_ratings_total": 0}

        origin_at, source, assumed_recent, reviews = listing_utils.extract_listing_origin(details)

        self.assertIsNone(origin_at)
        self.assertEqual(source, "assumed_recent")
        self.assertTrue(assumed_recent)
        self.assertEqual(reviews, [])


class ManualGoogleRecheckPersistenceTests(unittest.TestCase):
    def test_manual_recheck_clears_previous_google_listing_when_not_found(self) -> None:
        service = GoogleBusinessService.__new__(GoogleBusinessService)
        service._session = Mock()
        service._session.flush = Mock()
        # Marque le service comme "configuré".
        service._client = object()
        service._rate_limiter = object()

        establishment = SimpleNamespace(
            siret="12345678901234",
            name="Chez Paul",
            libelle_commune="Paris",
            libelle_commune_etranger=None,
            code_postal="75001",
            # État initial: fiche trouvée.
            google_place_id="place-old",
            google_place_url="https://maps.google.com/?cid=old",
            google_check_status="found",
            google_last_checked_at=None,
            google_last_found_at=None,
            google_match_confidence=0.9,
            google_category_match_confidence=0.9,
            google_listing_origin_at=None,
            google_listing_origin_source="google",
            google_listing_age_status="recent_creation",
            google_contact_phone="+33102030405",
            google_contact_email=None,
            google_contact_website=None,
        )

        class FakeEngine:
            def lookup(self, est, *, now=None):
                # Le reset doit avoir été fait avant le lookup.
                assert est.google_place_url is None
                assert est.google_place_id is None
                assert est.google_check_status == "pending"
                return None

            def apply_lookup_result(self, est, result, now, *, newly_found=None):
                est.google_last_checked_at = now
                if not result:
                    if est.google_check_status not in {"found", "type_mismatch"}:
                        est.google_check_status = "not_found"
                    return None
                raise AssertionError("Ce test ne couvre pas le cas found")

        service._lookup_engine = FakeEngine()

        result = GoogleBusinessService.manual_check(service, establishment)  # type: ignore[arg-type]

        self.assertIsNone(result)
        self.assertIsNone(establishment.google_place_url)
        self.assertIsNone(establishment.google_place_id)
        self.assertEqual(establishment.google_check_status, "not_found")

if __name__ == "__main__":
    unittest.main()
