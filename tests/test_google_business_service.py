"""Tests unitaires pour l'évaluation de l'âge des fiches Google."""
from __future__ import annotations

import unittest

from app.services.google_business_service import GoogleBusinessService


class GoogleListingAgeStatusTests(unittest.TestCase):
    """Couvre les scénarios d'absence d'avis pour la détection de fiche récente."""

    def setUp(self) -> None:
        # On instancie la classe sans __init__ car la méthode testée n'utilise aucun attribut.
        self.service = GoogleBusinessService.__new__(GoogleBusinessService)

    def test_assumes_recent_when_reviews_empty(self) -> None:
        details = {"reviews": []}

        self.assertTrue(self.service._should_assume_recent_listing(details))

    def test_assumes_recent_when_reviews_missing_and_no_ratings(self) -> None:
        details = {}

        self.assertTrue(self.service._should_assume_recent_listing(details))

    def test_does_not_assume_recent_when_ratings_positive(self) -> None:
        details = {"user_ratings_total": 5}

        self.assertFalse(self.service._should_assume_recent_listing(details))

    def test_assumes_recent_when_ratings_zero(self) -> None:
        details = {"user_ratings_total": 0}

        self.assertTrue(self.service._should_assume_recent_listing(details))


if __name__ == "__main__":
    unittest.main()
