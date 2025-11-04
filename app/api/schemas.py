"""Pydantic response schemas for the API layer."""
from __future__ import annotations

from datetime import datetime, date
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
    last_run: SyncRunOut | None
    last_alert: AlertOut | None
    database_size_pretty: str


class SyncRequest(BaseModel):
    resume: bool = True
    check_for_updates: bool = Field(
        default=False,
        description="Vérifie le service informations Sirene et annule si aucune mise à jour n'est disponible.",
    )


class EstablishmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    siret: str
    siren: str
    name: str | None
    naf_code: str | None
    naf_libelle: str | None
    etat_administratif: str | None
    code_postal: str | None
    libelle_commune: str | None
    date_creation: date | None
    date_debut_activite: date | None
    first_seen_at: datetime
    last_seen_at: datetime
    updated_at: datetime
    created_run_id: UUID | None
    last_run_id: UUID | None


class DeleteRunResult(BaseModel):
    establishments_deleted: int = Field(description="Nombre d'établissements supprimés.")
    alerts_deleted: int = Field(description="Nombre d'alertes supprimées.")
    states_reset: int = Field(description="Nombre d'états de synchronisation remis à zéro.")
    runs_updated: int = Field(description="Nombre de runs mis à jour (liens de reprise supprimés).")
    sync_run_deleted: bool = Field(description="Indique si le run a été supprimé.")