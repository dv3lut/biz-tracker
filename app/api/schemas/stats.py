"""Schemas d'agrégation et indicateurs de dashboard."""
from __future__ import annotations

from datetime import datetime, date as Date
from uuid import UUID

from pydantic import BaseModel, Field

from app.api.schemas.alerts import AlertOut
from app.api.schemas.naf import NafCategoryStats
from app.api.schemas.sync import SyncRunOut


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


class GoogleListingAgeBreakdown(BaseModel):
    recent_creation: int = Field(default=0, description="Nombre d'établissements avec fiche créée récemment.")
    recent_creation_missing_contact: int = Field(
        default=0,
        description="Nombre d'établissements dont la fiche semble récente mais sans canal de contact exploitable.",
    )
    not_recent_creation: int = Field(default=0, description="Nombre d'établissements dont la fiche semble antérieure à l'ouverture (création ancienne).")
    unknown: int = Field(default=0, description="Nombre d'établissements sans information d'âge de fiche.")


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
    listing_recent: int = Field(description="Fiches probablement créées lors de l'ouverture.")
    listing_recent_missing_contact: int = Field(
        description="Fiches récentes dépourvues d'information de contact fiable."
    )
    listing_not_recent: int = Field(description="Fiches déjà existantes avant la création recensée (création ancienne).")
    listing_unknown: int = Field(description="Fiches sans information d'âge sur le run.")
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
    listing_age_breakdown: GoogleListingAgeBreakdown = Field(description="Répartition globale des fiches Google par ancienneté relative.")
    establishment_status_breakdown: dict[str, int] = Field(default_factory=dict, description="Répartition des établissements par état administratif.")
    naf_category_breakdown: list[NafCategoryStats] = Field(
        default_factory=list,
        description="Répartition des établissements par catégorie et sous-catégorie NAF.",
    )


class NafAnalyticsTimePoint(BaseModel):
    """Point de données temporel pour une granularité donnée (jour/semaine/mois)."""

    period: str = Field(description="Période de référence (ex: 2026-02-08, 2026-W06, 2026-02).")
    total_fetched: int = Field(default=0, description="Établissements récupérés de l'API SIRENE.")
    non_diffusible: int = Field(default=0, description="Établissements non diffusibles (non cherchables).")
    insufficient_info: int = Field(default=0, description="Établissements sans identité exploitable.")
    google_found: int = Field(default=0, description="Fiches Google trouvées.")
    google_not_found: int = Field(default=0, description="Recherche Google sans succès.")
    google_pending: int = Field(default=0, description="En attente de recherche Google.")
    listing_recent: int = Field(default=0, description="Fiches Google récentes.")
    listing_recent_missing_contact: int = Field(default=0, description="Fiches récentes sans contact.")
    listing_not_recent: int = Field(default=0, description="Fiches anciennes / reprise.")
    individual_count: int = Field(default=0, description="Établissements en entreprise individuelle.")
    linkedin_found: int = Field(default=0, description="Profils LinkedIn trouvés.")
    linkedin_not_found: int = Field(default=0, description="Profils LinkedIn non trouvés.")
    linkedin_pending: int = Field(default=0, description="En attente de recherche LinkedIn.")
    linkedin_total_directors: int = Field(default=0, description="Total dirigeants rattachés.")
    linkedin_skipped_nd: int = Field(default=0, description="Dirigeants non diffusibles (LinkedIn skipped_nd).")
    alerts_created: int = Field(default=0, description="Alertes générées.")


class NafAnalyticsItem(BaseModel):
    """Statistiques d'un code NAF ou d'une catégorie avec séries temporelles."""

    id: str = Field(description="Identifiant du NAF ou de la catégorie.")
    code: str | None = Field(default=None, description="Code NAF (null si catégorie agrégée).")
    name: str = Field(description="Libellé du NAF ou de la catégorie.")
    totals: NafAnalyticsTimePoint = Field(description="Totaux cumulés sur la période.")
    time_series: list[NafAnalyticsTimePoint] = Field(
        default_factory=list, description="Séries temporelles par période."
    )
    creation_series: list[dict[str, object]] = Field(
        default_factory=list,
        description="Série temporelle des créations d'établissements (date de création) pour cet item.",
    )


class NafAnalyticsResponse(BaseModel):
    """Réponse complète de l'endpoint d'analytics NAF."""

    granularity: str = Field(description="Granularité appliquée: day, week, month.")
    start_date: Date = Field(description="Date de début de la fenêtre.")
    end_date: Date = Field(description="Date de fin de la fenêtre.")
    aggregation: str = Field(description="Mode d'agrégation: naf, category, subcategory.")
    items: list[NafAnalyticsItem] = Field(default_factory=list, description="Données par NAF/catégorie.")
    global_totals: NafAnalyticsTimePoint = Field(description="Totaux globaux tous NAF confondus.")
    creation_series: list[dict[str, object]] = Field(
        default_factory=list,
        description="Série temporelle des établissements par date de création (donnée établissement).",
    )


__all__ = [
    "DailyAlertMetricPoint",
    "DailyApiMetricPoint",
    "DailyGoogleStatusPoint",
    "DailyMetricPoint",
    "DailyRunOutcomePoint",
    "DashboardMetrics",
    "DashboardRunBreakdown",
    "GoogleListingAgeBreakdown",
    "GoogleStatusBreakdown",
    "NafAnalyticsItem",
    "NafAnalyticsResponse",
    "NafAnalyticsTimePoint",
    "StatsSummary",
]
