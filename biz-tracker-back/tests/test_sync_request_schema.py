from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import unittest
from pydantic import ValidationError

from app.api.schemas import SyncRequest, SyncRunOut
from app.services.sync.mode import SyncMode
from app.services.sync.replay_reference import DayReplayReference, DEFAULT_DAY_REPLAY_REFERENCE
from app.utils.dates import utcnow


class SyncRequestSchemaTests(unittest.TestCase):
    def _build_sync_run_out(self, *, mode: SyncMode) -> SyncRunOut:
        return SyncRunOut(
            id=uuid4(),
            scope_key="default",
            run_type="sync",
            status="completed",
            mode=mode,
            replay_for_date=None,
            started_at=utcnow(),
            finished_at=None,
            api_call_count=0,
            google_api_call_count=0,
            fetched_records=0,
            created_records=0,
            google_queue_count=0,
            google_eligible_count=0,
            google_matched_count=0,
            google_pending_count=0,
            google_immediate_matched_count=0,
            google_late_matched_count=0,
            updated_records=0,
            summary=None,
            last_cursor=None,
            query_checksum=None,
            resumed_from_run_id=None,
            notes=None,
            target_naf_codes=None,
            target_client_ids=None,
            notify_admins=True,
            day_replay_force_google=False,
            day_replay_reference=DEFAULT_DAY_REPLAY_REFERENCE,
            months_back=None,
            total_expected_records=None,
            progress=None,
            estimated_remaining_seconds=None,
            estimated_completion_at=None,
            linkedin_queue_count=0,
            linkedin_searched_count=0,
            linkedin_found_count=0,
            linkedin_not_found_count=0,
            linkedin_error_count=0,
        )

    def test_sync_run_out_computed_flags(self) -> None:
        sirene_only = self._build_sync_run_out(mode=SyncMode.SIRENE_ONLY)
        self.assertFalse(sirene_only.google_enabled)
        self.assertFalse(sirene_only.linkedin_enabled)

        full_run = self._build_sync_run_out(mode=SyncMode.FULL)
        self.assertTrue(full_run.google_enabled)
        self.assertTrue(full_run.linkedin_enabled)

        linkedin_run = self._build_sync_run_out(mode=SyncMode.LINKEDIN_PENDING)
        self.assertTrue(linkedin_run.linkedin_enabled)

    def test_day_replay_requires_date(self) -> None:
        with self.assertRaises(ValidationError):
            SyncRequest(mode=SyncMode.DAY_REPLAY)

    def test_replay_date_forbidden_in_other_modes(self) -> None:
        today = utcnow().date()
        with self.assertRaises(ValidationError):
            SyncRequest(mode=SyncMode.FULL, replay_for_date=today)

    def test_day_replay_rejects_future_date(self) -> None:
        future_day = utcnow().date() + timedelta(days=1)
        with self.assertRaises(ValidationError):
            SyncRequest(mode=SyncMode.DAY_REPLAY, replay_for_date=future_day)

    def test_day_replay_accepts_valid_payload(self) -> None:
        payload = SyncRequest(mode=SyncMode.DAY_REPLAY, replay_for_date=utcnow().date())
        self.assertIsNotNone(payload.replay_for_date)
        self.assertEqual(payload.mode, SyncMode.DAY_REPLAY)

    def test_accepts_valid_naf_codes(self) -> None:
        payload = SyncRequest(mode=SyncMode.FULL, naf_codes=["5610A", "56.10b", "  5610C  "])
        self.assertEqual(payload.naf_codes, ["56.10A", "56.10B", "56.10C"])

    def test_accepts_empty_naf_codes_list(self) -> None:
        payload = SyncRequest(mode=SyncMode.FULL, naf_codes=[])
        self.assertIsNone(payload.naf_codes)

    def test_deduplicates_naf_codes(self) -> None:
        payload = SyncRequest(mode=SyncMode.FULL, naf_codes=["56.10A", "5610a", "56.10A"])
        self.assertEqual(payload.naf_codes, ["56.10A"])

    def test_rejects_invalid_naf_code_format(self) -> None:
        with self.assertRaises(ValidationError):
            SyncRequest(mode=SyncMode.FULL, naf_codes=["INVALID"])

    def test_limits_number_of_naf_codes(self) -> None:
        with self.assertRaises(ValidationError):
            SyncRequest(mode=SyncMode.FULL, naf_codes=[f"5610{chr(65 + (i % 26))}" for i in range(30)])

    def test_target_clients_allowed_for_full(self) -> None:
        client_id = uuid4()
        payload = SyncRequest(mode=SyncMode.FULL, target_client_ids=[client_id, client_id])
        self.assertEqual(payload.target_client_ids, [client_id])

    def test_target_clients_restricted_to_supported_modes(self) -> None:
        with self.assertRaises(ValidationError):
            SyncRequest(mode=SyncMode.SIRENE_ONLY, target_client_ids=[uuid4()])

    def test_target_clients_deduplicated(self) -> None:
        client_id = uuid4()
        payload = SyncRequest(
            mode=SyncMode.DAY_REPLAY,
            replay_for_date=utcnow().date(),
            target_client_ids=[client_id, client_id],
        )
        self.assertEqual(payload.target_client_ids, [client_id])

    def test_target_clients_invalid_uuid_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            SyncRequest(
                mode=SyncMode.DAY_REPLAY,
                replay_for_date=utcnow().date(),
                target_client_ids=["not-a-uuid"],
            )

    def test_target_clients_limit_enforced(self) -> None:
        with self.assertRaises(ValidationError):
            SyncRequest(
                mode=SyncMode.DAY_REPLAY,
                replay_for_date=utcnow().date(),
                target_client_ids=[uuid4() for _ in range(60)],
            )

    def test_notify_admins_toggle_restricted(self) -> None:
        with self.assertRaises(ValidationError):
            SyncRequest(mode=SyncMode.FULL, notify_admins=False)

    def test_day_replay_accepts_admin_toggle(self) -> None:
        payload = SyncRequest(
            mode=SyncMode.DAY_REPLAY,
            replay_for_date=utcnow().date(),
            notify_admins=False,
        )
        self.assertFalse(payload.notify_admins)

    def test_force_google_replay_restricted_to_day_replay(self) -> None:
        with self.assertRaises(ValidationError):
            SyncRequest(mode=SyncMode.FULL, force_google_replay=True)

    def test_force_google_replay_allowed_for_day_replay(self) -> None:
        payload = SyncRequest(
            mode=SyncMode.DAY_REPLAY,
            replay_for_date=utcnow().date(),
            force_google_replay=True,
        )
        self.assertTrue(payload.force_google_replay)

    def test_replay_reference_restricted_to_day_replay(self) -> None:
        with self.assertRaises(ValidationError):
            SyncRequest(mode=SyncMode.FULL, replay_reference=DayReplayReference.INSERTION_DATE)

    def test_replay_reference_allowed_for_day_replay(self) -> None:
        payload = SyncRequest(
            mode=SyncMode.DAY_REPLAY,
            replay_for_date=utcnow().date(),
            replay_reference=DayReplayReference.INSERTION_DATE,
        )
        self.assertEqual(payload.replay_reference, DayReplayReference.INSERTION_DATE)

    def test_google_refresh_accepts_reset_google_state(self) -> None:
        payload = SyncRequest(mode=SyncMode.GOOGLE_REFRESH, reset_google_state=True, google_statuses=["pending"])
        self.assertTrue(payload.reset_google_state)
        self.assertEqual(payload.mode, SyncMode.GOOGLE_REFRESH)

    def test_google_refresh_accepts_reset_google_state_false(self) -> None:
        payload = SyncRequest(mode=SyncMode.GOOGLE_REFRESH, reset_google_state=False, google_statuses=["pending"])
        self.assertTrue(payload.reset_google_state)

    def test_reset_google_state_rejected_outside_google_refresh(self) -> None:
        with self.assertRaises(ValidationError):
            SyncRequest(mode=SyncMode.FULL, reset_google_state=True)

    def test_google_refresh_requires_google_statuses(self) -> None:
        with self.assertRaises(ValidationError):
            SyncRequest(mode=SyncMode.GOOGLE_REFRESH)

    def test_google_statuses_restricted_to_google_refresh(self) -> None:
        with self.assertRaises(ValidationError):
            SyncRequest(mode=SyncMode.FULL, google_statuses=["pending"])

    def test_google_statuses_normalized_and_deduped(self) -> None:
        payload = SyncRequest(
            mode=SyncMode.GOOGLE_REFRESH,
            google_statuses=[" Pending ", "pending", "FOUND", " ", "not_found"],
        )
        self.assertEqual(payload.google_statuses, ["pending", "found", "not_found"])

    def test_google_statuses_empty_list_is_ignored(self) -> None:
        payload = SyncRequest(mode=SyncMode.FULL, google_statuses=[])
        self.assertIsNone(payload.google_statuses)

    def test_linkedin_statuses_reject_invalid_values(self) -> None:
        with self.assertRaises(ValidationError):
            SyncRequest(mode=SyncMode.LINKEDIN_REFRESH, linkedin_statuses=["pending", "oops"])

    def test_linkedin_statuses_dedupes_and_strips(self) -> None:
        payload = SyncRequest(
            mode=SyncMode.LINKEDIN_REFRESH,
            linkedin_statuses=[" pending ", "PENDING", "found", "", "not_found", "INSUFFICIENT"],
        )
        self.assertEqual(payload.linkedin_statuses, ["pending", "found", "not_found", "insufficient"])

    def test_website_statuses_normalized_and_deduped(self) -> None:
        payload = SyncRequest(
            mode=SyncMode.FULL,
            website_statuses=[" scraped ", "NOT_SCRAPED", "scraped", ""],
        )
        self.assertEqual(payload.website_statuses, ["scraped", "not_scraped"])

    def test_website_statuses_invalid_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            SyncRequest(mode=SyncMode.FULL, website_statuses=["invalid"])

    def test_website_statuses_empty_list_is_ignored(self) -> None:
        payload = SyncRequest(mode=SyncMode.FULL, website_statuses=[])
        self.assertIsNone(payload.website_statuses)


if __name__ == "__main__":
    unittest.main()
