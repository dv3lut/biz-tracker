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
            linkedin_check_status=LINKEDIN_STATUS_PENDING,
            linkedin_last_checked_at=None,
            linkedin_profile_url=None,
            linkedin_profile_data=None,
        )
        establishment = SimpleNamespace(
            siret="000",
            name="Acme",
            enseigne1=None,
            denomination_usuelle_etablissement=None,
            legal_unit_name="Acme Holding",
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
            apify=SimpleNamespace(enabled=False, api_token=None)
        )
        session = MagicMock()
        service = LinkedInLookupService(session)

        result_a = SimpleNamespace(
            total_directors=1,
            eligible_directors=1,
            searched_count=1,
            found_count=1,
            not_found_count=0,
            error_count=0,
            api_call_count=1,
            directors_with_profiles=["d1"],
        )
        result_b = SimpleNamespace(
            total_directors=2,
            eligible_directors=1,
            searched_count=1,
            found_count=0,
            not_found_count=1,
            error_count=0,
            api_call_count=1,
            directors_with_profiles=[],
        )
        service.enrich_establishment_directors = MagicMock(side_effect=[result_a, result_b])

        total = service.enrich_batch(["est-1", "est-2"], run_id=None, force_refresh=False)

        self.assertEqual(total.total_directors, 3)
        self.assertEqual(total.eligible_directors, 2)
        self.assertEqual(total.searched_count, 2)
        self.assertEqual(total.found_count, 1)
        self.assertEqual(total.not_found_count, 1)
        self.assertEqual(total.error_count, 0)
        self.assertEqual(total.api_call_count, 2)
        self.assertEqual(total.directors_with_profiles, ["d1"])
