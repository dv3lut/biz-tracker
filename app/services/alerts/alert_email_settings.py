"""Persisted configuration for client alert emails."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models


def get_alert_email_settings(
    session: Session,
    *,
    create_if_missing: bool = True,
) -> models.AlertEmailSettings:
    settings = session.execute(select(models.AlertEmailSettings)).scalar_one_or_none()
    if settings is None or not isinstance(settings, models.AlertEmailSettings):
        settings = models.AlertEmailSettings()
        settings.include_previous_month_day_alerts = False
        if create_if_missing:
            session.add(settings)
            session.flush()
    return settings


def update_alert_email_settings(
    session: Session,
    *,
    include_previous_month_day_alerts: bool | None = None,
) -> models.AlertEmailSettings:
    settings = get_alert_email_settings(session, create_if_missing=True)
    if include_previous_month_day_alerts is not None:
        settings.include_previous_month_day_alerts = include_previous_month_day_alerts
    session.flush()
    return settings
