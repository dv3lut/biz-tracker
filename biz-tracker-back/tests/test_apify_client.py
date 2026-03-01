from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

import requests

from app.clients.apify_client import ApifyClient, LinkedInSearchInput


class ApifyClientTests(TestCase):
    @patch("app.clients.apify_client.get_settings")
    def test_search_returns_error_when_disabled(self, mock_get_settings) -> None:
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(
                enabled=False,
                api_token=None,
                linkedin_actor_id="actor",
                request_timeout_seconds=1,
            )
        )

        client = ApifyClient()
        result = client.search_linkedin_profile(LinkedInSearchInput("Jane", "Doe", "Acme"))

        self.assertFalse(result.success)
        self.assertIn("not configured", result.error or "")

    @patch("app.clients.apify_client.requests.Session")
    @patch("app.clients.apify_client.get_settings")
    def test_search_returns_profile_when_dataset_has_items(
        self,
        mock_get_settings,
        mock_session_cls,
    ) -> None:
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(
                enabled=True,
                api_token="token",
                linkedin_actor_id="actor",
                request_timeout_seconds=1,
            )
        )
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        run_response = MagicMock()
        run_response.raise_for_status.return_value = None
        run_response.json.return_value = {
            "data": {
                "status": "SUCCEEDED",
                "defaultDatasetId": "dataset-1",
            }
        }

        dataset_response = MagicMock()
        dataset_response.raise_for_status.return_value = None
        dataset_response.json.return_value = [
            {
                "linkedinProfileUrl": "https://linkedin.com/in/jane",
                "profileData": {"title": "CEO"},
            }
        ]

        mock_session.post.return_value = run_response
        mock_session.get.return_value = dataset_response

        client = ApifyClient()
        result = client.search_linkedin_profile(LinkedInSearchInput("Jane", "Doe", "Acme"))

        self.assertTrue(result.success)
        self.assertEqual(result.profile_url, "https://linkedin.com/in/jane")
        self.assertEqual(result.profile_data, {"title": "CEO"})

    @patch("app.clients.apify_client.requests.Session")
    @patch("app.clients.apify_client.get_settings")
    def test_search_returns_error_when_run_not_succeeded(
        self,
        mock_get_settings,
        mock_session_cls,
    ) -> None:
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(
                enabled=True,
                api_token="token",
                linkedin_actor_id="actor",
                request_timeout_seconds=1,
            )
        )
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        run_response = MagicMock()
        run_response.raise_for_status.return_value = None
        run_response.json.return_value = {
            "data": {
                "status": "FAILED",
                "defaultDatasetId": "dataset-1",
            }
        }
        mock_session.post.return_value = run_response

        client = ApifyClient()
        result = client.search_linkedin_profile(LinkedInSearchInput("Jane", "Doe", "Acme"))

        self.assertFalse(result.success)
        self.assertIn("Apify run status", result.error or "")

    @patch("app.clients.apify_client.requests.Session")
    @patch("app.clients.apify_client.get_settings")
    def test_search_returns_success_with_no_profile_when_empty_items(
        self,
        mock_get_settings,
        mock_session_cls,
    ) -> None:
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(
                enabled=True,
                api_token="token",
                linkedin_actor_id="actor",
                request_timeout_seconds=1,
            )
        )
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        run_response = MagicMock()
        run_response.raise_for_status.return_value = None
        run_response.json.return_value = {
            "data": {
                "status": "SUCCEEDED",
                "defaultDatasetId": "dataset-1",
            }
        }
        dataset_response = MagicMock()
        dataset_response.raise_for_status.return_value = None
        dataset_response.json.return_value = []

        mock_session.post.return_value = run_response
        mock_session.get.return_value = dataset_response

        client = ApifyClient()
        result = client.search_linkedin_profile(LinkedInSearchInput("Jane", "Doe", "Acme"))

        self.assertTrue(result.success)
        self.assertIsNone(result.profile_url)

    @patch("app.clients.apify_client.requests.Session")
    @patch("app.clients.apify_client.get_settings")
    def test_search_handles_timeout(self, mock_get_settings, mock_session_cls) -> None:
        mock_get_settings.return_value = SimpleNamespace(
            apify=SimpleNamespace(
                enabled=True,
                api_token="token",
                linkedin_actor_id="actor",
                request_timeout_seconds=1,
            )
        )
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_session.post.side_effect = requests.Timeout("boom")

        client = ApifyClient()
        result = client.search_linkedin_profile(LinkedInSearchInput("Jane", "Doe", "Acme"))

        self.assertFalse(result.success)
        self.assertIn("timeout", (result.error or "").lower())
