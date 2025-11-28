from __future__ import annotations

from datetime import date, timedelta

import unittest
from pydantic import ValidationError

from app.api.schemas import SyncRequest
from app.services.sync.mode import SyncMode


class SyncRequestSchemaTests(unittest.TestCase):
    def test_day_replay_requires_date(self) -> None:
        with self.assertRaises(ValidationError):
            SyncRequest(mode=SyncMode.DAY_REPLAY)

    def test_replay_date_forbidden_in_other_modes(self) -> None:
        with self.assertRaises(ValidationError):
            SyncRequest(mode=SyncMode.FULL, replay_for_date=date.today())

    def test_day_replay_rejects_future_date(self) -> None:
        future_day = date.today() + timedelta(days=1)
        with self.assertRaises(ValidationError):
            SyncRequest(mode=SyncMode.DAY_REPLAY, replay_for_date=future_day)

    def test_day_replay_accepts_valid_payload(self) -> None:
        payload = SyncRequest(mode=SyncMode.DAY_REPLAY, replay_for_date=date.today())
        self.assertIsNotNone(payload.replay_for_date)
        self.assertEqual(payload.mode, SyncMode.DAY_REPLAY)

    def test_accepts_valid_naf_codes(self) -> None:
        payload = SyncRequest(mode=SyncMode.FULL, naf_codes=["5610A", "56.10b", "  5610C  "])
        self.assertEqual(payload.naf_codes, ["5610A", "5610B", "5610C"])

    def test_rejects_invalid_naf_code_format(self) -> None:
        with self.assertRaises(ValidationError):
            SyncRequest(mode=SyncMode.FULL, naf_codes=["INVALID"])

    def test_limits_number_of_naf_codes(self) -> None:
        with self.assertRaises(ValidationError):
            SyncRequest(mode=SyncMode.FULL, naf_codes=[f"5610{chr(65 + (i % 26))}" for i in range(30)])


if __name__ == "__main__":
    unittest.main()
