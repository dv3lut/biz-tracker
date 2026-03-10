from __future__ import annotations

from unittest.mock import patch

from app.observability import log_event


def test_log_event_falls_back_when_settings_are_unavailable() -> None:
    with (
        patch("app.observability.get_settings", side_effect=RuntimeError("settings unavailable")),
        patch("app.observability._OBSERVABILITY_LOGGER.log") as mock_log,
    ):
        log_event("test.event", sample=True)

    mock_log.assert_called_once()
    _, serialized = mock_log.call_args.args
    extra = mock_log.call_args.kwargs["extra"]

    assert '"event":{"name":"test.event"}' in serialized
    assert extra["service_name"] == "biz-tracker-back"
    assert extra["elastic_doc"]["service"]["name"] == "biz-tracker-back"