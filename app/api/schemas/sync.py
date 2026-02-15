"""Schemas liés aux synchronisations (runs, états, rapports)."""
from __future__ import annotations

from datetime import datetime, date as Date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from app.services.sync.mode import SyncMode
from app.services.sync.replay_reference import DayReplayReference, DEFAULT_DAY_REPLAY_REFERENCE
from app.utils.dates import utcnow
from app.utils.naf import normalize_naf_code


class SyncRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scope_key: str
    run_type: str
    status: str
    mode: SyncMode
    replay_for_date: Date | None = Field(default=None)
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
    # LinkedIn enrichment progress
    linkedin_queue_count: int = 0
    linkedin_searched_count: int = 0
    linkedin_found_count: int = 0
    linkedin_not_found_count: int = 0
    linkedin_error_count: int = 0
    # Website scraping progress
    website_scrape_count: int = 0
    website_scrape_success_count: int = 0
    updated_records: int
    summary: dict[str, Any] | None = None
    last_cursor: str | None
    query_checksum: str | None
    resumed_from_run_id: UUID | None
    notes: str | None
    target_naf_codes: list[str] | None = Field(
        default=None,
        description="Liste optionnelle des codes NAF ciblés par ce run.",
    )
    target_client_ids: list[UUID] | None = Field(
        default=None,
        description="Clients explicitement ciblés lors de ce run (mode 'day_replay' uniquement).",
    )
    notify_admins: bool = Field(
        default=True,
        description="Indique si les alertes de ce run sont envoyées aux administrateurs.",
    )
    day_replay_force_google: bool = Field(
        default=False,
        description="Indique si les appels Google ont été forcés lors d'un rejeu.",
    )
    day_replay_reference: DayReplayReference = Field(
        default=DEFAULT_DAY_REPLAY_REFERENCE,
        description="Source de vérité utilisée pour rejouer une journée (date de création ou d'insertion).",
    )
    months_back: int | None = Field(
        default=None,
        description="Nombre de mois dans le passé à inclure dans la collecte (None = jour courant uniquement).",
    )
    total_expected_records: int | None = None
    progress: float | None = None
    estimated_remaining_seconds: float | None = None
    estimated_completion_at: datetime | None = None

    @computed_field
    @property
    def google_enabled(self) -> bool:
        return self.mode != SyncMode.SIRENE_ONLY

    @computed_field
    @property
    def linkedin_enabled(self) -> bool:
        return self.mode in {SyncMode.FULL, SyncMode.LINKEDIN_PENDING, SyncMode.LINKEDIN_REFRESH}


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
            "Mode d'exécution: 'full' exécute l'enrichissement Google et LinkedIn, 'sirene_only' le désactive, "
            "'google_refresh' relance Google sur les établissements filtrés par statuts, "
            "'linkedin_pending' relance uniquement les dirigeants jamais enrichis par LinkedIn, "
            "'linkedin_refresh' relance une détection LinkedIn sur tous les dirigeants, "
            "'day_replay' rejoue une journée complète en limitant les alertes aux administrateurs, "
            "'website_scrape' scrape les sites web des fiches Google."
        ),
    )
    reset_google_state: bool = Field(
        default=False,
        description=(
            "Disponible uniquement en mode 'google_refresh' (forcé à true) : réinitialise les données Google "
            "avant relance (reset biz-by-biz)."
        ),
    )
    replay_for_date: Date | None = Field(
        default=None,
        description="Limite la collecte aux établissements créés à la date indiquée (mode 'day_replay' uniquement).",
    )
    naf_codes: list[str] | None = Field(
        default=None,
        description="Filtre optionnel de codes NAF (ex: 5610A) à rejouer quel que soit le mode.",
    )
    target_client_ids: list[UUID] | None = Field(
        default=None,
        description="Limiter l'envoi des alertes à une liste précise de clients (mode 'day_replay').",
    )
    linkedin_statuses: list[str] | None = Field(
        default=None,
        description=(
            "Statuts LinkedIn à relancer lors d'un run LinkedIn-only (pending, found, not_found, error, insufficient)."
        ),
    )
    google_statuses: list[str] | None = Field(
        default=None,
        description=(
            "Statuts Google à relancer lors d'un run Google-only (ex: pending, found, not_found, insufficient, type_mismatch)."
        ),
    )
    website_statuses: list[str] | None = Field(
        default=None,
        description=(
            "Statuts de scraping site web à cibler (scraped, not_scraped). "
            "Mode 'website_scrape' uniquement."
        ),
    )
    notify_admins: bool = Field(
        default=True,
        description="Autorise l'envoi des alertes administrateurs lors d'un rejeu (mode 'day_replay').",
    )
    force_google_replay: bool = Field(
        default=False,
        description="Force les appels Google lors d'un rejeu même si des fiches existent déjà.",
    )
    replay_reference: DayReplayReference = Field(
        default=DEFAULT_DAY_REPLAY_REFERENCE,
        description=(
            "Contrôle le critère de rejeu: 'creation_date' récupère les établissements par date de création, "
            "'insertion_date' par date d'insertion en base (mode 'day_replay')."
        ),
    )
    months_back: int | None = Field(
        default=None,
        ge=1,
        le=24,
        description=(
            "Nombre de mois dans le passé à inclure dans la collecte Sirene. "
            "Si non spécifié, seul le jour courant est synchronisé (synchro incrémentale standard)."
        ),
    )

    @field_validator("linkedin_statuses")
    @classmethod
    def validate_linkedin_statuses(cls, value: list[str] | None) -> list[str] | None:
        if not value:
            return None
        allowed = {"pending", "found", "not_found", "error", "insufficient"}
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in value:
            candidate = (raw or "").strip().lower()
            if not candidate:
                continue
            if candidate not in allowed:
                raise ValueError("Statuts LinkedIn acceptés: pending, found, not_found, error, insufficient.")
            if candidate in seen:
                continue
            seen.add(candidate)
            normalized.append(candidate)
        return normalized or None

    @field_validator("google_statuses")
    @classmethod
    def validate_google_statuses(cls, value: list[str] | None) -> list[str] | None:
        if not value:
            return None
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in value:
            candidate = (raw or "").strip().lower()
            if not candidate:
                continue
            if candidate in seen:
                continue
            seen.add(candidate)
            normalized.append(candidate)
        return normalized or None

    @field_validator("website_statuses")
    @classmethod
    def validate_website_statuses(cls, value: list[str] | None) -> list[str] | None:
        if not value:
            return None
        allowed = {"scraped", "not_scraped"}
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in value:
            candidate = (raw or "").strip().lower()
            if not candidate:
                continue
            if candidate not in allowed:
                raise ValueError("Statuts site web acceptés: scraped, not_scraped.")
            if candidate in seen:
                continue
            seen.add(candidate)
            normalized.append(candidate)
        return normalized or None

    @field_validator("naf_codes")
    @classmethod
    def validate_naf_codes(cls, value: list[str] | None) -> list[str] | None:
        if not value:
            return None
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in value:
            candidate = (raw or "").strip().upper().replace(" ", "")
            normalized_code = normalize_naf_code(candidate)
            if not normalized_code:
                raise ValueError("Chaque code NAF doit contenir 4 chiffres suivis d'une lettre (ex: 56.10A).")
            if normalized_code in seen:
                continue
            seen.add(normalized_code)
            normalized.append(normalized_code)
            if len(normalized) > 25:
                raise ValueError("Maximum 25 codes NAF ciblés par synchronisation.")
        return normalized or None

    @field_validator("target_client_ids")
    @classmethod
    def validate_target_clients(cls, value: list[UUID] | None) -> list[UUID] | None:
        if not value:
            return None
        normalized: list[UUID] = []
        seen: set[str] = set()
        for raw in value:
            try:
                candidate = UUID(str(raw))
            except (TypeError, ValueError) as exc:  # noqa: PERF203 - explicit error for clarity
                raise ValueError("Chaque client ciblé doit être un UUID valide.") from exc
            candidate_key = str(candidate)
            if candidate_key in seen:
                continue
            seen.add(candidate_key)
            normalized.append(candidate)
            if len(normalized) > 50:
                raise ValueError("Maximum 50 clients ciblés par synchronisation.")
        return normalized or None

    @model_validator(mode="after")
    def validate_replay_settings(self) -> "SyncRequest":
        if "reset_google_state" in self.model_fields_set and self.mode is not SyncMode.GOOGLE_REFRESH:
            raise ValueError("Le paramètre reset_google_state est disponible uniquement pour les modes Google-only.")
        if self.mode is SyncMode.GOOGLE_REFRESH and not self.google_statuses:
            raise ValueError("Merci de sélectionner au moins un statut Google à relancer.")
        if self.google_statuses and self.mode is not SyncMode.GOOGLE_REFRESH:
            raise ValueError("Les statuts Google sont disponibles uniquement en mode 'google_refresh'.")
        if self.mode is SyncMode.GOOGLE_REFRESH:
            self.reset_google_state = True
        if self.mode.requires_replay_date and not self.replay_for_date:
            raise ValueError("Une date est requise pour rejouer une journée.")
        if self.replay_for_date and not self.mode.requires_replay_date:
            raise ValueError("La date de rejeu n'est disponible qu'en mode 'day_replay'.")
        if self.replay_for_date and self.replay_for_date > utcnow().date():
            raise ValueError("Impossible de rejouer une journée future.")
        if self.target_client_ids and self.mode is not SyncMode.DAY_REPLAY:
            raise ValueError("Le ciblage de clients est disponible uniquement en mode 'day_replay'.")
        if self.notify_admins is False and self.mode is not SyncMode.DAY_REPLAY:
            raise ValueError("La désactivation des notifications admin est réservée au mode 'day_replay'.")
        if self.force_google_replay and self.mode is not SyncMode.DAY_REPLAY:
            raise ValueError("Le forçage des appels Google est disponible uniquement en mode 'day_replay'.")
        if self.replay_reference is not DEFAULT_DAY_REPLAY_REFERENCE and self.mode is not SyncMode.DAY_REPLAY:
            raise ValueError("Le choix de la référence de rejeu est réservé au mode 'day_replay'.")
        return self


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
