"""Application settings loaded from the environment."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Dict, List, Literal, Optional
from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.sources import PydanticBaseSettingsSource
from pydantic_settings.sources.types import ForceDecode, NoDecode
from sqlalchemy.engine import URL, make_url


class SireneSettings(BaseModel):
    api_base_url: str = Field(
        default="https://api.insee.fr/api-sirene/3.11",
        description="Base URL for the Sirene API endpoints.",
    )
    api_token: str = Field(description="Bearer token for authenticating against the Sirene API.")
    max_calls_per_minute: int = Field(
        default=30,
        ge=1,
        description="Maximal number of API calls per minute, enforced via a software rate limiter.",
    )
    page_size: int = Field(default=1000, ge=1, le=1000)
    request_timeout_seconds: int = Field(default=30, ge=1)
    current_period_date: str = Field(
        default="2100-01-01",
        description=(
            "Date passed to Sirene searches so historized fields such as etatAdministratifEtablissement are "
            "evaluated on their current value."
        ),
    )


class DatabaseSettings(BaseModel):
    host: str = Field(default="localhost", description="Hostname for the PostgreSQL server.")
    port: int = Field(default=5432, ge=1, le=65535, description="Port for the PostgreSQL server.")
    name: str = Field(default="biz_tracker_db", description="Database name used by the application.")
    user: str = Field(default="sirene_user", description="Database user for connections.")
    password: str = Field(default="sirene_password", description="Database user password.")
    url: Optional[str] = Field(
        default=None,
        description="Optional SQLAlchemy URL overriding host-based configuration when provided.",
    )
    echo: bool = Field(default=False)
    pool_size: int = Field(default=5, ge=1)
    pool_timeout: int = Field(default=30, ge=1)

    @property
    def sqlalchemy_url(self) -> URL:
        if self.url:
            return make_url(self.url)

        return URL.create(
            "postgresql+psycopg",
            username=self.user or None,
            password=self.password or None,
            host=self.host,
            port=self.port,
            database=self.name,
        )


class EmailSettings(BaseModel):
    provider: Literal["custom", "mailhog", "mailjet"] = Field(
        default="custom",
        description="Preset de configuration SMTP (custom, mailhog, mailjet).",
    )
    enabled: bool = Field(default=False)
    smtp_host: Optional[str] = None
    smtp_port: int = Field(default=587, ge=1)
    smtp_timeout_seconds: int = Field(default=10, ge=1)
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    use_tls: bool = Field(default=True)
    from_address: Optional[str] = None

    @field_validator("smtp_host", "smtp_username", "smtp_password", "from_address", mode="before")
    @classmethod
    def _normalize_nullable_field(cls, value: object) -> Optional[str | object]:
        if value is None:
            return None
        if isinstance(value, str):
            trimmed = value.strip()
            if not trimmed or trimmed.lower() in {"null", "none"}:
                return None
            return trimmed
        return value

    @model_validator(mode="after")
    def _apply_provider_defaults(self) -> "EmailSettings":
        if self.provider == "mailhog":
            self.smtp_host = self.smtp_host or "localhost"
            self.smtp_port = 1025
            self.use_tls = False
        elif self.provider == "mailjet":
            self.smtp_host = self.smtp_host or "in-v3.mailjet.com"
            self.smtp_port = 587
            self.use_tls = True
        return self


class GoogleSettings(BaseModel):
    api_key: Optional[str] = Field(default=None, description="API key used to call Google Places APIs.")
    find_place_url: str = Field(
        default="https://maps.googleapis.com/maps/api/place/findplacefromtext/json",
        description="Endpoint for the Find Place from Text API.",
    )
    place_details_url: str = Field(
        default="https://maps.googleapis.com/maps/api/place/details/json",
        description="Endpoint for the Place Details API.",
    )
    max_calls_per_minute: int = Field(
        default=600,
        ge=1,
        description="Maximum number of Google Places API calls per minute (both search and details combined).",
    )
    language: str = Field(default="fr", description="Language hint provided to Google Places.")
    recheck_hours: int = Field(
        default=24,
        ge=1,
        description="Delay (in hours) before retrying establishments without an associated Google place.",
    )
    daily_retry_limit: int = Field(
        default=20000,
        ge=1,
        description="Maximum number of establishments rechecked for Google data during a single sync run.",
    )
    category_similarity_threshold: float = Field(
        default=0.72,
        ge=0.0,
        le=1.0,
        description="Seuil de similarité minimale entre les mots-clés NAF et les types Google retournés par Google Places.",
    )
    website_scrape_enabled: bool = Field(
        default=True,
        description=(
            "Active le scraping des sites web découverts via Google Places. "
            "Mettre à false pour désactiver le scraping tout en conservant l'enrichissement Google."
        ),
    )

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    @field_validator("api_key", mode="before")
    @classmethod
    def _normalize_api_key(cls, value: object) -> Optional[str | object]:
        if value is None:
            return None
        if isinstance(value, str):
            trimmed = value.strip()
            if not trimmed or trimmed.lower() in {"null", "none"}:
                return None
            return trimmed
        return value


class SyncSettings(BaseModel):
    scope_key: str = Field(
        default="default",
        validation_alias=AliasChoices("scope_key", "full_scope_key"),
        description="Scope identifier used to persist sync state and runs.",
    )
    minimum_delay_minutes: int = Field(
        default=1440,
        description="Default minimum delay between sync runs when no guidance is provided by the informations service.",
    )
    auto_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("auto_enabled", "auto_incremental_enabled"),
        description="Enable the background scheduler that can trigger sync runs automatically.",
    )
    auto_poll_minutes: int = Field(
        default=15,
        ge=1,
        validation_alias=AliasChoices("auto_poll_minutes", "auto_incremental_poll_minutes"),
        description="Polling interval (in minutes) for the background sync scheduler.",
    )
    auto_retry_max_attempts: int = Field(
        default=4,
        ge=1,
        description="Nombre maximum de tentatives automatiques (échec technique ou run vide) par journée.",
    )
    incremental_lookback_months: int = Field(
        default=3,
        ge=0,
        description="Nombre de mois en arrière à vérifier lors des synchros incrémentales auto pour capturer les créations administratives passées.",
    )


class AnnuaireSettings(BaseModel):
    api_base_url: str = Field(
        default="https://recherche-entreprises.api.gouv.fr",
        description="Base URL for the Recherche Entreprises API (dirigeants & unité légale).",
    )
    request_timeout_seconds: int = Field(default=15, ge=1)
    max_workers: int = Field(
        default=8,
        ge=1,
        le=50,
        description="Number of parallel workers for annuaire enrichment during sync.",
    )
    max_calls_per_second: int = Field(
        default=7,
        ge=1,
        le=50,
        description="Max annuaire API calls per second (rate limit).",
    )
    max_retries: int = Field(default=3, ge=1)
    backoff_factor: float = Field(default=1.0, ge=0.1)
    enabled: bool = Field(
        default=True,
        description="Enable director/legal-unit enrichment from the annuaire API.",
    )


class ElasticsearchLoggingSettings(BaseModel):
    enabled: bool = Field(default=False)
    hosts: List[str] = Field(default_factory=lambda: ["http://localhost:9200"])
    index_prefix: str = Field(default="biz-tracker-observability")
    environment: str = Field(default="local")
    verify_certs: bool = Field(default=False)
    username: Optional[str] = None
    password: Optional[str] = None
    timeout_seconds: int = Field(default=10, ge=1)

    @field_validator("enabled", "verify_certs", mode="before")
    @classmethod
    def _normalize_bool(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"", "0", "false", "off", "no"}:
                return False
            if normalized in {"1", "true", "on", "yes"}:
                return True
        return value


class LoggingSettings(BaseModel):
    level: str = Field(default="INFO")
    directory: str = Field(default="logs")
    alerts_log_filename: str = Field(default="alerts.log")
    app_log_filename: str = Field(default="app.log")
    service_name: str = Field(default="biz-tracker-back")
    elasticsearch: ElasticsearchLoggingSettings = Field(default_factory=ElasticsearchLoggingSettings)


class ApiSettings(BaseModel):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8080, ge=1, le=65535)
    admin_token: str = Field(default="change-me", min_length=8)
    admin_header_name: str = Field(default="X-Admin-Token")
    docs_enabled: bool = Field(default=False)
    log_admin_requests: bool = Field(
        default=False,
        description="Active les logs `api.request` pour les endpoints `/admin/*`.",
    )
    allowed_origins: List[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://localhost:5174", "http://localhost:8082"])

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_allowed_origins(cls, value: object) -> List[str] | object:
        def _normalize_origin(origin: str) -> str:
            normalized = origin.strip()
            if normalized.endswith("/"):
                normalized = normalized.rstrip("/")
            return normalized

        if value is None:
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            return [_normalize_origin(item) for item in stripped.split(",") if item.strip()]
        if isinstance(value, list):
            return [_normalize_origin(str(item)) for item in value if str(item).strip()]
        return value
    

class PublicContactSettings(BaseModel):
    enabled: bool = Field(
        default=True,
        description="Active l'endpoint public de réception du formulaire landing.",
    )
    inbox_address: str = Field(
        default="contact@business-tracker.fr",
        description="Adresse de réception (contact) qui reçoit les données du formulaire.",
    )


class StripeSettings(BaseModel):
    secret_key: Optional[str] = Field(default=None, description="Clé secrète Stripe.")
    webhook_secret: Optional[str] = Field(default=None, description="Secret de signature des webhooks Stripe.")
    success_url: str = Field(
        default="https://business-tracker.fr/#pricing",
        description="URL de redirection après paiement réussi.",
    )
    cancel_url: str = Field(
        default="https://business-tracker.fr/#pricing",
        description="URL de redirection après annulation du paiement.",
    )
    portal_return_url: str = Field(
        default="https://business-tracker.fr/upgrade",
        description="URL de retour depuis le Customer Portal.",
    )
    upgrade_url: str = Field(
        default="https://business-tracker.fr/upgrade",
        description="URL de la page dédiée pour la gestion et l'upgrade de plan.",
    )
    price_ids: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapping plan_key -> price_id Stripe.",
    )


class ApifySettings(BaseModel):
    api_token: Optional[str] = Field(default=None, description="Token API pour Apify.")
    linkedin_enrichment_enabled: bool = Field(
        default=True,
        description="Active/désactive l'enrichissement LinkedIn (aucun appel Apify si false).",
    )
    linkedin_actor_id: str = Field(
        default="FbqC9BRstFBddhUqj",
        description="ID de l'Actor Apify pour la recherche LinkedIn.",
    )
    max_concurrent_runs: int = Field(
        default=10,
        ge=1,
        le=10,
        description="Nombre maximum de runs Apify lancés en parallèle.",
    )
    request_timeout_seconds: int = Field(default=60, ge=10, description="Timeout pour les appels Apify.")

    @property
    def enabled(self) -> bool:
        return bool(self.api_token) and bool(self.linkedin_enrichment_enabled)

    @field_validator("api_token", mode="before")
    @classmethod
    def _normalize_api_token(cls, value: object) -> Optional[str | object]:
        if value is None:
            return None
        if isinstance(value, str):
            trimmed = value.strip()
            if not trimmed or trimmed.lower() in {"null", "none"}:
                return None
            return trimmed
        return value


def _permissive_json_loads(value: str) -> Any:
    trimmed = value.strip()
    if not trimmed:
        return value

    lowered = trimmed.lower()
    should_attempt = trimmed[0] in "[{" or trimmed[0] == '"' or lowered in {"true", "false", "null"}

    if not should_attempt:
        # Attempt to parse numeric values but ignore other free-form strings.
        if trimmed.replace(".", "", 1).isdigit() or (trimmed[0] == "-" and trimmed[1:].replace(".", "", 1).isdigit()):
            should_attempt = True

    if not should_attempt:
        return value

    try:
        return json.loads(trimmed)
    except json.JSONDecodeError:
        return value


def _decode_complex_value_with_permissive_json(
    self: PydanticBaseSettingsSource,
    field_name: str,
    field: Any,
    value: Any,
) -> Any:
    metadata = getattr(field, "metadata", ()) if field is not None else ()
    if field and (
        NoDecode in metadata
        or (self.config.get("enable_decoding") is False and ForceDecode not in metadata)
    ):
        return value

    if isinstance(value, (bytes, bytearray)):
        value = value.decode()

    if isinstance(value, str):
        return _permissive_json_loads(value)

    return json.loads(value)


PydanticBaseSettingsSource.decode_complex_value = _decode_complex_value_with_permissive_json


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_nested_delimiter="__",
        extra="allow",
    )

    environment: str = Field(
        default="production",
        validation_alias=AliasChoices("environment", "app_environment", "runtime_environment"),
        description="Deployment environment hint (set to 'local' to disable background workers).",
    )
    database: DatabaseSettings
    sirene: SireneSettings
    email: EmailSettings = Field(default_factory=EmailSettings)
    sync: SyncSettings = Field(default_factory=SyncSettings)
    annuaire: AnnuaireSettings = Field(default_factory=AnnuaireSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    api: ApiSettings = Field(default_factory=ApiSettings)
    google: GoogleSettings = Field(default_factory=GoogleSettings)
    public_contact: PublicContactSettings = Field(default_factory=PublicContactSettings)
    stripe: StripeSettings = Field(default_factory=StripeSettings)
    apify: ApifySettings = Field(default_factory=ApifySettings)

    @property
    def is_local(self) -> bool:
        return self.environment.strip().lower() == "local"


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()  # type: ignore[arg-type]
