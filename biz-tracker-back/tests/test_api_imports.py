from __future__ import annotations

import importlib
import sys
from unittest.mock import patch


def test_importing_app_api_has_no_settings_side_effect() -> None:
    sys.modules.pop("app.api", None)

    with (
        patch("app.config.get_settings", side_effect=AssertionError("get_settings() should not run on import")) as mock_get_settings,
        patch(
            "app.services.sync_scheduler.SyncScheduler",
            side_effect=AssertionError("SyncScheduler() should not run on import"),
        ) as mock_scheduler,
    ):
        module = importlib.import_module("app.api")

    assert hasattr(module, "create_app")
    assert mock_get_settings.call_count == 0
    assert mock_scheduler.call_count == 0