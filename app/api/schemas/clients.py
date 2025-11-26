"""Schemas associés aux clients et abonnements."""
from __future__ import annotations

from datetime import datetime, date as Date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.google_listing import default_listing_statuses, normalize_listing_status_filters

ListingStatus = Literal["recent_creation", "recent_creation_missing_contact", "not_recent_creation"]


class ClientRecipientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    created_at: datetime


class ClientSubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    client_id: UUID
    subcategory_id: UUID
    created_at: datetime
    subcategory: "NafSubCategoryOut"


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    start_date: Date
    end_date: Date | None
    listing_statuses: list[ListingStatus]
    emails_sent_count: int
    last_email_sent_at: datetime | None
    created_at: datetime
    updated_at: datetime
    recipients: list[ClientRecipientOut]
    subscriptions: list[ClientSubscriptionOut]


class ClientCreate(BaseModel):
    name: str
    start_date: Date
    end_date: Date | None = None
    listing_statuses: list[ListingStatus] = Field(
        default_factory=default_listing_statuses,
        description="Statuts des fiches Google à inclure dans les alertes et exports clients.",
    )
    recipients: list[str] = Field(default_factory=list, description="Liste d'adresses e-mail associées au client.")
    subscription_ids: list[UUID] = Field(
        default_factory=list,
        description="Identifiants des sous-catégories NAF auxquelles le client est abonné.",
    )

    @field_validator("listing_statuses")
    @classmethod
    def _validate_listing_statuses(cls, value: list[str]) -> list[ListingStatus]:
        statuses = normalize_listing_status_filters(value)
        if not statuses:
            raise ValueError("Sélectionnez au moins un statut de fiche Google.")
        return statuses


class ClientUpdate(BaseModel):
    name: str | None = None
    start_date: Date | None = None
    end_date: Date | None = None
    listing_statuses: list[ListingStatus] | None = Field(
        default=None,
        description="Remplace la liste complète des statuts lorsqu'elle est fournie.",
    )
    recipients: list[str] | None = Field(default=None, description="Remplace la liste complète des destinataires lorsqu'elle est fournie.")
    subscription_ids: list[UUID] | None = Field(
        default=None,
        description="Remplace complètement la liste des sous-catégories souscrites lorsqu'elle est fournie.",
    )

    @field_validator("listing_statuses")
    @classmethod
    def _validate_update_listing_statuses(
        cls,
        value: list[str] | None,
    ) -> list[ListingStatus] | None:
        if value is None:
            return None
        statuses = normalize_listing_status_filters(value)
        if not statuses:
            raise ValueError("Sélectionnez au moins un statut de fiche Google.")
        return statuses


from app.api.schemas.naf import NafSubCategoryOut  # noqa: E402  (import circular prevention)

ClientSubscriptionOut.model_rebuild()
ClientOut.model_rebuild()

__all__ = [
    "ClientCreate",
    "ClientOut",
    "ClientRecipientOut",
    "ClientSubscriptionOut",
    "ClientUpdate",
    "ListingStatus",
]
