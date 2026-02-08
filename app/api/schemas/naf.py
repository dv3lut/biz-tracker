"""Schemas relatifs aux catégories et sous-catégories NAF."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.api.schemas.regions import DepartmentOut


class NafSubCategoryStats(BaseModel):
    subcategory_id: UUID = Field(description="Identifiant de la sous-catégorie NAF.")
    naf_code: str = Field(description="Code NAF exact suivi par Business tracker.")
    name: str = Field(description="Libellé lisible de la sous-catégorie.")
    establishment_count: int = Field(description="Nombre d'établissements correspondant à ce code NAF.")
    google_found: int = Field(description="Nombre d'établissements avec fiche Google identifiée.")
    google_not_found: int = Field(description="Nombre d'établissements sans fiche Google trouvée.")
    google_insufficient: int = Field(description="Nombre d'établissements dont l'identité est insuffisante pour Google.")
    google_pending: int = Field(description="Nombre d'établissements encore en file d'attente Google.")
    google_type_mismatch: int = Field(description="Nombre d'établissements rejetés car la catégorie Google ne correspond pas au NAF attendu.")
    google_other: int = Field(description="Nombre d'établissements avec un statut Google inattendu.")
    listing_recent: int = Field(description="Fiches Google considérées comme création récente (dernier run).")
    listing_recent_missing_contact: int = Field(
        description="Fiches Google récentes mais sans contact disponible (dernier run)."
    )
    listing_not_recent: int = Field(description="Fiches Google considérées comme création ancienne ou reprise.")
    listing_unknown: int = Field(description="Fiches Google sans information fiable sur l'ancienneté.")


class NafCategoryStats(BaseModel):
    category_id: UUID = Field(description="Identifiant de la catégorie regroupant plusieurs NAF.")
    name: str = Field(description="Nom commercial de la catégorie.")
    total_establishments: int = Field(description="Total d'établissements rattachés aux sous-catégories de cette catégorie.")
    subcategories: list[NafSubCategoryStats] = Field(
        default_factory=list,
        description="Détail par sous-catégorie NAF.",
    )


class NafSubCategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    naf_code: str
    price_cents: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    google_department_count: int = Field(
        default=0,
        description="Nombre de départements activés pour les synchros Google.",
    )
    google_department_all: bool = Field(
        default=False,
        description="Indique si tous les départements sont activés via au moins un client.",
    )
    google_departments: list[DepartmentOut] = Field(
        default_factory=list,
        description="Liste des départements activés pour les synchros Google.",
    )

    @computed_field
    @property
    def price_eur(self) -> float:
        return round(self.price_cents / 100, 2)


class NafCategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    keywords: list[str] = Field(default_factory=list, description="Mots-clés supplémentaires pour l'appariement Google.")
    created_at: datetime
    updated_at: datetime
    subcategories: list[NafSubCategoryOut] = Field(default_factory=list)


class NafCategoryCreate(BaseModel):
    name: str
    description: str | None = None
    keywords: list[str] = Field(default_factory=list, description="Mots-clés additionnels (un mot/phrase par entrée).")


class NafCategoryUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    keywords: list[str] | None = Field(default=None, description="Remplace la liste complète des mots-clés lorsqu'elle est fournie.")


class NafSubCategoryCreate(BaseModel):
    category_id: UUID
    name: str
    naf_code: str
    description: str | None = None
    price_eur: float | None = Field(default=None, ge=0, description="Tarif de référence en euros TTC.")
    is_active: bool = True


class NafSubCategoryUpdate(BaseModel):
    name: str | None = None
    naf_code: str | None = None
    description: str | None = None
    price_eur: float | None = Field(default=None, ge=0)
    is_active: bool | None = None


class NafCategorySubCategoryLink(BaseModel):
    subcategory_id: UUID


__all__ = [
    "NafCategoryCreate",
    "NafCategoryOut",
    "NafCategoryStats",
    "NafCategoryUpdate",
    "NafCategorySubCategoryLink",
    "NafSubCategoryCreate",
    "NafSubCategoryOut",
    "NafSubCategoryStats",
    "NafSubCategoryUpdate",
]
