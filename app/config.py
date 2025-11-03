"""Application settings loaded from the environment."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, List, Optional
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
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
    restaurant_naf_codes: List[str] = Field(default_factory=lambda: ["56.10A"])
    request_timeout_seconds: int = Field(default=30, ge=1)
    current_period_date: str = Field(
        default="2100-01-01",
        description=(
            "Date passed to Sirene searches so historized fields such as etatAdministratifEtablissement are "
            "evaluated on their current value."
        ),
    )

    @field_validator("restaurant_naf_codes", mode="before")
    @classmethod
    def _split_naf_codes(cls, value: object) -> List[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return value
        return ["56.10A"]


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
            password=None,
            host=self.host,
            port=self.port,
            database=self.name,
        )


class EmailSettings(BaseModel):
    enabled: bool = Field(default=False)
    smtp_host: Optional[str] = None
    smtp_port: int = Field(default=587, ge=1)
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    use_tls: bool = Field(default=True)
    from_address: Optional[str] = None
    recipients: List[str] = Field(default_factory=list)

    @field_validator("recipients", mode="before")
    @classmethod
    def _split_recipients(cls, value: object) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return value
        raise TypeError("Unsupported value for recipients")


class SyncSettings(BaseModel):
    full_scope_key: str = Field(default="restaurants_full")
    incremental_scope_key: str = Field(default="restaurants_incremental")
    minimum_delay_minutes: int = Field(
        default=1440,
        description="Default minimum delay between sync runs when no guidance is provided by the informations service.",
    )


class LoggingSettings(BaseModel):
    level: str = Field(default="INFO")
    directory: str = Field(default="logs")
    alerts_log_filename: str = Field(default="alerts.log")
    app_log_filename: str = Field(default="app.log")


class ApiSettings(BaseModel):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8080, ge=1, le=65535)
    admin_token: str = Field(default="change-me", min_length=8)
    admin_header_name: str = Field(default="X-Admin-Token")
    docs_enabled: bool = Field(default=False)
    allowed_origins: List[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://localhost:5174"])

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_allowed_origins(cls, value: object) -> List[str] | object:
        if value is None:
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            return [item.strip() for item in stripped.split(",") if item.strip()]
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


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_nested_delimiter="__",
        json_loads=_permissive_json_loads,
        extra="allow",
    )

    database: DatabaseSettings
    sirene: SireneSettings
    email: EmailSettings = Field(default_factory=EmailSettings)
    sync: SyncSettings = Field(default_factory=SyncSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    api: ApiSettings = Field(default_factory=ApiSettings)


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()  # type: ignore[arg-type]
