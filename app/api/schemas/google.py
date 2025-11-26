"""Schemas liés aux fonctionnalités Google (checks manuels, relances)."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator

from app.api.schemas.establishments import EstablishmentOut


class ManualGoogleCheckResponse(BaseModel):
    found: bool = Field(description="Indique si une page Google a été identifiée.")
    email_sent: bool = Field(description="Indique si un e-mail a été envoyé suite à la détection.")
    message: str = Field(description="Résumé textuel du résultat.")
    place_id: str | None = Field(default=None, description="Identifiant Google Places si présent.")
    place_url: str | None = Field(default=None, description="URL Google Maps ou site associé.")
    check_status: str = Field(description="Statut Google associé à l'établissement.")
    establishment: EstablishmentOut = Field(description="Représentation de l'établissement après mise à jour.")


class GoogleRetryRule(BaseModel):
    max_age_days: int | None = Field(
        default=None,
        ge=0,
        description="Âge maximal (en jours) couvert par la règle. Null = sans limite supérieure.",
    )
    frequency_days: int = Field(
        gt=0,
        description="Fréquence de relance en jours pour la tranche visée.",
    )


class GoogleRetryConfigOut(BaseModel):
    retry_weekdays: list[int] = Field(
        default_factory=list,
        description="Jours de la semaine autorisés pour les relances (0=lundi).",
    )
    default_rules: list[GoogleRetryRule] = Field(description="Règles appliquées à l'ensemble des établissements.")
    micro_rules: list[GoogleRetryRule] = Field(
        description="Règles spécifiques aux micro/auto-entreprises.",
    )

    @field_validator("retry_weekdays")
    @classmethod
    def _validate_weekdays(cls, value: list[int]) -> list[int]:
        cleaned = []
        seen: set[int] = set()
        for day in value:
            if not isinstance(day, int):
                continue
            if day < 0 or day > 6:
                continue
            if day in seen:
                continue
            seen.add(day)
            cleaned.append(day)
        if not cleaned:
            cleaned.append(0)
        return cleaned

    @model_validator(mode="after")
    def _ensure_rules(self) -> "GoogleRetryConfigOut":
        if not self.default_rules:
            raise ValueError("Au moins une règle générale est requise.")
        if not self.micro_rules:
            raise ValueError("Au moins une règle micro-entreprise est requise.")
        return self


class GoogleRetryConfigUpdate(GoogleRetryConfigOut):
    """Payload pour mettre à jour la configuration des relances Google."""


__all__ = [
    "GoogleRetryConfigOut",
    "GoogleRetryConfigUpdate",
    "GoogleRetryRule",
    "ManualGoogleCheckResponse",
]
