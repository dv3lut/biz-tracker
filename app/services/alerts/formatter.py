from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.utils.google_listing import describe_listing_age_status
from app.utils.naf import normalize_naf_code
from app.utils.urls import build_annuaire_etablissement_url

MONTH_LABELS_FR = {
    1: "janvier",
    2: "février",
    3: "mars",
    4: "avril",
    5: "mai",
    6: "juin",
    7: "juillet",
    8: "août",
    9: "septembre",
    10: "octobre",
    11: "novembre",
    12: "décembre",
}


def format_month_year_fr(value) -> str:
    month_label = MONTH_LABELS_FR.get(value.month, str(value.month))
    return f"{month_label.capitalize()} {value.year}"


class EstablishmentFormatter:
    """Build alert payloads and textual representations for establishments."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._subcategory_lookup: dict[str, list[tuple[str | None, str | None]]] | None = None

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
            lines.append(f"  Création administrative : {format_month_year_fr(establishment.date_creation)}")
        else:
            lines.append("  Création administrative : N/A")
        if include_google and establishment.google_place_url:
            lines.append(f"  Google: {establishment.google_place_url}")
        if establishment.google_place_url:
            status_label, _ = self.describe_listing_age(establishment)
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

    def format_full_address(self, establishment: models.Establishment) -> str | None:
        street_line, commune_line = self.format_address_lines(establishment)
        parts = [part for part in [street_line, commune_line] if part]
        if not parts:
            return None
        return ", ".join(parts)

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
        entries = self._resolve_subcategory_entries(naf_code)
        if not entries:
            return None
        labels: list[str] = []
        categories_without_sub = set()
        grouped: dict[str, set[str]] = {}
        for category_name, subcategory_name in entries:
            if subcategory_name:
                grouped.setdefault(subcategory_name, set())
                if category_name and category_name != subcategory_name:
                    grouped[subcategory_name].add(category_name)
            elif category_name:
                categories_without_sub.add(category_name)
        for subcategory_name, categories in grouped.items():
            if categories:
                labels.append(f"{subcategory_name} ({', '.join(sorted(categories))})")
            else:
                labels.append(subcategory_name)
        labels.extend(sorted(categories_without_sub))
        return ", ".join(labels) if labels else None

    def resolve_category_and_subcategory(self, naf_code: str | None) -> tuple[str | None, str | None]:
        entries = self._resolve_subcategory_entries(naf_code)
        if not entries:
            return None, None
        category_name, subcategory_name = entries[0]
        return category_name, subcategory_name

    def resolve_client_category_labels(
        self,
        client: models.Client,
        naf_code: str | None,
    ) -> tuple[list[str], list[str]]:
        normalized = normalize_naf_code(naf_code)
        if not normalized:
            return [], []
        client_category_ids = {str(value) for value in getattr(client, "category_ids", []) or []}
        categories: set[str] = set()
        subcategories: set[str] = set()
        for subscription in getattr(client, "subscriptions", []) or []:
            subcategory = getattr(subscription, "subcategory", None)
            if not subcategory or not getattr(subcategory, "is_active", True):
                continue
            if normalize_naf_code(getattr(subcategory, "naf_code", None)) != normalized:
                continue
            if subcategory.name:
                subcategories.add(subcategory.name)
            for category in getattr(subcategory, "categories", []) or []:
                category_id = getattr(category, "id", None)
                if client_category_ids and category_id is not None and str(category_id) not in client_category_ids:
                    continue
                category_name = getattr(category, "name", None)
                if category_name:
                    categories.add(category_name)
        return sorted(categories), sorted(subcategories)

    def _resolve_subcategory_entries(self, naf_code: str | None) -> list[tuple[str | None, str | None]]:
        if not naf_code:
            return []
        key = naf_code.strip().upper()
        if not key:
            return []
        lookup = self._get_subcategory_lookup()
        return lookup.get(key, [])

    def _get_subcategory_lookup(self) -> dict[str, list[tuple[str | None, str | None]]]:
        if self._subcategory_lookup is not None:
            return self._subcategory_lookup

        rows = (
            self._session.execute(
                select(
                    models.NafSubCategory.naf_code,
                    models.NafSubCategory.name,
                    models.NafCategory.name,
                )
                .join(
                    models.NafCategorySubCategory,
                    models.NafCategorySubCategory.subcategory_id == models.NafSubCategory.id,
                )
                .join(models.NafCategory, models.NafCategory.id == models.NafCategorySubCategory.category_id)
                .where(models.NafSubCategory.is_active.is_(True))
            ).all()
        )
        lookup: dict[str, list[tuple[str | None, str | None]]] = {}
        for naf_code, sub_name, category_name in rows:
            if not naf_code:
                continue
            lookup.setdefault(naf_code.strip().upper(), []).append((category_name, sub_name))
        self._subcategory_lookup = lookup
        return lookup