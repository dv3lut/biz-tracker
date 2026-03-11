"""Tests unitaires pour l'évaluation de l'âge des fiches Google."""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from app.services.google_business import (
    adjust_listing_status_for_contacts,
    compute_listing_age_status,
    should_assume_recent_listing,
)
from app.services.google_business import google_listing as listing_utils
from app.services.google_business.google_lookup_engine import GoogleLookupEngine
from app.services.google_business.google_business_service import GoogleBusinessService
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
            api_error_hook=lambda operation, _error: calls.append(operation),
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


class GoogleDepartmentFilteringTests(unittest.TestCase):
    def _establishment(self, code_postal: str | None, code_commune: str | None = None):
        return SimpleNamespace(
            code_postal=code_postal,
            code_commune=code_commune,
        )

    def test_filter_establishments_for_departments_keeps_all_when_none(self) -> None:
        est_a = self._establishment("75001")
        est_b = self._establishment("33000")

        result = GoogleBusinessService._filter_establishments_for_departments(
            [est_a, est_b],
            None,
        )

        self.assertEqual(result, [est_a, est_b])

    def test_filter_establishments_for_departments_handles_empty_set(self) -> None:
        est = self._establishment("75001")

        result = GoogleBusinessService._filter_establishments_for_departments([est], set())

        self.assertEqual(result, [])

    def test_filter_establishments_for_departments_filters_by_code(self) -> None:
        est_idf = self._establishment("75001")
        est_naq = self._establishment("33000")

        result = GoogleBusinessService._filter_establishments_for_departments(
            [est_idf, est_naq],
            {"75"},
        )

        self.assertEqual(result, [est_idf])

    def test_filter_establishments_for_departments_handles_corsica_alias(self) -> None:
        est_corse = self._establishment("20000")

        result = GoogleBusinessService._filter_establishments_for_departments(
            [est_corse],
            {"2A"},
        )

        self.assertEqual(result, [est_corse])


class GoogleAdminNotificationTests(unittest.TestCase):
    """Vérifie que l'alerte admin est envoyée une seule fois en fin de run."""

    def test_sends_admin_email_when_google_api_errors_aggregated(self) -> None:
        service = GoogleBusinessService.__new__(GoogleBusinessService)
        service._session = Mock()
        service._google_api_error_summaries = {
            ("find_place", "REQUEST_DENIED", "Plus de crédit"): {
                "operation": "find_place",
                "status": "REQUEST_DENIED",
                "message": "Plus de crédit",
                "count": 3,
            }
        }

        email_service = Mock()
        email_service.is_enabled.return_value = True
        email_service.is_configured.return_value = True

        with patch(
            "app.services.google_business.google_business_service.EmailService",
            return_value=email_service,
        ), patch(
            "app.services.google_business.google_business_service.get_admin_emails",
            return_value=["admin@example.com"],
        ):
            run = SimpleNamespace(id="run-1", scope_key="scope-1", started_at=None)
            service._notify_google_api_errors(run)

        email_service.send.assert_called_once()


class GoogleSerializationTests(unittest.TestCase):
    def test_serialize_establishment_returns_expected_payload(self) -> None:
        establishment = SimpleNamespace(
            siret="12345678901234",
            siren="123456789",
            name="Chez Paul",
            naf_code="56.10A",
            code_postal="75001",
            libelle_commune="Paris",
            libelle_commune_etranger=None,
            google_check_status="found",
            google_place_id="place-1",
            google_place_url="https://maps.google.com/?cid=1",
        )

        payload = GoogleBusinessService._serialize_establishment(establishment)

        self.assertEqual(payload["siret"], "12345678901234")
        self.assertEqual(payload["siren"], "123456789")
        self.assertEqual(payload["name"], "Chez Paul")
        self.assertEqual(payload["naf_code"], "56.10A")
        self.assertEqual(payload["code_postal"], "75001")
        self.assertEqual(payload["libelle_commune"], "Paris")

    def test_serialize_establishment_stays_aligned_with_lookup_engine(self) -> None:
        establishment = SimpleNamespace(
            siret="12345678901234",
            siren="123456789",
            name="Chez Paul",
            naf_code="56.10A",
            code_postal="75001",
            libelle_commune="Paris",
        )

        service_payload = GoogleBusinessService._serialize_establishment(establishment)
        engine = GoogleLookupEngine.__new__(GoogleLookupEngine)
        engine_payload = GoogleLookupEngine._serialize_establishment(engine, establishment)

        self.assertEqual(service_payload, engine_payload)


class GoogleBacklogCountingTests(unittest.TestCase):
    """Vérifie que les matches backlog sont bien comptés dans les résultats du run."""

    def test_apply_lookup_result_appends_found_even_when_created_run_differs_from_last_run(self) -> None:
        session = Mock()
        session.flush = Mock()
        engine = GoogleLookupEngine(
            session,
            client=Mock(),
            rate_limiter=SimpleNamespace(acquire=lambda: None),
            settings=SimpleNamespace(),
            naf_keyword_map={},
            neutral_google_types={"point_of_interest", "establishment"},
            category_similarity_threshold=0.72,
            api_call_hook=lambda: None,
        )

        establishment = SimpleNamespace(
            siret="12345678901234",
            created_run_id="older-run-id",
            last_run_id="current-run-id",
            google_place_id=None,
            google_place_url=None,
            google_check_status="pending",
            google_last_checked_at=None,
            google_last_found_at=None,
            google_listing_origin_at=None,
            google_listing_origin_source="unknown",
            google_listing_age_status="unknown",
            google_match_confidence=None,
            google_category_match_confidence=None,
            google_contact_phone=None,
            google_contact_email=None,
            google_contact_website=None,
        )

        match = SimpleNamespace(
            place_id="place-1",
            place_url="https://maps.google.com/?cid=1",
            confidence=0.91,
            category_confidence=0.88,
            listing_origin_at=None,
            listing_origin_source="reviews",
            listing_age_status="recent_creation",
            status_override=None,
            contact_phone=None,
            contact_email=None,
            contact_website=None,
        )

        newly_found: list[object] = []
        now = datetime(2026, 2, 16, 13, 30)

        result = engine.apply_lookup_result(
            establishment,
            match,
            now,
            newly_found=newly_found,
        )

        self.assertIs(result, match)
        self.assertEqual(establishment.google_check_status, "found")
        self.assertEqual(len(newly_found), 1)
        self.assertIs(newly_found[0], establishment)


class GoogleFieldLengthGuardsTests(unittest.TestCase):
    def test_apply_lookup_result_truncates_bounded_google_fields(self) -> None:
        engine = GoogleLookupEngine(
            Mock(),
            client=Mock(),
            rate_limiter=SimpleNamespace(acquire=lambda: None),
            settings=SimpleNamespace(),
            naf_keyword_map={},
            neutral_google_types={"point_of_interest", "establishment"},
            category_similarity_threshold=0.72,
            api_call_hook=lambda: None,
        )
        engine._session.flush = Mock()

        establishment = SimpleNamespace(
            siret="12345678901234",
            google_place_id=None,
            google_place_url=None,
            google_check_status="pending",
            google_last_checked_at=None,
            google_last_found_at=None,
            google_listing_origin_at=None,
            google_listing_origin_source="unknown",
            google_listing_age_status="unknown",
            google_match_confidence=None,
            google_category_match_confidence=None,
            google_contact_phone=None,
            google_contact_email=None,
            google_contact_website=None,
        )

        match = SimpleNamespace(
            place_id="p" * 300,
            place_url="https://example.com/" + ("u" * 900),
            confidence=0.91,
            category_confidence=0.88,
            listing_origin_at=None,
            listing_origin_source="reviews",
            listing_age_status="recent_creation",
            status_override=None,
            contact_phone="+33" + ("1" * 120),
            contact_email=("a" * 300) + "@example.com",
            contact_website="https://site.example/" + ("w" * 900),
        )

        engine.apply_lookup_result(establishment, match, datetime(2026, 3, 12, 1, 0, 0))

        self.assertEqual(len(establishment.google_place_id), 128)
        self.assertEqual(len(establishment.google_place_url), 512)
        self.assertEqual(len(establishment.google_contact_phone), 64)
        self.assertEqual(len(establishment.google_contact_email), 255)
        self.assertEqual(len(establishment.google_contact_website), 512)

    def test_scrape_establishment_website_truncates_all_social_links(self) -> None:
        service = GoogleBusinessService.__new__(GoogleBusinessService)
        service._session = Mock()
        service._session.flush = Mock()

        establishment = SimpleNamespace(
            siret="12345678901234",
            name="Test Biz",
            website_scraped_at=None,
            website_scraped_mobile_phones=None,
            website_scraped_national_phones=None,
            website_scraped_international_phones=None,
            website_scraped_emails=None,
            website_scraped_facebook=None,
            website_scraped_instagram=None,
            website_scraped_twitter=None,
            website_scraped_linkedin=None,
        )

        long_url = "https://social.example/" + ("x" * 900)
        scrape_result = SimpleNamespace(
            mobile_phones_str=None,
            national_phones_str=None,
            international_phones_str=None,
            emails_str=None,
            facebook=long_url,
            instagram=long_url,
            twitter=long_url,
            linkedin=long_url,
            mobile_phones=[],
            national_phones=[],
            international_phones=[],
            emails=[],
            has_data=True,
        )

        with patch(
            "app.services.google_business.google_business_service.scrape_website",
            return_value=scrape_result,
        ), patch(
            "app.services.google_business.google_business_service._persist_scraped_contacts"
        ):
            success = GoogleBusinessService._scrape_establishment_website(
                service,
                establishment,
                "https://example.com",
                datetime(2026, 3, 12, 1, 0, 0),
            )

        self.assertTrue(success)
        self.assertEqual(len(establishment.website_scraped_facebook), 512)
        self.assertEqual(len(establishment.website_scraped_instagram), 512)
        self.assertEqual(len(establishment.website_scraped_twitter), 512)
        self.assertEqual(len(establishment.website_scraped_linkedin), 512)

if __name__ == "__main__":
    unittest.main()
