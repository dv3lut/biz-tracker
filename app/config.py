"""Application settings loaded from the environment."""
from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    @field_validator("restaurant_naf_codes", mode="before")
    @classmethod
    def _split_naf_codes(cls, value: object) -> List[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return value
        return ["56.10A"]


class DatabaseSettings(BaseModel):
    url: str = Field(description="SQLAlchemy URL for the PostgreSQL database.")
    echo: bool = Field(default=False)
    pool_size: int = Field(default=5, ge=1)
    pool_timeout: int = Field(default=30, ge=1)


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


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_nested_delimiter="__",
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
