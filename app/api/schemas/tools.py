"""Schemas pour les outils admin (Sirene, etc.)."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator, model_validator

from app.utils.naf import normalize_naf_code


class SireneNewBusinessesRequest(BaseModel):
    start_date: date = Field(description="Date de début (incluse) pour la création des établissements.")
    end_date: date | None = Field(
        default=None,
        description="Date de fin (incluse). Si absente, la date de début est utilisée.",
    )
    naf_codes: list[str] = Field(
        description="Liste des codes NAF à cibler (ex: 56.10A).",
        min_length=1,
    )
    limit: int = Field(
        default=100,
        ge=1,
        le=200,
        description="Nombre maximum d'établissements à retourner.",
    )
    department_codes: list[str] | None = Field(
        default=None,
        description="Codes départements à filtrer (ex: 75, 33).",
    )
    enrich_annuaire: bool = Field(
        default=False,
        description="Si activé, enrichit chaque résultat avec les dirigeants et le nom de l'unité légale via l'API Recherche Entreprises.",
    )

    @field_validator("naf_codes")
    @classmethod
    def validate_naf_codes(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in value or []:
            candidate = (raw or "").strip().upper().replace(" ", "")
            normalized_code = normalize_naf_code(candidate)
            if not normalized_code:
                raise ValueError("Chaque code NAF doit contenir 4 chiffres suivis d'une lettre (ex: 56.10A).")
            if normalized_code in seen:
                continue
            seen.add(normalized_code)
            normalized.append(normalized_code)
            if len(normalized) > 25:
                raise ValueError("Maximum 25 codes NAF ciblés par requête.")
        if not normalized:
            raise ValueError("Au moins un code NAF est requis.")
        return normalized

    @model_validator(mode="after")
    def validate_dates(self) -> "SireneNewBusinessesRequest":
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("La date de fin doit être postérieure ou égale à la date de début.")
        return self


class SireneNewBusinessDirectorOut(BaseModel):
    type_dirigeant: str
    first_names: str | None = None
    last_name: str | None = None
    quality: str | None = None
    birth_month: int | None = None
    birth_year: int | None = None
    siren: str | None = None
    denomination: str | None = None
    nationality: str | None = None


class SireneNewBusinessOut(BaseModel):
    siret: str
    siren: str | None = None
    nic: str | None = None
    name: str | None = None
    naf_code: str | None = None
    naf_label: str | None = None
    date_creation: date | None = None
    is_individual: bool
    leader_name: str | None = None
    denomination_unite_legale: str | None = None
    denomination_usuelle_unite_legale: str | None = None
    denomination_usuelle_etablissement: str | None = None
    enseigne1: str | None = None
    enseigne2: str | None = None
    enseigne3: str | None = None
    complement_adresse: str | None = None
    numero_voie: str | None = None
    indice_repetition: str | None = None
    type_voie: str | None = None
    libelle_voie: str | None = None
    code_postal: str | None = None
    libelle_commune: str | None = None
    libelle_commune_etranger: str | None = None
    legal_unit_name: str | None = None
    directors: list[SireneNewBusinessDirectorOut] = []


class AnnuaireDebugResponse(BaseModel):
    siret: str
    siren: str
    success: bool
    status_code: int | None = None
    duration_ms: float | None = None
    error: str | None = None
    payload: dict[str, object] | None = None


class SireneNewBusinessesResponse(BaseModel):
    total: int
    returned: int
    establishments: list[SireneNewBusinessOut]


__all__ = [
    "SireneNewBusinessDirectorOut",
    "SireneNewBusinessesRequest",
    "SireneNewBusinessesResponse",
    "SireneNewBusinessOut",
    "AnnuaireDebugResponse",
]
