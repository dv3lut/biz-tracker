"""Data structures shared by synchronization services."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from sqlalchemy.orm import Session

from app.clients.sirene_client import SireneClient
from app.config import Settings
from app.db import models


@dataclass
class SyncContext:
    """Holds per-run state shared across sync helpers."""

    session: Session
    run: models.SyncRun
    state: models.SyncState
    client: SireneClient
    settings: Settings


@dataclass
class UpdatedEstablishmentInfo:
    """Track changed establishments with their modified fields."""

    establishment: models.Establishment
    changed_fields: list[str]


@dataclass
class SyncResult:
    """Aggregate the outcome of a synchronization run."""

    last_treated: datetime | None
    new_establishments: list[models.Establishment]
    new_establishment_payloads: list[dict[str, object]]
    updated_establishments: list[UpdatedEstablishmentInfo]
    updated_payloads: list[dict[str, object]]
    google_immediate_matches: list[models.Establishment]
    google_late_matches: list[models.Establishment]
    google_match_payloads: list[dict[str, object]]
    alerts: list[models.Alert]
    alert_payloads: list[dict[str, object]]
    page_count: int
    duration_seconds: float
    google_queue_count: int
    google_eligible_count: int
    google_matched_count: int
    google_pending_count: int
    google_api_call_count: int
    alerts_sent_count: int


EstablishmentSequence = Sequence[models.Establishment]
