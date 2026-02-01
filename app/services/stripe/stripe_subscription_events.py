"""Helpers to persist subscription change events."""
from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy.orm import Session

from app.db import models


def record_subscription_event(
    session: Session,
    *,
    client: models.Client,
    stripe_subscription_id: str | None,
    event_type: str,
    from_plan_key: str | None,
    to_plan_key: str | None,
    from_category_ids: Iterable[str] | None,
    to_category_ids: Iterable[str] | None,
    effective_at: datetime | None,
    source: str | None,
) -> models.ClientSubscriptionEvent:
    event = models.ClientSubscriptionEvent(
        client_id=client.id,
        stripe_subscription_id=stripe_subscription_id,
        event_type=event_type,
        from_plan_key=from_plan_key,
        to_plan_key=to_plan_key,
        from_category_ids=list(from_category_ids) if from_category_ids is not None else None,
        to_category_ids=list(to_category_ids) if to_category_ids is not None else None,
        effective_at=effective_at,
        source=source,
    )
    session.add(event)
    session.flush()
    return event
