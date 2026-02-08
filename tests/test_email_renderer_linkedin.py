from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase

from app.services.alerts import email_renderer


class EmailRendererLinkedInTests(TestCase):
    def test_get_linkedin_title_prefers_profile_data(self) -> None:
        director = SimpleNamespace(
            linkedin_profile_data={"title": "CEO"},
            quality="Président",
        )
        title = email_renderer._get_linkedin_title_for_director(director)
        self.assertEqual(title, "CEO")

    def test_get_linkedin_title_falls_back_to_quality(self) -> None:
        director = SimpleNamespace(
            linkedin_profile_data=None,
            quality="Président",
        )
        title = email_renderer._get_linkedin_title_for_director(director)
        self.assertEqual(title, "Président")

    def test_get_linkedin_title_defaults_to_dirigeant(self) -> None:
        director = SimpleNamespace(
            linkedin_profile_data=None,
            quality=None,
        )
        title = email_renderer._get_linkedin_title_for_director(director)
        self.assertEqual(title, "Dirigeant")

    def test_get_linkedin_title_ignores_non_string_profile_title(self) -> None:
        director = SimpleNamespace(
            linkedin_profile_data={"title": 123},
            quality=None,
        )
        title = email_renderer._get_linkedin_title_for_director(director)
        self.assertEqual(title, "Dirigeant")

    def test_build_linkedin_buttons_returns_empty_when_none(self) -> None:
        establishment = SimpleNamespace(directors=[])
        text_lines, html_block = email_renderer._build_linkedin_buttons_html(
            establishment,
            theme={},
        )
        self.assertEqual(text_lines, [])
        self.assertEqual(html_block, "")

    def test_build_linkedin_buttons_renders_profiles(self) -> None:
        director = SimpleNamespace(
            is_physical_person=True,
            linkedin_profile_url="https://linkedin.com/in/jane",
            linkedin_profile_data={"title": "CEO"},
            quality=None,
        )
        establishment = SimpleNamespace(directors=[director])

        text_lines, html_block = email_renderer._build_linkedin_buttons_html(
            establishment,
            theme={},
        )

        self.assertTrue(any("https://linkedin.com/in/jane" in line for line in text_lines))
        self.assertIn("Contacter le CEO sur LinkedIn", html_block)
        self.assertIn("https://linkedin.com/in/jane", html_block)

    def test_build_linkedin_buttons_skips_non_physical_director(self) -> None:
        director = SimpleNamespace(
            is_physical_person=False,
            linkedin_profile_url="https://linkedin.com/in/jane",
            linkedin_profile_data={"title": "CEO"},
            quality=None,
        )
        establishment = SimpleNamespace(directors=[director])

        text_lines, html_block = email_renderer._build_linkedin_buttons_html(
            establishment,
            theme={},
        )

        self.assertEqual(text_lines, [])
        self.assertEqual(html_block, "")
