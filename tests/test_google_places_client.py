from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

from app.clients.google_places_client import GooglePlacesClient, GooglePlacesError


class GooglePlacesClientTests(TestCase):
    @patch("app.clients.google_places_client.get_settings")
    @patch("app.clients.google_places_client.log_event")
    def test_find_place_raises_on_request_denied(self, mock_log_event, mock_get_settings) -> None:
        google_settings = SimpleNamespace(
            enabled=True,
            find_place_url="https://example.test/find",
            place_details_url="https://example.test/details",
            language="fr",
            api_key="test-key",
        )
        mock_get_settings.return_value = SimpleNamespace(google=google_settings)

        client = GooglePlacesClient()
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"status":"REQUEST_DENIED"}'
        mock_response.content = b"{}"
        mock_response.json.return_value = {
            "status": "REQUEST_DENIED",
            "error_message": "The provided API key is invalid.",
        }
        mock_session.get.return_value = mock_response
        client._session = mock_session

        with self.assertRaises(GooglePlacesError) as ctx:
            client.find_place("Chez Paul Paris 75001", fields="place_id")

        self.assertIn("REQUEST_DENIED", str(ctx.exception))
        self.assertEqual(getattr(ctx.exception, "google_status", None), "REQUEST_DENIED")
        self.assertTrue(mock_log_event.called)
        call_kwargs = mock_log_event.call_args.kwargs
        self.assertEqual(call_kwargs["external"]["outcome"], "api_error")

    @patch("app.clients.google_places_client.get_settings")
    def test_find_place_returns_empty_on_zero_results(self, mock_get_settings) -> None:
        google_settings = SimpleNamespace(
            enabled=True,
            find_place_url="https://example.test/find",
            place_details_url="https://example.test/details",
            language="fr",
            api_key="test-key",
        )
        mock_get_settings.return_value = SimpleNamespace(google=google_settings)

        client = GooglePlacesClient()
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"status":"ZERO_RESULTS"}'
        mock_response.content = b"{}"
        mock_response.json.return_value = {"status": "ZERO_RESULTS", "candidates": []}
        mock_session.get.return_value = mock_response
        client._session = mock_session

        candidates = client.find_place("Query", fields="place_id")
        self.assertEqual(candidates, [])

    @patch("app.clients.google_places_client.get_settings")
    def test_place_details_raises_on_over_query_limit(self, mock_get_settings) -> None:
        google_settings = SimpleNamespace(
            enabled=True,
            find_place_url="https://example.test/find",
            place_details_url="https://example.test/details",
            language="fr",
            api_key="test-key",
        )
        mock_get_settings.return_value = SimpleNamespace(google=google_settings)

        client = GooglePlacesClient()
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"status":"OVER_QUERY_LIMIT"}'
        mock_response.content = b"{}"
        mock_response.json.return_value = {
            "status": "OVER_QUERY_LIMIT",
            "error_message": "You have exceeded your daily request quota for this API.",
        }
        mock_session.get.return_value = mock_response
        client._session = mock_session

        with self.assertRaises(GooglePlacesError) as ctx:
            client.get_place_details("place-id", fields="place_id")

        self.assertIn("OVER_QUERY_LIMIT", str(ctx.exception))
        self.assertEqual(getattr(ctx.exception, "google_status", None), "OVER_QUERY_LIMIT")
