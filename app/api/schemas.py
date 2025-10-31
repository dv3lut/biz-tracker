"""Pydantic response schemas for the API layer."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SyncRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scope_key: str
    run_type: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    api_call_count: int
    fetched_records: int
    created_records: int
    last_cursor: str | None
    query_checksum: str | None
    resumed_from_run_id: UUID | None
    notes: str | None
    max_records: int | None
    total_expected_records: int | None = None
    progress: float | None = None
    estimated_remaining_seconds: float | None = None
    estimated_completion_at: datetime | None = None


class SyncStateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scope_key: str
    last_successful_run_id: UUID | None
    last_cursor: str | None
    cursor_completed: bool
    last_synced_at: datetime | None
    last_total: int | None
    last_treated_max: datetime | None
    query_checksum: str | None
    updated_at: datetime


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    siret: str
    recipients: list[str]
    payload: dict[str, Any]
    created_at: datetime
    sent_at: datetime | None


class StatsSummary(BaseModel):
    total_establishments: int
    total_alerts: int
    last_full_run: SyncRunOut | None
    last_incremental_run: SyncRunOut | None
    last_alert: AlertOut | None


class SyncRequest(BaseModel):
    resume: bool = True
    max_records: int | None = Field(default=None, ge=1, description="Nombre maximal d'enregistrements à traiter.")