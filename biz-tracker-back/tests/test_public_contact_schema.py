from __future__ import annotations

from unittest import TestCase

from pydantic import ValidationError

from app.api.schemas import PublicContactRequest


class PublicContactSchemaTests(TestCase):
    def test_email_is_trimmed(self) -> None:
        payload = PublicContactRequest(
            name="Jean",
            email="  jean@example.com  ",
            company="ACME",
            phone=None,
            message=None,
            website=None,
        )
        self.assertEqual(payload.email, "jean@example.com")

    def test_email_rejects_non_string(self) -> None:
        with self.assertRaises(ValidationError):
            PublicContactRequest(
                name="Jean",
                email=123,  # type: ignore[arg-type]
                company="ACME",
                phone=None,
                message=None,
                website=None,
            )

    def test_email_rejects_missing_or_invalid(self) -> None:
        for value in ["", "   ", "example.com", "@example.com", "jean@", "jean@localhost"]:
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    PublicContactRequest(
                        name="Jean",
                        email=value,
                        company="ACME",
                        phone=None,
                        message=None,
                        website=None,
                    )

    def test_email_rejects_personal_domains(self) -> None:
        for value in ["jean@gmail.com", "jean@laposte.net", "jean@outlook.com"]:
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    PublicContactRequest(
                        name="Jean",
                        email=value,
                        company="ACME",
                        phone=None,
                        message=None,
                        website=None,
                    )
