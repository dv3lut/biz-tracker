from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from app.api.routers import public_router as public
from app.api.schemas import PublicContactRequest


class PublicContactRouterTests(TestCase):
    def setUp(self) -> None:
        self.request = SimpleNamespace(
            client=SimpleNamespace(host="127.0.0.1"),
            headers={"user-agent": "pytest"},
        )

    @patch("app.api.routers.public_router.get_settings")
    def test_honeypot_skips_email_send(self, mock_settings) -> None:
        mock_settings.return_value = SimpleNamespace(
            public_contact=SimpleNamespace(enabled=True, inbox_address="contact@business-tracker.fr")
        )

        sent = []

        class DummyEmail:
            def is_enabled(self):
                return True

            def is_configured(self):
                return True

            def send(self, subject, body, recipients, *, html_body=None, reply_to=None):
                sent.append((subject, tuple(recipients)))

        with patch("app.api.routers.public_router.EmailService", DummyEmail):
            payload = PublicContactRequest(
                name="Jean",
                email="jean@example.com",
                company="ACME",
                phone=None,
                message="Hello",
                website="https://spam.example",
            )
            result = public.submit_contact_form(request=self.request, payload=payload)

        self.assertTrue(result.accepted)
        self.assertEqual(sent, [])

    @patch("app.api.routers.public_router.get_settings")
    def test_sends_contact_email(self, mock_settings) -> None:
        inbox = "contact@business-tracker.fr"
        mock_settings.return_value = SimpleNamespace(
            public_contact=SimpleNamespace(enabled=True, inbox_address=inbox)
        )

        sent = []

        class DummyEmail:
            def is_enabled(self):
                return True

            def is_configured(self):
                return True

            def send(self, subject, body, recipients, *, html_body=None, reply_to=None):
                sent.append((subject, tuple(recipients), reply_to))

        with patch("app.api.routers.public_router.EmailService", DummyEmail):
            payload = PublicContactRequest(
                name="Jean",
                email="jean@example.com",
                company="ACME",
                phone="+33 6 00 00 00 00",
                message="Bonjour",
                website=None,
            )
            result = public.submit_contact_form(request=self.request, payload=payload)

        self.assertTrue(result.accepted)
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0][1], (inbox,))
        self.assertEqual(sent[0][2], "jean@example.com")

    @patch("app.api.routers.public_router.get_settings")
    def test_returns_404_when_endpoint_disabled(self, mock_settings) -> None:
        mock_settings.return_value = SimpleNamespace(
            public_contact=SimpleNamespace(enabled=False, inbox_address="contact@business-tracker.fr")
        )

        with self.assertRaises(Exception) as ctx:
            payload = PublicContactRequest(
                name="Jean",
                email="jean@example.com",
                company="ACME",
                phone=None,
                message=None,
                website=None,
            )
            public.submit_contact_form(request=self.request, payload=payload)

        # FastAPI HTTPException has status_code attribute.
        self.assertEqual(getattr(ctx.exception, "status_code", None), 404)

    @patch("app.api.routers.public_router.get_settings")
    def test_returns_503_when_email_service_unavailable(self, mock_settings) -> None:
        mock_settings.return_value = SimpleNamespace(
            public_contact=SimpleNamespace(enabled=True, inbox_address="contact@business-tracker.fr")
        )

        class DummyEmail:
            def is_enabled(self):
                return False

            def is_configured(self):  # pragma: no cover - should not matter
                return False

        with patch("app.api.routers.public_router.EmailService", DummyEmail):
            with self.assertRaises(Exception) as ctx:
                payload = PublicContactRequest(
                    name="Jean",
                    email="jean@example.com",
                    company="ACME",
                    phone=None,
                    message=None,
                    website=None,
                )
                public.submit_contact_form(request=self.request, payload=payload)

        self.assertEqual(getattr(ctx.exception, "status_code", None), 503)

    def test_format_contact_body_handles_missing_message_and_phone(self) -> None:
        payload = PublicContactRequest(
            name="Jean",
            email="jean@example.com",
            company="ACME",
            phone=" ",
            message=" ",
            website=None,
        )
        body = public._format_contact_body(payload)
        self.assertIn("Téléphone: -", body)
        self.assertTrue(body.strip().endswith("-"))

    @patch("app.api.routers.public_router.get_settings")
    def test_inbox_empty_returns_503(self, mock_settings) -> None:
        mock_settings.return_value = SimpleNamespace(public_contact=SimpleNamespace(enabled=True, inbox_address=" "))

        class DummyEmail:
            def is_enabled(self):
                return True

            def is_configured(self):
                return True

        with patch("app.api.routers.public_router.EmailService", DummyEmail):
            with self.assertRaises(Exception) as ctx:
                payload = PublicContactRequest(
                    name="Jean",
                    email="jean@example.com",
                    company="ACME",
                    phone=None,
                    message="Bonjour",
                    website=None,
                )
                public.submit_contact_form(request=self.request, payload=payload)

        self.assertEqual(getattr(ctx.exception, "status_code", None), 503)
