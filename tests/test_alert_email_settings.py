"""Tests for alert email settings storage helpers."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.db import models
from app.services.alerts.alert_email_settings import (
    get_alert_email_settings,
    update_alert_email_settings,
)


def test_get_alert_email_settings_returns_default_without_persisting() -> None:
    session = MagicMock()
    session.execute.return_value.scalar_one_or_none.return_value = None

    settings = get_alert_email_settings(session, create_if_missing=False)

    assert isinstance(settings, models.AlertEmailSettings)
    assert settings.include_previous_month_day_alerts is False
    session.add.assert_not_called()


def test_update_alert_email_settings_persists_and_updates_flag() -> None:
    session = MagicMock()
    session.execute.return_value.scalar_one_or_none.return_value = None

    settings = update_alert_email_settings(session, include_previous_month_day_alerts=True)

    assert isinstance(settings, models.AlertEmailSettings)
    assert settings.include_previous_month_day_alerts is True
    session.add.assert_called_once()
    session.flush.assert_called()


def test_get_alert_email_settings_returns_existing_instance() -> None:
    session = MagicMock()
    existing = models.AlertEmailSettings()
    existing.include_previous_month_day_alerts = True
    session.execute.return_value.scalar_one_or_none.return_value = existing

    settings = get_alert_email_settings(session, create_if_missing=True)

    assert settings is existing
    assert settings.include_previous_month_day_alerts is True
    session.add.assert_not_called()
