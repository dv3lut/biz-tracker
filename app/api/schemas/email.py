"""Schemas relatifs à la configuration et aux tests d'e-mails admin."""
from __future__ import annotations

from pydantic import BaseModel, Field


class AdminEmailConfig(BaseModel):
    recipients: list[str] = Field(default_factory=list, description="Destinataires administrateurs du résumé de synchro.")
    include_previous_month_day_alerts: bool = Field(
        default=False,
        description=(
            "Inclure un rappel des alertes du même jour le mois précédent dans les e-mails clients."
        ),
    )


class AdminEmailConfigUpdate(BaseModel):
    recipients: list[str] = Field(default_factory=list, description="Nouvelle liste d'adresses e-mail admin.")
    include_previous_month_day_alerts: bool | None = Field(
        default=None,
        description=(
            "Active/désactive le rappel des alertes du même jour le mois précédent dans les e-mails clients."
        ),
    )


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


__all__ = [
    "AdminEmailConfig",
    "AdminEmailConfigUpdate",
    "EmailTestRequest",
    "EmailTestResponse",
]
