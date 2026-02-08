from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest import TestCase

from app.services.alerts import email_renderer


class EmailRendererUtilsTests(TestCase):
    def test_format_date_fr(self) -> None:
        value = date(2026, 2, 8)
        self.assertEqual(email_renderer._format_date_fr(value), "8 février 2026")

    def test_section_title_for_status_uses_overrides(self) -> None:
        title = email_renderer._section_title_for_status("not_recent_creation")
        self.assertEqual(title, "Modification administrative récente")

    def test_section_title_for_status_defaults(self) -> None:
        title = email_renderer._section_title_for_status("custom_status")
        self.assertEqual(title, "custom_status")

    def test_format_listing_status_labels(self) -> None:
        labels = email_renderer._format_listing_status_labels(["recent_creation", "unknown"])
        self.assertEqual(labels, ["Création récente", "Non déterminé"])

    def test_get_status_badge_html_contains_label(self) -> None:
        html = email_renderer._get_status_badge_html("unknown", "Non déterminé")
        self.assertIn("Non déterminé", html)
        self.assertIn("<span", html)

    def test_order_establishments_by_status(self) -> None:
        est_a = SimpleNamespace(google_listing_age_status="recent_creation")
        est_b = SimpleNamespace(google_listing_age_status="not_recent_creation")
        est_c = SimpleNamespace(google_listing_age_status="unknown")

        ordered = email_renderer._order_establishments_by_status(
            [est_b, est_c, est_a],
            ordered_statuses=["recent_creation", "not_recent_creation"],
        )

        self.assertEqual(ordered, [est_a, est_b, est_c])
