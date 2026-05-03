"""Tests for sync run cancellation (endpoint + background task)."""
from __future__ import annotations

from unittest import TestCase
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException

from app.api.routers.admin.sync_runs_router import cancel_sync_run
from app.services.sync.cancellation import (
    clear_cancel,
    is_cancel_requested,
    request_cancel,
    SyncCancellationError,
)
from app.services.sync.pages import collect_pages


class CancellationRegistryTests(TestCase):
    def tearDown(self) -> None:
        clear_cancel("test-run-id")

    def test_request_and_detect_cancel(self) -> None:
        self.assertFalse(is_cancel_requested("test-run-id"))
        request_cancel("test-run-id")
        self.assertTrue(is_cancel_requested("test-run-id"))

    def test_clear_cancel(self) -> None:
        request_cancel("test-run-id")
        clear_cancel("test-run-id")
        self.assertFalse(is_cancel_requested("test-run-id"))

    def test_clear_cancel_unknown_id(self) -> None:
        # Should not raise
        clear_cancel("unknown-run-id")


class CancelEndpointTests(TestCase):
    def _make_run(self, status: str = "running"):
        run = MagicMock()
        run.id = uuid4()
        run.status = status
        run.scope_key = "scope_test"
        return run

    def tearDown(self) -> None:
        # Ensure registry is clean after each test
        pass

    @patch("app.api.routers.admin.sync_runs_router.serialize_run")
    @patch("app.api.routers.admin.sync_runs_router.request_cancel")
    @patch("app.api.routers.admin.sync_runs_router.log_event")
    def test_cancel_running_run_succeeds(self, mock_log, mock_request_cancel, mock_serialize_run):
        run = self._make_run("running")
        session = MagicMock()
        session.get.side_effect = lambda model, key: run if model.__name__ == "SyncRun" else None

        mock_serialize_run.return_value = MagicMock()
        result = cancel_sync_run(run.id, session=session)

        mock_request_cancel.assert_called_once_with(str(run.id))
        mock_log.assert_called_once()
        self.assertIsNotNone(result)

    def test_cancel_nonexistent_run_raises_404(self):
        session = MagicMock()
        session.get.return_value = None
        with self.assertRaises(HTTPException) as ctx:
            cancel_sync_run(uuid4(), session=session)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_cancel_finished_run_raises_409(self):
        run = self._make_run("success")
        session = MagicMock()
        session.get.side_effect = lambda model, key: run
        with self.assertRaises(HTTPException) as ctx:
            cancel_sync_run(run.id, session=session)
        self.assertEqual(ctx.exception.status_code, 409)

    def test_cancel_failed_run_raises_409(self):
        run = self._make_run("failed")
        session = MagicMock()
        session.get.side_effect = lambda model, key: run
        with self.assertRaises(HTTPException) as ctx:
            cancel_sync_run(run.id, session=session)
        self.assertEqual(ctx.exception.status_code, 409)


class CollectPagesCancellationTests(TestCase):
    def test_cancellation_detected_at_first_page(self):
        run_id = str(uuid4())
        run = MagicMock()
        run.id = run_id
        run.scope_key = "scope"
        run.api_call_count = 0
        run.fetched_records = 0
        run.created_records = 0
        run.updated_records = 0

        state = MagicMock()
        state.last_creation_date = None

        context = MagicMock()
        context.run = run
        context.state = state

        collector = MagicMock()
        collector._settings.sirene.page_size = 100

        request_cancel(run_id)
        try:
            with self.assertRaises(SyncCancellationError):
                collect_pages(
                    collector,
                    context,
                    query="q",
                    champs="champs",
                    cursor_value="*",
                    tri="tri",
                    months_back=3,
                    since_creation=None,
                    creation_range=None,
                    persist_state=False,
                )
        finally:
            clear_cancel(run_id)
