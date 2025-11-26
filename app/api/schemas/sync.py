"""Schemas liés aux synchronisations (runs, états, rapports)."""
from __future__ import annotations

from datetime import datetime, date as Date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.services.sync.mode import SyncMode


class SyncRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scope_key: str
    run_type: str
    status: str
    mode: SyncMode
    started_at: datetime
    finished_at: datetime | None
    api_call_count: int
    google_api_call_count: int
    fetched_records: int
    created_records: int
    google_queue_count: int
    google_eligible_count: int
    google_matched_count: int
    google_pending_count: int
    google_immediate_matched_count: int
    google_late_matched_count: int
    updated_records: int
    summary: dict[str, Any] | None = None
    last_cursor: str | None
    query_checksum: str | None
    resumed_from_run_id: UUID | None
    notes: str | None
    total_expected_records: int | None = None
    progress: float | None = None
    estimated_remaining_seconds: float | None = None
    estimated_completion_at: datetime | None = None

    @computed_field
    @property
    def google_enabled(self) -> bool:
        return self.mode != SyncMode.SIRENE_ONLY


class SyncStateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scope_key: str
    last_successful_run_id: UUID | None
    last_cursor: str | None
    cursor_completed: bool
    last_synced_at: datetime | None
    last_total: int | None
    last_treated_max: datetime | None
    last_creation_date: Date | None
    query_checksum: str | None
    updated_at: datetime


class RunEstablishmentSummary(BaseModel):
    siret: str
    name: str | None = None
    code_postal: str | None = None
    libelle_commune: str | None = None
    google_status: str | None = None
    google_place_url: str | None = None
    google_place_id: str | None = None
    created_run_id: UUID | None = None
    first_seen_at: datetime | None = None


class RunUpdatedEstablishmentSummary(RunEstablishmentSummary):
    changed_fields: list[str] = Field(default_factory=list)


class RunSummaryStats(BaseModel):
    new_establishments: int
    updated_establishments: int
    fetched_records: int
    api_call_count: int
    google_total_matches: int
    google_immediate_matches: int
    google_late_matches: int
    google_api_call_count: int
    alerts_created: int
    alerts_sent: int
    page_count: int
    duration_seconds: float


class RunEmailSummary(BaseModel):
    sent: bool
    recipients: list[str] = Field(default_factory=list)
    subject: str | None = None
    reason: str | None = None


class SyncRunReport(BaseModel):
    run: SyncRunOut
    stats: RunSummaryStats
    new_establishments: list[RunEstablishmentSummary]
    updated_establishments: list[RunUpdatedEstablishmentSummary]
    google_immediate_matches: list[RunEstablishmentSummary]
    google_late_matches: list[RunEstablishmentSummary]
    email: RunEmailSummary | None = None


class SyncRequest(BaseModel):
    check_for_updates: bool = Field(
        default=False,
        description="Vérifie le service informations Sirene et annule si aucune mise à jour n'est disponible.",
    )
    mode: SyncMode = Field(
        default=SyncMode.FULL,
        description=(
            "Mode d'exécution: 'full' exécute l'enrichissement Google, 'sirene_only' le désactive, "
            "'google_pending' relance uniquement les établissements jamais enrichis et déclenche les alertes, "
            "'google_refresh' purge les fiches Google et relance une détection complète sans alertes."
        ),
    )


class DeleteRunResult(BaseModel):
    establishments_deleted: int = Field(description="Nombre d'établissements supprimés.")
    alerts_deleted: int = Field(description="Nombre d'alertes supprimées.")
    states_reset: int = Field(description="Nombre d'états de synchronisation remis à zéro.")
    runs_updated: int = Field(description="Nombre de runs mis à jour (liens de reprise supprimés).")
    sync_run_deleted: bool = Field(description="Indique si le run a été supprimé.")


__all__ = [
    "DeleteRunResult",
    "RunEmailSummary",
    "RunEstablishmentSummary",
    "RunSummaryStats",
    "RunUpdatedEstablishmentSummary",
    "SyncRequest",
    "SyncRunOut",
    "SyncRunReport",
    "SyncStateOut",
]
