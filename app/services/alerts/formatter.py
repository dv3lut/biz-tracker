from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.utils.google_listing import describe_listing_age_status
from app.utils.urls import build_annuaire_etablissement_url


class EstablishmentFormatter:
    """Build alert payloads and textual representations for establishments."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._subcategory_lookup: dict[str, tuple[str | None, str | None]] | None = None

    def build_payload(self, establishment: models.Establishment) -> dict[str, object]:
        return {
            "siret": establishment.siret,
            "siren": establishment.siren,
            "name": establishment.name,
            "naf_code": establishment.naf_code,
            "naf_libelle": establishment.naf_libelle,
            "date_creation": establishment.date_creation.isoformat() if establishment.date_creation else None,
            "google_listing_origin_at": (
                establishment.google_listing_origin_at.isoformat()
                if establishment.google_listing_origin_at
                else None
            ),
            "google_listing_age_status": establishment.google_listing_age_status,
            "adresse": {
                "numero_voie": establishment.numero_voie,
                "type_voie": establishment.type_voie,
                "libelle_voie": establishment.libelle_voie,
                "complement": establishment.complement_adresse,
                "code_postal": establishment.code_postal,
                "commune": establishment.libelle_commune,
                "code_commune": establishment.code_commune,
                "code_pays": establishment.code_pays,
                "libelle_pays": establishment.libelle_pays,
            },
            "date_dernier_traitement_etablissement": (
                establishment.date_dernier_traitement_etablissement.isoformat()
                if establishment.date_dernier_traitement_etablissement
                else None
            ),
        }

    def format_lines(self, establishment: models.Establishment, *, include_google: bool = False) -> list[str]:
        siret_display, siret_url = self.get_siret_display_and_url(establishment.siret)
        siret_line = f"  SIRET: {siret_display}"
        if siret_url:
            siret_line += f" ({siret_url})"
        naf_code = establishment.naf_code or "N/A"

        lines = [
            f"- {establishment.name or '(nom indisponible)'}",
            f"{siret_line} | NAF: {naf_code}",
        ]
        subcategory_label = self.format_subcategory_label(establishment.naf_code)
        if subcategory_label:
            lines.append(f"  Catégorie : {subcategory_label}")

        address_parts = [
            element
            for element in [
                establishment.numero_voie,
                establishment.type_voie,
                establishment.libelle_voie,
            ]
            if element
        ]
        commune_parts = [
            part
            for part in [
                establishment.code_postal,
                establishment.libelle_commune or establishment.libelle_commune_etranger,
            ]
            if part
        ]
        lines.append(f"  Adresse: {' '.join(address_parts)}")
        lines.append(f"           {' '.join(commune_parts)}")
        if establishment.date_creation:
            lines.append(f"  Création: {establishment.date_creation.isoformat()}")
        if include_google and establishment.google_place_url:
            lines.append(f"  Google: {establishment.google_place_url}")
        if establishment.google_place_url:
            status_label, origin = self.describe_listing_age(establishment)
            if origin:
                lines.append(f"  Statut fiche Google : {status_label} (origine {origin})")
            else:
                lines.append(f"  Statut fiche Google : {status_label}")
        return lines

    def format_address_lines(self, establishment: models.Establishment) -> tuple[str | None, str | None]:
        street_parts = [
            element
            for element in [
                establishment.numero_voie,
                establishment.type_voie,
                establishment.libelle_voie,
            ]
            if element
        ]
        commune_parts = [
            part
            for part in [
                establishment.code_postal,
                establishment.libelle_commune or establishment.libelle_commune_etranger,
            ]
            if part
        ]
        street_line = " ".join(street_parts) or None
        commune_line = " ".join(commune_parts) or None
        return street_line, commune_line

    def get_siret_display_and_url(self, siret: str | None) -> tuple[str, str | None]:
        siret_display = siret or "N/A"
        return siret_display, build_annuaire_etablissement_url(siret)

    def describe_listing_age(self, establishment: models.Establishment) -> tuple[str, str | None]:
        label = describe_listing_age_status(establishment.google_listing_age_status)
        origin = (
            establishment.google_listing_origin_at.isoformat()
            if establishment.google_listing_origin_at
            else None
        )
        return label, origin

    def format_subcategory_label(self, naf_code: str | None) -> str | None:
        category_name, subcategory_name = self._resolve_subcategory_info(naf_code)
        if subcategory_name and category_name and category_name != subcategory_name:
            return f"{subcategory_name} ({category_name})"
        return subcategory_name or category_name

    def _resolve_subcategory_info(self, naf_code: str | None) -> tuple[str | None, str | None]:
        if not naf_code:
            return None, None
        key = naf_code.strip().upper()
        if not key:
            return None, None
        lookup = self._get_subcategory_lookup()
        return lookup.get(key, (None, None))

    def _get_subcategory_lookup(self) -> dict[str, tuple[str | None, str | None]]:
        if self._subcategory_lookup is not None:
            return self._subcategory_lookup

        rows = (
            self._session.execute(
                select(
                    models.NafSubCategory.naf_code,
                    models.NafSubCategory.name,
                    models.NafCategory.name,
                )
                .join(models.NafCategory, models.NafCategory.id == models.NafSubCategory.category_id)
                .where(models.NafSubCategory.is_active.is_(True))
            ).all()
        )
        lookup: dict[str, tuple[str | None, str | None]] = {}
        for naf_code, sub_name, category_name in rows:
            if not naf_code:
                continue
            lookup[naf_code.strip().upper()] = (category_name, sub_name)
        self._subcategory_lookup = lookup
        return lookup