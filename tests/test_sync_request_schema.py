from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

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
        self.assertEqual(payload.naf_codes, ["56.10A", "56.10B", "56.10C"])

    def test_rejects_invalid_naf_code_format(self) -> None:
        with self.assertRaises(ValidationError):
            SyncRequest(mode=SyncMode.FULL, naf_codes=["INVALID"])

    def test_limits_number_of_naf_codes(self) -> None:
        with self.assertRaises(ValidationError):
            SyncRequest(mode=SyncMode.FULL, naf_codes=[f"5610{chr(65 + (i % 26))}" for i in range(30)])

    def test_target_clients_require_day_replay(self) -> None:
        with self.assertRaises(ValidationError):
            SyncRequest(mode=SyncMode.FULL, target_client_ids=[uuid4()])

    def test_target_clients_deduplicated(self) -> None:
        client_id = uuid4()
        payload = SyncRequest(
            mode=SyncMode.DAY_REPLAY,
            replay_for_date=date.today(),
            target_client_ids=[client_id, client_id],
        )
        self.assertEqual(payload.target_client_ids, [client_id])

    def test_target_clients_limit_enforced(self) -> None:
        with self.assertRaises(ValidationError):
            SyncRequest(
                mode=SyncMode.DAY_REPLAY,
                replay_for_date=date.today(),
                target_client_ids=[uuid4() for _ in range(60)],
            )

    def test_notify_admins_toggle_restricted(self) -> None:
        with self.assertRaises(ValidationError):
            SyncRequest(mode=SyncMode.FULL, notify_admins=False)

    def test_day_replay_accepts_admin_toggle(self) -> None:
        payload = SyncRequest(
            mode=SyncMode.DAY_REPLAY,
            replay_for_date=date.today(),
            notify_admins=False,
        )
        self.assertFalse(payload.notify_admins)

    def test_force_google_replay_restricted_to_day_replay(self) -> None:
        with self.assertRaises(ValidationError):
            SyncRequest(mode=SyncMode.FULL, force_google_replay=True)

    def test_force_google_replay_allowed_for_day_replay(self) -> None:
        payload = SyncRequest(
            mode=SyncMode.DAY_REPLAY,
            replay_for_date=date.today(),
            force_google_replay=True,
        )
        self.assertTrue(payload.force_google_replay)


if __name__ == "__main__":
    unittest.main()
