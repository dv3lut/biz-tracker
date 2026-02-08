"""Schemas décrivant les établissements."""
from __future__ import annotations

from datetime import datetime, date as Date
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DirectorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type_dirigeant: str
    first_names: str | None
    last_name: str | None
    quality: str | None
    birth_month: int | None
    birth_year: int | None
    siren: str | None
    denomination: str | None
    nationality: str | None


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
    google_match_confidence: float | None
    google_category_match_confidence: float | None
    google_listing_origin_at: datetime | None
    google_listing_origin_source: str | None
    google_listing_age_status: str | None
    google_contact_phone: str | None
    google_contact_email: str | None
    google_contact_website: str | None
    is_sole_proprietorship: bool
    legal_unit_name: str | None = None
    directors: list[DirectorOut] = []


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


__all__ = ["DirectorOut", "EstablishmentDetailOut", "EstablishmentOut"]
