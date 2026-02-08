from __future__ import annotations

from unittest import TestCase

from app.utils.urls import ANNULAIRE_ETABLISSEMENT_BASE_URL, build_annuaire_etablissement_url


class UrlsUtilsTests(TestCase):
    def test_build_annuaire_url_with_valid_siret(self) -> None:
        url = build_annuaire_etablissement_url("123 456 789 00000")
        self.assertEqual(url, f"{ANNULAIRE_ETABLISSEMENT_BASE_URL}/12345678900000")

    def test_build_annuaire_url_invalid(self) -> None:
        self.assertIsNone(build_annuaire_etablissement_url("123"))
        self.assertIsNone(build_annuaire_etablissement_url(None))
