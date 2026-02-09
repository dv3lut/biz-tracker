"""Tests unitaires pour le calcul de la fenêtre de collecte Sirene."""
from __future__ import annotations

import logging
import unittest
from datetime import date
from types import SimpleNamespace

from app.db import models
from app.services.sync.collector import SyncCollectorMixin
from app.services.sync.context import SyncContext
from app.services.sync.mode import SyncMode
from app.services.sync.replay_reference import DayReplayReference


class _DummyCollector(SyncCollectorMixin):
    """Implémentation minimale du collecteur pour tester la fenêtre de création."""

    def __init__(
        self,
        current_date: date,
        *,
        months_back: int = 6,
        incremental_lookback_months: int = 1,
    ) -> None:
        self._current_date_value = current_date
        self._settings = SimpleNamespace(
            sync=SimpleNamespace(
                months_back=months_back,
                incremental_lookback_months=incremental_lookback_months,
            ),
            sirene=SimpleNamespace(page_size=1000),
        )
        self._logger = logging.getLogger("dummy-collector")

    def _current_date(self) -> date:  # pragma: no cover - simple override for determinism
        return self._current_date_value


class _ReplayAwareCollector(SyncCollectorMixin):
    """Collector factice pour contrôler les candidats Google en mode day replay."""

    def __init__(self, replay_results: list[object], current_date: date) -> None:
        self._replay_results = replay_results
        self._current_date_value = current_date
        self._settings = SimpleNamespace(
            sync=SimpleNamespace(months_back=6, incremental_lookback_months=1),
            sirene=SimpleNamespace(page_size=1000),
        )
        self._logger = logging.getLogger("replay-aware-collector")
        self.last_request: dict[str, object] | None = None

    def _current_date(self) -> date:  # pragma: no cover - simple override for determinism
        return self._current_date_value

    def _load_replay_establishments(
        self,
        session,
        *,
        target_date: date,
        naf_codes: list[str] | None = None,
        reference: DayReplayReference | None = None,
    ) -> list[object]:
        self.last_request = {
            "session": session,
            "target_date": target_date,
            "naf_codes": list(naf_codes or []),
            "reference": reference or DayReplayReference.CREATION_DATE,
        }
        return list(self._replay_results)


class ComputeSinceCreationTests(unittest.TestCase):
    """Vérifie le calcul de la fenêtre `dateCreationEtablissement`."""

    def test_returns_baseline_when_no_checkpoint(self) -> None:
        collector = _DummyCollector(date(2025, 11, 15), months_back=6)
        state = models.SyncState(scope_key="restaurants")

        result = collector._compute_since_creation(state, months_back=6)

        self.assertEqual(result, date(2025, 5, 15))

class ComputeSinceCreationIncrementalTests(unittest.TestCase):
    """Vérifie le calcul de la fenêtre pour les synchros incrémentales auto."""

    def test_returns_lookback_baseline_when_no_checkpoint(self) -> None:
        """Sans checkpoint, on regarde 1 mois en arrière (incremental_lookback_months)."""
        collector = _DummyCollector(date(2025, 11, 15), incremental_lookback_months=1)
        state = models.SyncState(scope_key="restaurants")

        result = collector._compute_since_creation_incremental(state)

        # 15 nov - 1 mois = 15 oct
        self.assertEqual(result, date(2025, 10, 15))

    def test_returns_baseline_with_lookback_zero(self) -> None:
        """Si lookback est 0, on retourne la date du jour (comportement legacy)."""
        collector = _DummyCollector(date(2025, 11, 15), incremental_lookback_months=0)
        state = models.SyncState(scope_key="restaurants")

        result = collector._compute_since_creation_incremental(state)

        self.assertEqual(result, date(2025, 11, 15))

    def test_larger_lookback_goes_further_back(self) -> None:
        """Avec 2 mois de lookback, on regarde plus loin en arrière."""
        collector = _DummyCollector(
            date(2025, 11, 15),
            incremental_lookback_months=2,
        )
        state = models.SyncState(scope_key="restaurants")

        result = collector._compute_since_creation_incremental(state)

        # 15 nov - 2 mois = 15 sept
        self.assertEqual(result, date(2025, 9, 15))


class ResolveGoogleCandidatesTests(unittest.TestCase):
    """Vérifie que les candidats Google sont enrichis correctement en day replay."""

    def _make_context(
        self,
        *,
        mode: SyncMode,
        replay_for_date: date | None = None,
        target_naf_codes: list[str] | None = None,
        replay_reference: DayReplayReference = DayReplayReference.CREATION_DATE,
    ) -> SyncContext:
        return SyncContext(
            session=SimpleNamespace(name="session"),
            run=SimpleNamespace(id="run", scope_key="restaurants"),
            state=SimpleNamespace(),
            client=SimpleNamespace(),
            settings=SimpleNamespace(),
            mode=mode,
            replay_for_date=replay_for_date,
            target_naf_codes=target_naf_codes,
            replay_reference=replay_reference,
        )

    def test_non_replay_mode_keeps_base_candidates(self) -> None:
        collector = _ReplayAwareCollector([], current_date=date(2025, 11, 15))
        base_candidates = [SimpleNamespace(siret="11111111111111"), SimpleNamespace(siret="22222222222222")]
        context = self._make_context(mode=SyncMode.FULL)

        candidates, force_refresh = collector._resolve_google_candidates(context, base_candidates, ["5610A"])

        self.assertEqual([candidate.siret for candidate in candidates], ["11111111111111", "22222222222222"])
        self.assertFalse(force_refresh)
        self.assertIsNone(collector.last_request)

    def test_day_replay_appends_rehydrated_candidates(self) -> None:
        replay_candidates = [SimpleNamespace(siret="22222222222222"), SimpleNamespace(siret="33333333333333")]
        collector = _ReplayAwareCollector(replay_candidates, current_date=date(2025, 11, 15))
        base_candidates = [SimpleNamespace(siret="11111111111111"), SimpleNamespace(siret="22222222222222")]
        context = self._make_context(mode=SyncMode.DAY_REPLAY, replay_for_date=date(2025, 11, 10), target_naf_codes=["5610A"])

        candidates, force_refresh = collector._resolve_google_candidates(context, base_candidates, ["5610A"])

        self.assertEqual(
            [candidate.siret for candidate in candidates],
            ["11111111111111", "22222222222222", "33333333333333"],
        )
        self.assertTrue(force_refresh)
        last_request = collector.last_request
        self.assertIsNotNone(last_request)
        if last_request is not None:
            self.assertEqual(last_request["naf_codes"], ["5610A"])
            self.assertEqual(last_request["target_date"], date(2025, 11, 10))
            self.assertEqual(last_request["reference"], DayReplayReference.CREATION_DATE)

    def test_day_replay_can_switch_reference_mode(self) -> None:
        collector = _ReplayAwareCollector([], current_date=date(2025, 11, 15))
        context = self._make_context(
            mode=SyncMode.DAY_REPLAY,
            replay_for_date=date(2025, 11, 10),
            target_naf_codes=None,
            replay_reference=DayReplayReference.INSERTION_DATE,
        )

        collector._resolve_google_candidates(context, [], [])

        self.assertIsNotNone(collector.last_request)
        if collector.last_request is not None:
            self.assertEqual(collector.last_request["reference"], DayReplayReference.INSERTION_DATE)


class DayReplayPolicyTests(unittest.TestCase):
    def test_filter_ready_google_matches_requires_found_status_and_link(self) -> None:
        collector = _ReplayAwareCollector([], current_date=date(2025, 11, 15))
        establishments = [
            SimpleNamespace(google_check_status="found", google_place_url="https://example.com", google_place_id=None),
            SimpleNamespace(google_check_status="found", google_place_url=None, google_place_id="place123"),
            SimpleNamespace(google_check_status="found", google_place_url=None, google_place_id=None),
            SimpleNamespace(google_check_status="pending", google_place_url="https://example.com", google_place_id="place456"),
        ]

        ready = collector._filter_ready_google_matches(establishments)

        self.assertEqual(len(ready), 2)
        self.assertTrue(all(getattr(item, "google_check_status", "").lower() == "found" for item in ready))


if __name__ == "__main__":
    unittest.main()
