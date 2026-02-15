from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

from app.clients.apify_client import LinkedInProfileResult
from app.services.linkedin.linkedin_lookup_service import (
    LINKEDIN_STATUS_FOUND,
    LINKEDIN_STATUS_INSUFFICIENT,
    LINKEDIN_STATUS_PENDING,
    LinkedInEnrichmentResult,
    LinkedInLookupService,
)


class LinkedInLookupServiceTests(TestCase):
    @patch("app.services.linkedin.linkedin_lookup_service.get_settings")
    def test_enrich_directors_returns_empty_when_disabled(self, mock_get_settings) -> None:
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(
                enabled=False,
                api_token=None,
            )
        )
        session = MagicMock()
        service = LinkedInLookupService(session)

        director = SimpleNamespace(
            id="dir-1",
            is_physical_person=True,
            linkedin_check_status=LINKEDIN_STATUS_PENDING,
        )

        result = service.enrich_directors([director])

        self.assertEqual(result.total_directors, 1)
        self.assertEqual(result.eligible_directors, 0)
        self.assertEqual(result.searched_count, 0)
        self.assertEqual(result.found_count, 0)
        self.assertEqual(result.not_found_count, 0)
        self.assertEqual(result.error_count, 0)

    @patch("app.services.linkedin.linkedin_lookup_service.utcnow")
    @patch("app.services.linkedin.linkedin_lookup_service.ApifyClient")
    @patch("app.services.linkedin.linkedin_lookup_service.get_settings")
    def test_enrich_directors_marks_insufficient_when_missing_names(
        self,
        mock_get_settings,
        mock_client_cls,
        mock_utcnow,
    ) -> None:
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(enabled=True, api_token="token")
        )
        mock_client_cls.return_value = MagicMock()
        now = datetime(2026, 2, 8, tzinfo=timezone.utc)
        mock_utcnow.return_value = now

        session = MagicMock()
        service = LinkedInLookupService(session)

        director = SimpleNamespace(
            id="dir-1",
            is_physical_person=True,
            first_name_for_search=None,
            last_name=None,
            first_names=None,
            linkedin_check_status=LINKEDIN_STATUS_PENDING,
            linkedin_last_checked_at=None,
        )
        establishment = SimpleNamespace(
            siret="000",
            name="Acme",
            enseigne1=None,
            denomination_usuelle_etablissement=None,
            legal_unit_name=None,
            denomination_unite_legale=None,
        )

        result = service.enrich_directors([director], establishment=establishment)

        self.assertEqual(result.total_directors, 1)
        self.assertEqual(result.eligible_directors, 1)
        self.assertEqual(director.linkedin_check_status, LINKEDIN_STATUS_INSUFFICIENT)
        self.assertEqual(director.linkedin_last_checked_at, now)

    @patch("app.services.linkedin.linkedin_lookup_service.utcnow")
    @patch("app.services.linkedin.linkedin_lookup_service.ApifyClient")
    @patch("app.services.linkedin.linkedin_lookup_service.get_settings")
    def test_enrich_directors_retries_with_legal_unit_and_marks_found(
        self,
        mock_get_settings,
        mock_client_cls,
        mock_utcnow,
    ) -> None:
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(enabled=True, api_token="token")
        )
        mock_client = MagicMock()
        mock_client.search_linkedin_profile.side_effect = [
            LinkedInProfileResult(success=True, profile_url=None, profile_data=None),
            LinkedInProfileResult(
                success=True,
                profile_url="https://linkedin.com/in/john",
                profile_data={"title": "CEO"},
            ),
        ]
        mock_client_cls.return_value = mock_client
        now = datetime(2026, 2, 8, tzinfo=timezone.utc)
        mock_utcnow.return_value = now

        session = MagicMock()
        service = LinkedInLookupService(session)

        director = SimpleNamespace(
            id="dir-1",
            is_physical_person=True,
            first_name_for_search="John",
            last_name="Doe",
            first_names=None,
            linkedin_check_status=LINKEDIN_STATUS_PENDING,
            linkedin_last_checked_at=None,
            linkedin_profile_url=None,
            linkedin_profile_data=None,
        )
        establishment = SimpleNamespace(
            siret="000",
            name="Acme Branch Paris",
            enseigne1=None,
            denomination_usuelle_etablissement=None,
            legal_unit_name="Dupont Enterprises",
            denomination_unite_legale=None,
        )

        result = service.enrich_directors([director], establishment=establishment)

        self.assertEqual(result.searched_count, 1)
        self.assertEqual(result.api_call_count, 2)
        self.assertEqual(result.found_count, 1)
        self.assertEqual(director.linkedin_check_status, LINKEDIN_STATUS_FOUND)
        self.assertEqual(director.linkedin_profile_url, "https://linkedin.com/in/john")
        self.assertEqual(director.linkedin_profile_data, {"title": "CEO"})
        session.flush.assert_called_once()

    @patch("app.services.linkedin.linkedin_lookup_service.utcnow")
    @patch("app.services.linkedin.linkedin_lookup_service.ApifyClient")
    @patch("app.services.linkedin.linkedin_lookup_service.get_settings")
    def test_enrich_directors_marks_not_found_when_no_profile(
        self,
        mock_get_settings,
        mock_client_cls,
        mock_utcnow,
    ) -> None:
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(enabled=True, api_token="token")
        )
        mock_client = MagicMock()
        mock_client.search_linkedin_profile.return_value = LinkedInProfileResult(
            success=True,
            profile_url=None,
            profile_data=None,
        )
        mock_client_cls.return_value = mock_client
        now = datetime(2026, 2, 8, tzinfo=timezone.utc)
        mock_utcnow.return_value = now

        session = MagicMock()
        service = LinkedInLookupService(session)

        director = SimpleNamespace(
            id="dir-1",
            is_physical_person=True,
            first_name_for_search="Jane",
            last_name="Doe",
            first_names=None,
            linkedin_check_status=LINKEDIN_STATUS_PENDING,
            linkedin_last_checked_at=None,
        )
        establishment = SimpleNamespace(
            siret="000",
            name="Acme",
            enseigne1=None,
            denomination_usuelle_etablissement=None,
            legal_unit_name=None,
            denomination_unite_legale=None,
        )

        result = service.enrich_directors([director], establishment=establishment)

        self.assertEqual(result.not_found_count, 1)
        self.assertEqual(director.linkedin_check_status, "not_found")
        self.assertEqual(director.linkedin_last_checked_at, now)

    @patch("app.services.linkedin.linkedin_lookup_service.utcnow")
    @patch("app.services.linkedin.linkedin_lookup_service.ApifyClient")
    @patch("app.services.linkedin.linkedin_lookup_service.get_settings")
    def test_enrich_directors_marks_error_on_failed_search(
        self,
        mock_get_settings,
        mock_client_cls,
        mock_utcnow,
    ) -> None:
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(enabled=True, api_token="token")
        )
        mock_client = MagicMock()
        mock_client.search_linkedin_profile.return_value = LinkedInProfileResult(
            success=False,
            profile_url=None,
            error="boom",
        )
        mock_client_cls.return_value = mock_client
        now = datetime(2026, 2, 8, tzinfo=timezone.utc)
        mock_utcnow.return_value = now

        session = MagicMock()
        service = LinkedInLookupService(session)

        director = SimpleNamespace(
            id="dir-1",
            is_physical_person=True,
            first_name_for_search="Jane",
            last_name="Doe",
            first_names=None,
            linkedin_check_status=LINKEDIN_STATUS_PENDING,
            linkedin_last_checked_at=None,
        )
        establishment = SimpleNamespace(
            siret="000",
            name="Acme",
            enseigne1=None,
            denomination_usuelle_etablissement=None,
            legal_unit_name=None,
            denomination_unite_legale=None,
        )

        result = service.enrich_directors([director], establishment=establishment)

        self.assertEqual(result.error_count, 1)
        self.assertEqual(director.linkedin_check_status, "error")
        self.assertEqual(director.linkedin_last_checked_at, now)

    @patch("app.services.linkedin.linkedin_lookup_service.get_settings")
    def test_resolve_company_name_falls_back_to_enseigne(self, mock_get_settings) -> None:
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(enabled=False, api_token=None)
        )
        session = MagicMock()
        service = LinkedInLookupService(session)

        establishment = SimpleNamespace(
            name=None,
            enseigne1="Maison Dupont",
            denomination_usuelle_etablissement=None,
            legal_unit_name=None,
            denomination_unite_legale=None,
        )

        company = service._resolve_company_name(SimpleNamespace(), establishment)

        self.assertEqual(company, "Maison Dupont")

    @patch("app.services.linkedin.linkedin_lookup_service.get_settings")
    def test_enrich_directors_skips_when_no_physical_directors(self, mock_get_settings) -> None:
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(enabled=True, api_token="token")
        )
        session = MagicMock()
        service = LinkedInLookupService(session)

        director = SimpleNamespace(
            id="dir-1",
            is_physical_person=False,
            linkedin_check_status=LINKEDIN_STATUS_PENDING,
        )

        result = service.enrich_directors([director])

        self.assertEqual(result.total_directors, 1)
        self.assertEqual(result.eligible_directors, 0)
        self.assertEqual(result.searched_count, 0)

    @patch("app.services.linkedin.linkedin_lookup_service.get_settings")
    def test_enrich_directors_skips_when_already_checked(self, mock_get_settings) -> None:
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(enabled=True, api_token="token")
        )
        session = MagicMock()
        service = LinkedInLookupService(session)

        director = SimpleNamespace(
            id="dir-1",
            is_physical_person=True,
            linkedin_check_status="found",
        )
        establishment = SimpleNamespace(siret="000")

        result = service.enrich_directors([director], establishment=establishment)

        self.assertEqual(result.total_directors, 1)
        self.assertEqual(result.eligible_directors, 1)
        self.assertEqual(result.searched_count, 0)

    @patch("app.services.linkedin.linkedin_lookup_service.utcnow")
    @patch("app.services.linkedin.linkedin_lookup_service.ApifyClient")
    @patch("app.services.linkedin.linkedin_lookup_service.get_settings")
    def test_enrich_directors_marks_insufficient_when_missing_company(
        self,
        mock_get_settings,
        mock_client_cls,
        mock_utcnow,
    ) -> None:
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(enabled=True, api_token="token")
        )
        mock_client_cls.return_value = MagicMock()
        now = datetime(2026, 2, 8, tzinfo=timezone.utc)
        mock_utcnow.return_value = now

        session = MagicMock()
        service = LinkedInLookupService(session)

        director = SimpleNamespace(
            id="dir-1",
            is_physical_person=True,
            first_name_for_search="Jane",
            last_name="Doe",
            first_names=None,
            linkedin_check_status=LINKEDIN_STATUS_PENDING,
            linkedin_last_checked_at=None,
        )
        establishment = SimpleNamespace(
            siret="000",
            name=None,
            enseigne1=None,
            denomination_usuelle_etablissement=None,
            legal_unit_name=None,
            denomination_unite_legale=None,
        )

        result = service.enrich_directors([director], establishment=establishment)

        self.assertEqual(result.searched_count, 0)
        self.assertEqual(director.linkedin_check_status, LINKEDIN_STATUS_INSUFFICIENT)
        self.assertEqual(director.linkedin_last_checked_at, now)

    @patch("app.services.linkedin.linkedin_lookup_service.get_settings")
    def test_lookup_single_director_delegates(self, mock_get_settings) -> None:
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(enabled=False, api_token=None)
        )
        session = MagicMock()
        service = LinkedInLookupService(session)
        service.enrich_directors = MagicMock()

        establishment = SimpleNamespace(siret="000")
        director = SimpleNamespace(establishment=establishment)

        service.lookup_single_director(director)

        service.enrich_directors.assert_called_once_with(
            [director],
            establishment=establishment,
            force_refresh=True,
        )

    @patch("app.services.linkedin.linkedin_lookup_service.get_settings")
    def test_fetch_pending_directors_returns_results(self, mock_get_settings) -> None:
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(enabled=False, api_token=None)
        )
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = ["director-1"]

        service = LinkedInLookupService(session)

        result = service.fetch_pending_directors(naf_codes=["56.10A"], limit=10)

        self.assertEqual(result, ["director-1"])
        session.execute.assert_called_once()

    @patch("app.services.linkedin.linkedin_lookup_service.get_settings")
    def test_enrich_batch_aggregates_results(self, mock_get_settings) -> None:
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(enabled=True, api_token="test-token")
        )
        session = MagicMock()
        service = LinkedInLookupService(session)

        # Create mock directors
        director1 = MagicMock()
        director1.id = "d1"
        director1.is_physical_person = True
        director1.linkedin_check_status = LINKEDIN_STATUS_PENDING
        director1.first_name = "Jean"
        director1.last_name = "Dupont"

        director2 = MagicMock()
        director2.id = "d2"
        director2.is_physical_person = True
        director2.linkedin_check_status = LINKEDIN_STATUS_PENDING
        director2.first_name = "Marie"
        director2.last_name = "Martin"

        director3 = MagicMock()
        director3.id = "d3"
        director3.is_physical_person = False  # Not a physical person

        # Create mock establishments
        est1 = MagicMock()
        est1.siret = "12345678901234"
        est1.directors = [director1]

        est2 = MagicMock()
        est2.siret = "98765432109876"
        est2.directors = [director2, director3]

        # Mock _search_director_parallel to return search outcomes
        search_outcome_found = {"status": "found", "profile_url": "https://linkedin.com/in/jean", "api_calls": 1}
        search_outcome_not_found = {"status": "not_found", "profile_url": None, "api_calls": 1}

        service._search_director_parallel = MagicMock(side_effect=[search_outcome_found, search_outcome_not_found])

        # Mock _apply_search_result to update total_result
        original_apply = service._apply_search_result

        def mock_apply(director, establishment, outcome, run_id, now, total_result):
            total_result.searched_count += 1
            total_result.api_call_count += outcome.get("api_calls", 0)
            if outcome["status"] == "found":
                total_result.found_count += 1
                total_result.directors_with_profiles.append(str(director.id))
            elif outcome["status"] == "not_found":
                total_result.not_found_count += 1

        service._apply_search_result = MagicMock(side_effect=mock_apply)

        total = service.enrich_batch([est1, est2], run_id=None, force_refresh=False)

        # 3 total directors (1 in est1, 2 in est2)
        self.assertEqual(total.total_directors, 3)
        # 2 eligible (physical persons with pending status)
        self.assertEqual(total.eligible_directors, 2)
        # 2 searched (both eligible directors)
        self.assertEqual(total.searched_count, 2)
        # 1 found
        self.assertEqual(total.found_count, 1)
        # 1 not found
        self.assertEqual(total.not_found_count, 1)
        # 0 errors
        self.assertEqual(total.error_count, 0)
        # 2 API calls
        self.assertEqual(total.api_call_count, 2)
        # 1 director with profile
        self.assertEqual(total.directors_with_profiles, ["d1"])

    @patch("app.services.linkedin.linkedin_lookup_service.utcnow")
    @patch("app.services.linkedin.linkedin_lookup_service.ApifyClient")
    @patch("app.services.linkedin.linkedin_lookup_service.get_settings")
    def test_enrich_directors_marks_insufficient_for_non_diffusible_name(
        self,
        mock_get_settings,
        mock_client_cls,
        mock_utcnow,
    ) -> None:
        """Test that directors with [ND] in their name are skipped."""
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(enabled=True, api_token="token")
        )
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        now = datetime(2026, 2, 8, tzinfo=timezone.utc)
        mock_utcnow.return_value = now

        session = MagicMock()
        service = LinkedInLookupService(session)

        director = SimpleNamespace(
            id="dir-1",
            is_physical_person=True,
            first_name_for_search="[ND]",
            last_name="Dupont",
            first_names="[ND]",
            linkedin_check_status=LINKEDIN_STATUS_PENDING,
            linkedin_last_checked_at=None,
        )
        establishment = SimpleNamespace(
            siret="000",
            name="Acme",
            enseigne1=None,
            denomination_usuelle_etablissement=None,
            legal_unit_name=None,
            denomination_unite_legale=None,
        )

        result = service.enrich_directors([director], establishment=establishment)

        self.assertEqual(result.skipped_nd_count, 1)
        self.assertEqual(result.searched_count, 0)
        self.assertEqual(director.linkedin_check_status, LINKEDIN_STATUS_INSUFFICIENT)
        mock_client.search_linkedin_profile.assert_not_called()

    @patch("app.services.linkedin.linkedin_lookup_service.utcnow")
    @patch("app.services.linkedin.linkedin_lookup_service.ApifyClient")
    @patch("app.services.linkedin.linkedin_lookup_service.get_settings")
    def test_enrich_directors_skips_non_diffusible_company(
        self,
        mock_get_settings,
        mock_client_cls,
        mock_utcnow,
    ) -> None:
        """Test that directors with [ND] in their company name are skipped.

        Note: When all company name candidates are non-diffusible, _resolve_company_name
        returns None, which results in INSUFFICIENT status (no company found).
        """
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(enabled=True, api_token="token")
        )
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        now = datetime(2026, 2, 8, tzinfo=timezone.utc)
        mock_utcnow.return_value = now

        session = MagicMock()
        service = LinkedInLookupService(session)

        director = SimpleNamespace(
            id="dir-1",
            is_physical_person=True,
            first_name_for_search="Jean",
            last_name="Dupont",
            first_names=None,
            linkedin_check_status=LINKEDIN_STATUS_PENDING,
            linkedin_last_checked_at=None,
        )
        establishment = SimpleNamespace(
            siret="000",
            name="[ND] ENTREPRISE NON DIFFUSIBLE",
            enseigne1=None,
            denomination_usuelle_etablissement=None,
            legal_unit_name=None,
            denomination_unite_legale=None,
        )

        result = service.enrich_directors([director], establishment=establishment)

        # When all company names are ND, _resolve_company_name returns None
        # and the director is marked as INSUFFICIENT (no company found)
        self.assertEqual(result.searched_count, 0)
        self.assertEqual(director.linkedin_check_status, LINKEDIN_STATUS_INSUFFICIENT)
        mock_client.search_linkedin_profile.assert_not_called()

    @patch("app.services.linkedin.linkedin_lookup_service.get_settings")
    def test_should_retry_with_legal_unit_returns_false_when_same_name(
        self,
        mock_get_settings,
    ) -> None:
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(enabled=False, api_token=None)
        )
        session = MagicMock()
        service = LinkedInLookupService(session)

        result = service._should_retry_with_legal_unit("Acme Corp", "Acme Corp")
        self.assertFalse(result)

    @patch("app.services.linkedin.linkedin_lookup_service.get_settings")
    def test_should_retry_with_legal_unit_returns_false_when_establishment_in_legal(
        self,
        mock_get_settings,
    ) -> None:
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(enabled=False, api_token=None)
        )
        session = MagicMock()
        service = LinkedInLookupService(session)

        # "Acme" is contained in "Acme Holding Company"
        result = service._should_retry_with_legal_unit("Acme", "Acme Holding Company")
        self.assertFalse(result)

    @patch("app.services.linkedin.linkedin_lookup_service.get_settings")
    def test_should_retry_with_legal_unit_returns_false_when_legal_in_establishment(
        self,
        mock_get_settings,
    ) -> None:
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(enabled=False, api_token=None)
        )
        session = MagicMock()
        service = LinkedInLookupService(session)

        result = service._should_retry_with_legal_unit("MAISON DUPONT - PARIS", "DUPONT")
        self.assertFalse(result)

    @patch("app.services.linkedin.linkedin_lookup_service.get_settings")
    def test_should_retry_with_legal_unit_returns_true_when_names_different(
        self,
        mock_get_settings,
    ) -> None:
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(enabled=False, api_token=None)
        )
        session = MagicMock()
        service = LinkedInLookupService(session)

        result = service._should_retry_with_legal_unit("Acme Branch Paris", "Dupont Enterprises")
        self.assertTrue(result)

    @patch("app.services.linkedin.linkedin_lookup_service.get_settings")
    def test_should_retry_with_legal_unit_returns_false_when_legal_unit_is_nd(
        self,
        mock_get_settings,
    ) -> None:
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(enabled=False, api_token=None)
        )
        session = MagicMock()
        service = LinkedInLookupService(session)

        result = service._should_retry_with_legal_unit("Acme", "[ND] NON DIFFUSIBLE")
        self.assertFalse(result)

    @patch("app.services.linkedin.linkedin_lookup_service.get_settings")
    def test_enrich_batch_returns_early_when_no_directors_to_search(
        self,
        mock_get_settings,
    ) -> None:
        """Test that enrich_batch returns early when all directors are already checked."""
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(enabled=True, api_token="token")
        )
        session = MagicMock()
        service = LinkedInLookupService(session)

        # Director already checked (status is not PENDING)
        director = MagicMock()
        director.is_physical_person = True
        director.linkedin_check_status = "found"  # Already checked

        est = MagicMock()
        est.directors = [director]

        result = service.enrich_batch([est], run_id=None, force_refresh=False)

        self.assertEqual(result.total_directors, 1)
        self.assertEqual(result.eligible_directors, 1)
        self.assertEqual(result.searched_count, 0)

    @patch("app.services.linkedin.linkedin_lookup_service.get_settings")
    def test_enrich_batch_returns_early_when_client_disabled(
        self,
        mock_get_settings,
    ) -> None:
        """Test that enrich_batch returns early when LinkedIn is disabled."""
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(enabled=False, api_token=None)
        )
        session = MagicMock()
        service = LinkedInLookupService(session)

        director = MagicMock()
        director.is_physical_person = True
        director.linkedin_check_status = LINKEDIN_STATUS_PENDING

        est = MagicMock()
        est.directors = [director]

        result = service.enrich_batch([est], run_id=None, force_refresh=False)

        self.assertEqual(result.total_directors, 0)
        self.assertEqual(result.searched_count, 0)

    @patch("app.services.linkedin.linkedin_lookup_service.utcnow")
    @patch("app.services.linkedin.linkedin_lookup_service.ApifyClient")
    @patch("app.services.linkedin.linkedin_lookup_service.get_settings")
    def test_search_director_parallel_marks_insufficient_for_nd_names(
        self,
        mock_get_settings,
        mock_client_cls,
        mock_utcnow,
    ) -> None:
        """Test that _search_director_parallel skips non-diffusible names."""
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(enabled=True, api_token="token")
        )
        mock_client_cls.return_value = MagicMock()
        now = datetime(2026, 2, 8, tzinfo=timezone.utc)
        mock_utcnow.return_value = now

        session = MagicMock()
        service = LinkedInLookupService(session)

        director = SimpleNamespace(
            id="dir-1",
            first_name_for_search="[ND]",
            last_name="Dupont",
            first_names="[ND]",
        )
        establishment = SimpleNamespace(
            siret="000",
        )

        result = service._search_director_parallel(director, establishment, None, now)

        self.assertEqual(result["status"], "insufficient")
        self.assertEqual(result["reason"], "non_diffusible")
        self.assertEqual(result["api_calls"], 0)

    @patch("app.services.linkedin.linkedin_lookup_service.utcnow")
    @patch("app.services.linkedin.linkedin_lookup_service.ApifyClient")
    @patch("app.services.linkedin.linkedin_lookup_service.get_settings")
    def test_search_director_parallel_returns_insufficient_when_missing_name(
        self,
        mock_get_settings,
        mock_client_cls,
        mock_utcnow,
    ) -> None:
        """Test that _search_director_parallel returns insufficient when name is missing."""
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(enabled=True, api_token="token")
        )
        mock_client_cls.return_value = MagicMock()
        now = datetime(2026, 2, 8, tzinfo=timezone.utc)
        mock_utcnow.return_value = now

        session = MagicMock()
        service = LinkedInLookupService(session)

        director = SimpleNamespace(
            id="dir-1",
            first_name_for_search=None,
            last_name="Dupont",
            first_names=None,
        )
        establishment = SimpleNamespace(
            siret="000",
        )

        result = service._search_director_parallel(director, establishment, None, now)

        self.assertEqual(result["status"], "insufficient")

    @patch("app.services.linkedin.linkedin_lookup_service.utcnow")
    @patch("app.services.linkedin.linkedin_lookup_service.ApifyClient")
    @patch("app.services.linkedin.linkedin_lookup_service.get_settings")
    def test_search_director_parallel_returns_insufficient_when_missing_company(
        self,
        mock_get_settings,
        mock_client_cls,
        mock_utcnow,
    ) -> None:
        """Test that _search_director_parallel returns insufficient when company is missing."""
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(enabled=True, api_token="token")
        )
        mock_client_cls.return_value = MagicMock()
        now = datetime(2026, 2, 8, tzinfo=timezone.utc)
        mock_utcnow.return_value = now

        session = MagicMock()
        service = LinkedInLookupService(session)

        director = SimpleNamespace(
            id="dir-1",
            first_name_for_search="Jean",
            last_name="Dupont",
            first_names=None,
        )
        establishment = SimpleNamespace(
            siret="000",
            name=None,
            enseigne1=None,
            denomination_usuelle_etablissement=None,
            legal_unit_name=None,
            denomination_unite_legale=None,
        )

        result = service._search_director_parallel(director, establishment, None, now)

        self.assertEqual(result["status"], "insufficient")
        self.assertEqual(result["reason"], "missing_company")

    @patch("app.services.linkedin.linkedin_lookup_service.utcnow")
    @patch("app.services.linkedin.linkedin_lookup_service.ApifyClient")
    @patch("app.services.linkedin.linkedin_lookup_service.get_settings")
    def test_search_director_parallel_returns_insufficient_for_nd_company(
        self,
        mock_get_settings,
        mock_client_cls,
        mock_utcnow,
    ) -> None:
        """Test that _search_director_parallel skips non-diffusible company names."""
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(enabled=True, api_token="token")
        )
        mock_client_cls.return_value = MagicMock()
        now = datetime(2026, 2, 8, tzinfo=timezone.utc)
        mock_utcnow.return_value = now

        session = MagicMock()
        service = LinkedInLookupService(session)

        # Mock _resolve_company_name to return a ND company
        service._resolve_company_name = MagicMock(return_value="[ND] COMPANY")

        director = SimpleNamespace(
            id="dir-1",
            first_name_for_search="Jean",
            last_name="Dupont",
            first_names=None,
        )
        establishment = SimpleNamespace(
            siret="000",
        )

        result = service._search_director_parallel(director, establishment, None, now)

        self.assertEqual(result["status"], "insufficient")
        self.assertEqual(result["reason"], "non_diffusible_company")

    @patch("app.services.linkedin.linkedin_lookup_service.utcnow")
    @patch("app.services.linkedin.linkedin_lookup_service.ApifyClient")
    @patch("app.services.linkedin.linkedin_lookup_service.get_settings")
    def test_apply_search_result_counts_non_diffusible_insufficient_as_skipped_nd(
        self,
        mock_get_settings,
        mock_client_cls,
        mock_utcnow,
    ) -> None:
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(enabled=True, api_token="token")
        )
        mock_client_cls.return_value = MagicMock()
        now = datetime(2026, 2, 8, tzinfo=timezone.utc)
        mock_utcnow.return_value = now

        session = MagicMock()
        service = LinkedInLookupService(session)

        director = SimpleNamespace(
            id="dir-1",
            linkedin_check_status=LINKEDIN_STATUS_PENDING,
            linkedin_last_checked_at=None,
            linkedin_profile_url=None,
            linkedin_profile_data=None,
        )
        establishment = SimpleNamespace(siret="000")
        aggregated = LinkedInEnrichmentResult()

        service._apply_search_result(
            director,
            establishment,
            {"status": LINKEDIN_STATUS_INSUFFICIENT, "reason": "non_diffusible", "api_calls": 0},
            None,
            now,
            aggregated,
        )

        self.assertEqual(director.linkedin_check_status, LINKEDIN_STATUS_INSUFFICIENT)
        self.assertEqual(aggregated.skipped_nd_count, 1)

    @patch("app.services.linkedin.linkedin_lookup_service.utcnow")
    @patch("app.services.linkedin.linkedin_lookup_service.ApifyClient")
    @patch("app.services.linkedin.linkedin_lookup_service.get_settings")
    def test_apply_search_result_does_not_count_missing_name_insufficient_as_skipped_nd(
        self,
        mock_get_settings,
        mock_client_cls,
        mock_utcnow,
    ) -> None:
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(enabled=True, api_token="token")
        )
        mock_client_cls.return_value = MagicMock()
        now = datetime(2026, 2, 8, tzinfo=timezone.utc)
        mock_utcnow.return_value = now

        session = MagicMock()
        service = LinkedInLookupService(session)

        director = SimpleNamespace(
            id="dir-1",
            linkedin_check_status=LINKEDIN_STATUS_PENDING,
            linkedin_last_checked_at=None,
            linkedin_profile_url=None,
            linkedin_profile_data=None,
        )
        establishment = SimpleNamespace(siret="000")
        aggregated = LinkedInEnrichmentResult()

        service._apply_search_result(
            director,
            establishment,
            {"status": LINKEDIN_STATUS_INSUFFICIENT, "reason": "missing_name", "api_calls": 0},
            None,
            now,
            aggregated,
        )

        self.assertEqual(director.linkedin_check_status, LINKEDIN_STATUS_INSUFFICIENT)
        self.assertEqual(aggregated.skipped_nd_count, 0)

    @patch("app.services.linkedin.linkedin_lookup_service.utcnow")
    @patch("app.services.linkedin.linkedin_lookup_service.ApifyClient")
    @patch("app.services.linkedin.linkedin_lookup_service.get_settings")
    def test_search_director_parallel_performs_search_and_returns_found(
        self,
        mock_get_settings,
        mock_client_cls,
        mock_utcnow,
    ) -> None:
        """Test that _search_director_parallel performs search and returns found."""
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(enabled=True, api_token="token")
        )
        mock_client = MagicMock()
        mock_client.search_linkedin_profile.return_value = LinkedInProfileResult(
            success=True,
            profile_url="https://linkedin.com/in/jean",
            profile_data={"title": "CEO"},
        )
        mock_client_cls.return_value = mock_client
        now = datetime(2026, 2, 8, tzinfo=timezone.utc)
        mock_utcnow.return_value = now

        session = MagicMock()
        service = LinkedInLookupService(session)

        director = SimpleNamespace(
            id="dir-1",
            first_name_for_search="Jean",
            last_name="Dupont",
            first_names=None,
        )
        establishment = SimpleNamespace(
            siret="000",
            name="Acme Corp",
            enseigne1=None,
            denomination_usuelle_etablissement=None,
            legal_unit_name=None,
            denomination_unite_legale=None,
        )

        result = service._search_director_parallel(director, establishment, None, now)

        self.assertEqual(result["status"], "found")
        self.assertEqual(result["profile_url"], "https://linkedin.com/in/jean")
        self.assertEqual(result["api_calls"], 1)

    @patch("app.services.linkedin.linkedin_lookup_service.utcnow")
    @patch("app.services.linkedin.linkedin_lookup_service.ApifyClient")
    @patch("app.services.linkedin.linkedin_lookup_service.get_settings")
    def test_search_director_parallel_returns_not_found(
        self,
        mock_get_settings,
        mock_client_cls,
        mock_utcnow,
    ) -> None:
        """Test that _search_director_parallel returns not_found when no profile."""
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(enabled=True, api_token="token")
        )
        mock_client = MagicMock()
        mock_client.search_linkedin_profile.return_value = LinkedInProfileResult(
            success=True,
            profile_url=None,
            profile_data=None,
        )
        mock_client_cls.return_value = mock_client
        now = datetime(2026, 2, 8, tzinfo=timezone.utc)
        mock_utcnow.return_value = now

        session = MagicMock()
        service = LinkedInLookupService(session)

        director = SimpleNamespace(
            id="dir-1",
            first_name_for_search="Jean",
            last_name="Dupont",
            first_names=None,
        )
        establishment = SimpleNamespace(
            siret="000",
            name="Acme Corp",
            enseigne1=None,
            denomination_usuelle_etablissement=None,
            legal_unit_name=None,
            denomination_unite_legale=None,
        )

        result = service._search_director_parallel(director, establishment, None, now)

        self.assertEqual(result["status"], "not_found")
        self.assertEqual(result["api_calls"], 1)

    @patch("app.services.linkedin.linkedin_lookup_service.utcnow")
    @patch("app.services.linkedin.linkedin_lookup_service.ApifyClient")
    @patch("app.services.linkedin.linkedin_lookup_service.get_settings")
    def test_search_director_parallel_retries_with_legal_unit(
        self,
        mock_get_settings,
        mock_client_cls,
        mock_utcnow,
    ) -> None:
        """Test that _search_director_parallel retries with legal unit name when not found."""
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(enabled=True, api_token="token")
        )
        mock_client = MagicMock()
        mock_client.search_linkedin_profile.side_effect = [
            LinkedInProfileResult(success=True, profile_url=None, profile_data=None),
            LinkedInProfileResult(
                success=True,
                profile_url="https://linkedin.com/in/jean",
                profile_data={"title": "CEO"},
            ),
        ]
        mock_client_cls.return_value = mock_client
        now = datetime(2026, 2, 8, tzinfo=timezone.utc)
        mock_utcnow.return_value = now

        session = MagicMock()
        service = LinkedInLookupService(session)

        director = SimpleNamespace(
            id="dir-1",
            first_name_for_search="Jean",
            last_name="Dupont",
            first_names=None,
        )
        establishment = SimpleNamespace(
            siret="000",
            name="Acme Branch Paris",
            enseigne1=None,
            denomination_usuelle_etablissement=None,
            legal_unit_name="Dupont Enterprises",
            denomination_unite_legale=None,
        )

        result = service._search_director_parallel(director, establishment, None, now)

        self.assertEqual(result["status"], "found")
        self.assertEqual(result["api_calls"], 2)

    @patch("app.services.linkedin.linkedin_lookup_service.utcnow")
    @patch("app.services.linkedin.linkedin_lookup_service.ApifyClient")
    @patch("app.services.linkedin.linkedin_lookup_service.get_settings")
    def test_search_director_parallel_returns_error_on_api_failure(
        self,
        mock_get_settings,
        mock_client_cls,
        mock_utcnow,
    ) -> None:
        """Test that _search_director_parallel returns error on API failure."""
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(enabled=True, api_token="token")
        )
        mock_client = MagicMock()
        mock_client.search_linkedin_profile.return_value = LinkedInProfileResult(
            success=False,
            profile_url=None,
            error="API error",
        )
        mock_client_cls.return_value = mock_client
        now = datetime(2026, 2, 8, tzinfo=timezone.utc)
        mock_utcnow.return_value = now

        session = MagicMock()
        service = LinkedInLookupService(session)

        director = SimpleNamespace(
            id="dir-1",
            first_name_for_search="Jean",
            last_name="Dupont",
            first_names=None,
        )
        establishment = SimpleNamespace(
            siret="000",
            name="Acme Corp",
            enseigne1=None,
            denomination_usuelle_etablissement=None,
            legal_unit_name=None,
            denomination_unite_legale=None,
        )

        result = service._search_director_parallel(director, establishment, None, now)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"], "API error")
