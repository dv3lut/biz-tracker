from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4
from unittest import TestCase
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.api.routers.admin.linkedin_router import (
    check_director_linkedin,
    debug_director_linkedin,
)
from app.clients.apify_client import LinkedInProfileResult


class LinkedInAdminRoutesTests(TestCase):
    def _session_with_director(self, director):
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = director
        return session

    def test_check_director_linkedin_returns_404_when_missing(self) -> None:
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None
        director_id = uuid4()

        with self.assertRaises(HTTPException) as ctx:
            check_director_linkedin(director_id=director_id, session=session)

        self.assertEqual(ctx.exception.status_code, 404)

    def test_check_director_linkedin_rejects_non_physical(self) -> None:
        director_id = uuid4()
        director = SimpleNamespace(id=director_id, is_physical_person=False)
        session = self._session_with_director(director)

        with self.assertRaises(HTTPException) as ctx:
            check_director_linkedin(director_id=director_id, session=session)

        self.assertEqual(ctx.exception.status_code, 400)

    @patch("app.api.routers.admin.linkedin_router.get_settings")
    def test_check_director_linkedin_returns_503_when_apify_feature_disabled(self, mock_get_settings) -> None:
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(api_token="token", enabled=False)
        )

        director_id = uuid4()
        director = SimpleNamespace(
            id=director_id,
            is_physical_person=True,
            first_name_for_search="Jane",
            first_names="Jane",
            last_name="Doe",
            quality="CEO",
            linkedin_check_status=None,
            linkedin_last_checked_at=None,
        )
        establishment = SimpleNamespace(
            siret="000",
            name="Acme",
            enseigne1=None,
            legal_unit_name=None,
        )
        director.establishment = establishment
        session = self._session_with_director(director)

        with self.assertRaises(HTTPException) as ctx:
            check_director_linkedin(director_id=director_id, session=session)

        self.assertEqual(ctx.exception.status_code, 503)

    @patch("app.api.routers.admin.linkedin_router.get_settings")
    def test_check_director_linkedin_marks_insufficient(self, mock_get_settings) -> None:
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(api_token="token")
        )

        director_id = uuid4()
        director = SimpleNamespace(
            id=director_id,
            is_physical_person=True,
            first_name_for_search=None,
            first_names=None,
            last_name=None,
            quality=None,
            linkedin_check_status=None,
            linkedin_last_checked_at=None,
        )
        establishment = SimpleNamespace(
            siret="000",
            name="Acme",
            enseigne1=None,
            legal_unit_name=None,
        )
        director.establishment = establishment
        session = self._session_with_director(director)

        response = check_director_linkedin(director_id=director_id, session=session)

        self.assertEqual(response.linkedin_check_status, "insufficient")
        self.assertIn("Données insuffisantes", response.message)
        session.commit.assert_called_once()

    @patch("app.api.routers.admin.linkedin_router.ApifyClient")
    @patch("app.api.routers.admin.linkedin_router.get_settings")
    def test_check_director_linkedin_success(self, mock_get_settings, mock_client_cls) -> None:
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(api_token="token")
        )
        mock_client = MagicMock()
        mock_client.search_linkedin_profile.return_value = LinkedInProfileResult(
            success=True,
            profile_url="https://linkedin.com/in/jane",
            profile_data={"title": "CEO"},
        )
        mock_client_cls.return_value = mock_client

        director_id = uuid4()
        director = SimpleNamespace(
            id=director_id,
            is_physical_person=True,
            first_name_for_search="Jane",
            first_names="Jane",
            last_name="Doe",
            quality="CEO",
            linkedin_profile_url=None,
            linkedin_profile_data=None,
            linkedin_check_status=None,
            linkedin_last_checked_at=None,
        )
        establishment = SimpleNamespace(
            siret="000",
            name="Acme",
            enseigne1=None,
            legal_unit_name=None,
        )
        director.establishment = establishment
        session = self._session_with_director(director)

        response = check_director_linkedin(director_id=director_id, session=session)

        self.assertEqual(response.linkedin_profile_url, "https://linkedin.com/in/jane")
        self.assertEqual(response.linkedin_check_status, "found")
        session.commit.assert_called_once()

    @patch("app.api.routers.admin.linkedin_router.ApifyClient")
    @patch("app.api.routers.admin.linkedin_router.get_settings")
    def test_debug_director_linkedin_retries_with_legal_unit(
        self,
        mock_get_settings,
        mock_client_cls,
    ) -> None:
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(api_token="token")
        )
        mock_client = MagicMock()
        mock_client.search_linkedin_profile.side_effect = [
            LinkedInProfileResult(success=False, profile_url=None, error="not_found"),
            LinkedInProfileResult(success=True, profile_url="https://linkedin.com/in/john"),
        ]
        mock_client_cls.return_value = mock_client

        director_id = uuid4()
        director = SimpleNamespace(
            id=director_id,
            is_physical_person=True,
            first_name_for_search="John",
            last_name="Doe",
        )
        establishment = SimpleNamespace(
            siret="000",
            name="Acme",
            enseigne1=None,
            legal_unit_name="Acme Holding",
        )
        director.establishment = establishment
        session = self._session_with_director(director)

        response = debug_director_linkedin(director_id=director_id, session=session)

        self.assertEqual(response.status, "found")
        self.assertTrue(response.retried_with_legal_unit)
        self.assertEqual(response.profile_url, "https://linkedin.com/in/john")
