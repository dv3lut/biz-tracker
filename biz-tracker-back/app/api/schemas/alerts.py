"""Schemas dédiés aux alertes."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    siret: str
    recipients: list[str]
    payload: dict[str, Any]
    created_at: datetime
    sent_at: datetime | None


__all__ = ["AlertOut"]
