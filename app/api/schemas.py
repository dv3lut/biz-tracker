"""Pydantic response schemas for the API layer."""
from __future__ import annotations

from datetime import datetime, date as Date
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


class DailyMetricPoint(BaseModel):
    date: Date = Field(description="Jour de référence.")
    value: int = Field(description="Valeur agrégée pour la journée.")


class DailyApiMetricPoint(DailyMetricPoint):
    run_count: int = Field(description="Nombre de runs terminés ce jour-là.")
    google_api_call_count: int = Field(default=0, description="Nombre d'appels Google réalisés durant la journée.")


class DailyAlertMetricPoint(BaseModel):
    date: Date = Field(description="Jour de référence.")
    created: int = Field(description="Alertes créées durant la journée.")
    sent: int = Field(description="Alertes réellement envoyées durant la journée.")


class DailyRunOutcomePoint(BaseModel):
    date: Date = Field(description="Jour de référence.")
    created_records: int = Field(description="Établissements créés durant la journée.")
    updated_records: int = Field(description="Établissements mis à jour durant la journée.")


class DailyGoogleStatusPoint(BaseModel):
    date: Date = Field(description="Jour de référence.")
    immediate_matches: int = Field(description="Fiches Google trouvées immédiatement pour la journée.")
    late_matches: int = Field(description="Fiches Google rattrapées sur des établissements existants pour la journée.")
    not_found: int = Field(description="Établissements sans fiche Google trouvée durant la journée.")
    insufficient: int = Field(description="Établissements avec identité insuffisante pour Google durant la journée.")
    pending: int = Field(description="Établissements encore en file d'attente Google durant la journée.")
    other: int = Field(description="Statuts Google inattendus durant la journée.")


class GoogleStatusBreakdown(BaseModel):
    found: int = Field(default=0, description="Fiches Google identifiées.")
    not_found: int = Field(default=0, description="Recherches Google sans succès.")
    insufficient: int = Field(default=0, description="Identités insuffisantes pour tenter une recherche Google.")
    pending: int = Field(default=0, description="Établissements en attente d'une recherche Google.")
    other: int = Field(default=0, description="Statuts inattendus ou transitoires.")


class DashboardRunBreakdown(BaseModel):
    run_id: UUID = Field(description="Identifiant du run analysé.")
    started_at: datetime = Field(description="Horodatage de démarrage du run.")
    created_records: int = Field(description="Nombre de nouveaux établissements créés par le run.")
    updated_records: int = Field(description="Nombre d'établissements existants mis à jour durant le run.")
    api_call_count: int = Field(description="Nombre d'appels API effectués par le run.")
    google_api_call_count: int = Field(description="Nombre d'appels Google effectués par le run.")
    google_found: int = Field(description="Nouveaux établissements associés à une fiche Google.")
    google_found_late: int = Field(description="Établissements existants enrichis lors d'un run ultérieur.")
    google_not_found: int = Field(description="Nouveaux établissements sans fiche Google détectée.")
    google_insufficient: int = Field(description="Nouveaux établissements sans identité exploitable pour Google.")
    google_pending: int = Field(description="Nouveaux établissements encore en file d'attente Google.")
    google_other: int = Field(description="Nouveaux établissements avec un statut Google inattendu.")
    alerts_created: int = Field(description="Alertes créées pendant le run.")
    alerts_sent: int = Field(description="Alertes envoyées pendant le run.")


class DashboardMetrics(BaseModel):
    latest_run: SyncRunOut | None = Field(description="Dernier run terminé avec ses métadonnées enrichies.")
    latest_run_breakdown: DashboardRunBreakdown | None = Field(description="Répartition détaillée des résultats pour le dernier run.")
    daily_new_businesses: list[DailyMetricPoint] = Field(default_factory=list, description="Volume de nouveaux établissements par jour.")
    daily_api_calls: list[DailyApiMetricPoint] = Field(default_factory=list, description="Nombre d'appels API par jour avec le nombre de runs.")
    daily_alerts: list[DailyAlertMetricPoint] = Field(default_factory=list, description="Alertes créées et envoyées par jour.")
    daily_run_outcomes: list[DailyRunOutcomePoint] = Field(default_factory=list, description="Créations et mises à jour quotidiennes.")
    daily_google_statuses: list[DailyGoogleStatusPoint] = Field(default_factory=list, description="Répartition quotidienne des statuts Google.")
    google_status_breakdown: GoogleStatusBreakdown = Field(description="Répartition globale des statuts Google.")
    establishment_status_breakdown: dict[str, int] = Field(default_factory=dict, description="Répartition des établissements par état administratif.")


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


class ClientRecipientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    created_at: datetime


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    start_date: Date
    end_date: Date | None
    emails_sent_count: int
    last_email_sent_at: datetime | None
    created_at: datetime
    updated_at: datetime
    recipients: list[ClientRecipientOut]


class ClientCreate(BaseModel):
    name: str
    start_date: Date
    end_date: Date | None = None
    recipients: list[str] = Field(default_factory=list, description="Liste d'adresses e-mail associées au client.")


class ClientUpdate(BaseModel):
    name: str | None = None
    start_date: Date | None = None
    end_date: Date | None = None
    recipients: list[str] | None = Field(default=None, description="Remplace la liste complète des destinataires lorsqu'elle est fournie.")


class AdminEmailConfig(BaseModel):
    recipients: list[str] = Field(default_factory=list, description="Destinataires administrateurs du résumé de synchro.")


class AdminEmailConfigUpdate(BaseModel):
    recipients: list[str] = Field(default_factory=list, description="Nouvelle liste d'adresses e-mail admin.")


class SyncRequest(BaseModel):
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
    date_creation: Date | None
    date_debut_activite: Date | None
    first_seen_at: datetime
    last_seen_at: datetime
    updated_at: datetime
    created_run_id: UUID | None
    last_run_id: UUID | None
    google_place_id: str | None
    google_place_url: str | None
    google_last_checked_at: datetime | None
    google_last_found_at: datetime | None
    google_check_status: str


class DeleteRunResult(BaseModel):
    establishments_deleted: int = Field(description="Nombre d'établissements supprimés.")
    alerts_deleted: int = Field(description="Nombre d'alertes supprimées.")
    states_reset: int = Field(description="Nombre d'états de synchronisation remis à zéro.")
    runs_updated: int = Field(description="Nombre de runs mis à jour (liens de reprise supprimés).")
    sync_run_deleted: bool = Field(description="Indique si le run a été supprimé.")


class EmailTestRequest(BaseModel):
    subject: str | None = Field(
        default=None,
        description="Sujet personnalisé. Utilise un sujet par défaut si omis.",
    )
    body: str | None = Field(
        default=None,
        description="Corps du message en texte brut.",
    )
    recipients: list[str] | None = Field(
        default=None,
        description="Destinataires spécifiques pour ce test (sinon configuration par défaut).",
    )


class EmailTestResponse(BaseModel):
    sent: bool = Field(description="Indique si la demande d'envoi a été effectuée.")
    provider: str = Field(description="Preset SMTP actif.")
    subject: str = Field(description="Sujet utilisé pour l'envoi.")
    recipients: list[str] = Field(description="Destinataires ciblés par l'envoi.")


class ManualGoogleCheckResponse(BaseModel):
    found: bool = Field(description="Indique si une page Google a été identifiée.")
    email_sent: bool = Field(description="Indique si un e-mail a été envoyé suite à la détection.")
    message: str = Field(description="Résumé textuel du résultat.")
    place_id: str | None = Field(default=None, description="Identifiant Google Places si présent.")
    place_url: str | None = Field(default=None, description="URL Google Maps ou site associé.")
    check_status: str = Field(description="Statut Google associé à l'établissement.")
    establishment: EstablishmentOut = Field(description="Représentation de l'établissement après mise à jour.")


class EstablishmentDetailOut(EstablishmentOut):
    nic: str | None
    denomination_unite_legale: str | None
    denomination_usuelle_unite_legale: str | None
    denomination_usuelle_etablissement: str | None
    enseigne1: str | None
    enseigne2: str | None
    enseigne3: str | None
    categorie_juridique: str | None
    categorie_entreprise: str | None
    tranche_effectifs: str | None
    annee_effectifs: int | None
    nom_usage: str | None
    nom: str | None
    prenom1: str | None
    prenom2: str | None
    prenom3: str | None
    prenom4: str | None
    prenom_usuel: str | None
    pseudonyme: str | None
    sexe: str | None
    date_dernier_traitement_etablissement: datetime | None
    date_dernier_traitement_unite_legale: datetime | None
    complement_adresse: str | None
    numero_voie: str | None
    indice_repetition: str | None
    type_voie: str | None
    libelle_voie: str | None
    distribution_speciale: str | None
    libelle_commune_etranger: str | None
    code_commune: str | None
    code_cedex: str | None
    libelle_cedex: str | None
    code_pays: str | None
    libelle_pays: str | None