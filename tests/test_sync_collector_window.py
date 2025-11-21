"""Tests unitaires pour le calcul de la fenêtre de collecte Sirene."""
from __future__ import annotations

import logging
import unittest
from datetime import date
from types import SimpleNamespace

from app.db import models
from app.services.sync.collector import SyncCollectorMixin


class _DummyCollector(SyncCollectorMixin):
    """Implémentation minimale du collecteur pour tester la fenêtre de création."""

    def __init__(self, current_date: date, *, months_back: int = 6, overlap_days: int = 3) -> None:
        self._current_date_value = current_date
        self._settings = SimpleNamespace(
            sync=SimpleNamespace(months_back=months_back, creation_overlap_days=overlap_days),
            sirene=SimpleNamespace(page_size=1000),
        )
        self._logger = logging.getLogger("dummy-collector")

    def _current_date(self) -> date:  # pragma: no cover - simple override for determinism
        return self._current_date_value


class ComputeSinceCreationTests(unittest.TestCase):
    """Vérifie le calcul de la fenêtre `dateCreationEtablissement`."""

    def test_returns_baseline_when_no_checkpoint(self) -> None:
        collector = _DummyCollector(date(2025, 11, 15), months_back=6)
        state = models.SyncState(scope_key="restaurants")

        result = collector._compute_since_creation(state, months_back=6)

        self.assertEqual(result, date(2025, 5, 15))

    def test_applies_overlap_and_clamps_to_today(self) -> None:
        collector = _DummyCollector(date(2025, 11, 15), overlap_days=2)
        state = models.SyncState(scope_key="restaurants")
        state.last_creation_date = date(2025, 11, 14)

        result = collector._compute_since_creation(state, months_back=6)

        self.assertEqual(result, date(2025, 11, 12))

        # Couvre le cas où la dernière création dépasse la date du jour (publication anticipée)
        state.last_creation_date = date(2025, 11, 20)
        result_future = collector._compute_since_creation(state, months_back=6)
        self.assertEqual(result_future, date(2025, 11, 15))

    def test_never_goes_before_baseline(self) -> None:
        collector = _DummyCollector(date(2025, 11, 15), months_back=3, overlap_days=5)
        state = models.SyncState(scope_key="restaurants")
        state.last_creation_date = date(2025, 7, 1)

        result = collector._compute_since_creation(state, months_back=3)

        # Baseline = 2025-08-15 -> même avec overlap, on reste borné au baseline
        self.assertEqual(result, date(2025, 8, 15))


if __name__ == "__main__":
    unittest.main()
