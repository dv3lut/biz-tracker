"""Transform Sirene API payloads into ORM-friendly structures."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional

from app.utils.dates import parse_date, parse_datetime


def _select_current_period(periods: list[dict[str, Any]]) -> dict[str, Any]:
    for period in periods:
        if period.get("dateFin") in (None, ""):
            return period
    return periods[0] if periods else {}


def _select_current_unite_legale_period(periods: list[dict[str, Any]]) -> dict[str, Any]:
    for period in periods:
        if period.get("dateFin") in (None, ""):
            return period
    return periods[0] if periods else {}


def _parse_int(value: Optional[str]) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def extract_name(payload: dict[str, Any]) -> str | None:
    unite_legale = payload.get("uniteLegale", {})
    periods_etablissement = payload.get("periodesEtablissement", [])
    current_period = _select_current_period(periods_etablissement)
    periods_unite_legale = unite_legale.get("periodesUniteLegale", [])
    current_unite_legale_period = _select_current_unite_legale_period(periods_unite_legale)

    candidates = [
        current_period.get("denominationUsuelleEtablissement"),
        current_period.get("enseigne1Etablissement"),
        current_period.get("enseigne2Etablissement"),
        current_period.get("enseigne3Etablissement"),
        unite_legale.get("denominationUsuelle1UniteLegale"),
        unite_legale.get("denominationUsuelle2UniteLegale"),
        unite_legale.get("denominationUsuelle3UniteLegale"),
        unite_legale.get("denominationUniteLegale"),
    ]

    nom_usage = unite_legale.get("nomUsageUniteLegale")
    nom = unite_legale.get("nomUniteLegale")
    prenom = unite_legale.get("prenom1UniteLegale")
    if nom_usage:
        candidates.append(nom_usage)
    if nom and prenom:
        candidates.append(f"{prenom} {nom}")
    elif nom:
        candidates.append(nom)

    for candidate in candidates:
        cleaned = _clean(candidate)
        if cleaned:
            return cleaned
    return None


def extract_fields(payload: dict[str, Any]) -> Dict[str, Any]:
    unite_legale = payload.get("uniteLegale", {})
    periods_etablissement = payload.get("periodesEtablissement", [])
    current_period = _select_current_period(periods_etablissement)
    periods_unite_legale = unite_legale.get("periodesUniteLegale", [])
    current_unite_legale_period = _select_current_unite_legale_period(periods_unite_legale)
    adresse = payload.get("adresseEtablissement", payload)

    return {
        "siret": payload.get("siret"),
        "siren": payload.get("siren"),
        "nic": payload.get("nic"),
        "naf_code": current_period.get("activitePrincipaleEtablissement")
        or payload.get("activitePrincipaleEtablissement"),
        "naf_libelle": current_period.get("libelleActivitePrincipaleEtablissement")
        or payload.get("libelleActivitePrincipaleEtablissement"),
        "etat_administratif": current_period.get("etatAdministratifEtablissement")
        or payload.get("etatAdministratifEtablissement"),
        "date_creation": parse_date(payload.get("dateCreationEtablissement")),
        "date_debut_activite": parse_date(current_period.get("dateDebut")),
        "date_dernier_traitement_etablissement": parse_datetime(payload.get("dateDernierTraitementEtablissement")),
        "date_dernier_traitement_unite_legale": parse_datetime(unite_legale.get("dateDernierTraitementUniteLegale")),
        "name": extract_name(payload),
        "denomination_unite_legale": _clean(unite_legale.get("denominationUniteLegale")),
        "denomination_usuelle_unite_legale": _clean(unite_legale.get("denominationUsuelle1UniteLegale")),
        "denomination_usuelle_etablissement": _clean(current_period.get("denominationUsuelleEtablissement")),
        "enseigne1": _clean(current_period.get("enseigne1Etablissement")),
        "enseigne2": _clean(current_period.get("enseigne2Etablissement")),
        "enseigne3": _clean(current_period.get("enseigne3Etablissement")),
        "categorie_juridique": _clean(
            unite_legale.get("categorieJuridiqueUniteLegale")
            or current_unite_legale_period.get("categorieJuridiqueUniteLegale")
        ),
        "categorie_entreprise": _clean(unite_legale.get("categorieEntreprise")),
        "tranche_effectifs": _clean(unite_legale.get("trancheEffectifsUniteLegale")),
        "annee_effectifs": _parse_int(unite_legale.get("anneeEffectifsUniteLegale")),
        "nom_usage": _clean(unite_legale.get("nomUsageUniteLegale")),
        "nom": _clean(unite_legale.get("nomUniteLegale")),
        "prenom1": _clean(unite_legale.get("prenom1UniteLegale")),
        "prenom2": _clean(unite_legale.get("prenom2UniteLegale")),
        "prenom3": _clean(unite_legale.get("prenom3UniteLegale")),
        "prenom4": _clean(unite_legale.get("prenom4UniteLegale")),
        "prenom_usuel": _clean(unite_legale.get("prenomUsuelUniteLegale")),
        "pseudonyme": _clean(current_unite_legale_period.get("pseudonymeUniteLegale")),
        "sexe": _clean(unite_legale.get("sexeUniteLegale")),
        "complement_adresse": _clean(adresse.get("complementAdresseEtablissement")),
        "numero_voie": _clean(adresse.get("numeroVoieEtablissement")),
        "indice_repetition": _clean(adresse.get("indiceRepetitionEtablissement")),
        "type_voie": _clean(adresse.get("typeVoieEtablissement")),
        "libelle_voie": _clean(adresse.get("libelleVoieEtablissement")),
        "distribution_speciale": _clean(adresse.get("distributionSpecialeEtablissement")),
        "code_postal": _clean(adresse.get("codePostalEtablissement")),
        "libelle_commune": _clean(adresse.get("libelleCommuneEtablissement")),
        "libelle_commune_etranger": _clean(adresse.get("libelleCommuneEtrangerEtablissement")),
        "code_commune": _clean(adresse.get("codeCommuneEtablissement")),
        "code_cedex": _clean(adresse.get("codeCedexEtablissement")),
        "libelle_cedex": _clean(adresse.get("libelleCedexEtablissement")),
        "code_pays": _clean(adresse.get("codePaysEtrangerEtablissement")),
        "libelle_pays": _clean(adresse.get("libellePaysEtrangerEtablissement")),
    }



_PLACEHOLDER_TOKENS = {"ND"}


def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    normalized = "".join(ch for ch in stripped.upper() if ch.isalnum())
    if not normalized:
        return None
    if normalized in _PLACEHOLDER_TOKENS:
        return None
    if len(normalized) % 2 == 0 and all(normalized[i : i + 2] == "ND" for i in range(0, len(normalized), 2)):
        return None
    return stripped
