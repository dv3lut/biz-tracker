"""Règles de matching strict entre un établissement Sirene et une fiche Google.

Objectif:
- Réduire les faux positifs via des contraintes fortes (code postal, numéro de voie).
- Permettre un fallback "distance" quand le nom est très proche mais l'adresse diffère.

Ce module est volontairement pur (pas d'accès réseau) pour être facilement testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import math
import re
from typing import Any

from app.services.google_business.google_matching import (
    extract_postal_code,
    normalize_text,
    token_similarity,
    tokenize_name,
)


# Stopwords génériques (langue + formes juridiques).
# Important: on évite les listes métier (restaurant, café, etc.) pour rester agnostique.
_STOPWORDS = {
    "a",
    "au",
    "aux",
    "d",
    "de",
    "des",
    "du",
    "en",
    "et",
    "l",
    "la",
    "le",
    "les",
    "sur",
    "sous",
    "un",
    "une",
    # formes juridiques fréquentes
    "eurl",
    "gmbh",
    "holding",
    "sas",
    "sasu",
    "sa",
    "sarl",
    "sci",
    "scm",
    "scp",
    "snc",
    "selarl",
    "selas",
    "selasu",
}

_HOUSE_NUMBER_RE = re.compile(r"^\s*(\d{1,5})\s*(bis|ter|quater|[a-z])?\b", re.IGNORECASE)


@dataclass(frozen=True)
class CandidateMatchDecision:
    accept: bool
    needs_distance_check: bool
    score: float
    details: dict[str, Any]


def normalize_house_number(number: str | None, repetition: str | None = None) -> str | None:
    if not number:
        return None
    base = normalize_text(number)
    base = re.sub(r"[^0-9a-z]", "", base)
    if not base:
        return None

    suffix = normalize_text(repetition) if repetition else ""
    suffix = re.sub(r"[^0-9a-z]", "", suffix)
    suffix = suffix or ""

    if suffix and base.endswith(suffix):
        return base
    return f"{base}{suffix}" if suffix else base


def extract_house_number(address: str | None) -> str | None:
    if not address:
        return None
    match = _HOUSE_NUMBER_RE.search(address)
    if not match:
        return None
    digits = match.group(1)
    suffix = match.group(2) or ""
    suffix = suffix.strip().lower()
    return f"{digits}{suffix}" if suffix else digits


def _distinctive_tokens(value: str | None) -> set[str]:
    tokens = set(tokenize_name(value))
    # On filtre agressivement les tokens peu informatifs.
    return {token for token in tokens if token not in _STOPWORDS and not token.isdigit()}


def _name_metrics(ref_name: str | None, cand_name: str | None) -> dict[str, Any]:
    ref_norm = normalize_text(ref_name)
    cand_norm = normalize_text(cand_name)
    if not ref_norm or not cand_norm:
        return {
            "name_ratio": 0.0,
            "token_score": 0.0,
            "distinctive_overlap": 0,
        }

    name_ratio = SequenceMatcher(None, ref_norm, cand_norm).ratio()
    token_score = token_similarity(tokenize_name(ref_name), tokenize_name(cand_name))
    ref_dist = _distinctive_tokens(ref_name)
    cand_dist = _distinctive_tokens(cand_name)
    overlap_set = ref_dist & cand_dist
    overlap = len(overlap_set)
    distinct_union = len(ref_dist | cand_dist)
    distinct_jaccard = (overlap / distinct_union) if distinct_union else 0.0
    return {
        "name_ratio": round(name_ratio, 4),
        "token_score": round(token_score, 4),
        "distinctive_overlap": overlap,
        "distinctive_jaccard": round(distinct_jaccard, 4),
    }


def evaluate_candidate_match(
    establishment: Any,
    candidate_name: str,
    candidate_address: str | None,
    *,
    distance_m: float | None = None,
    distance_threshold_m: float = 500.0,
) -> CandidateMatchDecision:
    """Décide si un candidat Google correspond à l'établissement.

    - Code postal: strict (si on en attend un, il doit être présent côté Google et identique)
    - Nom: doit partager au moins un token distinctif (ou être quasi-identique)
    - Numéro de voie: strict si présent des deux côtés ; sinon fallback distance si nom très fort

    Si `distance_m` est fourni, il est utilisé pour valider les cas "needs_distance_check".
    """

    ref_postal = getattr(establishment, "code_postal", None) or None
    ref_commune = getattr(establishment, "libelle_commune", None) or getattr(establishment, "libelle_commune_etranger", None)
    ref_number = normalize_house_number(
        getattr(establishment, "numero_voie", None),
        getattr(establishment, "indice_repetition", None),
    )

    cand_address = candidate_address or ""
    cand_postal = extract_postal_code(cand_address)
    cand_number = extract_house_number(cand_address)

    metrics = _name_metrics(getattr(establishment, "name", None), candidate_name)
    name_ratio = float(metrics["name_ratio"])
    token_score = float(metrics["token_score"])
    distinctive_overlap = int(metrics["distinctive_overlap"])
    distinctive_jaccard = float(metrics.get("distinctive_jaccard", 0.0))

    ref_dist = _distinctive_tokens(getattr(establishment, "name", None))
    cand_dist = _distinctive_tokens(candidate_name)
    ref_dist_fully_in_candidate = bool(ref_dist) and ref_dist.issubset(cand_dist)

    postal_match: bool | None
    if ref_postal:
        if cand_postal is None:
            postal_match = None
        else:
            postal_match = cand_postal == ref_postal
    else:
        postal_match = None

    commune_match: bool | None = None
    commune_norm = normalize_text(ref_commune)
    addr_norm = normalize_text(cand_address)
    if commune_norm and addr_norm:
        commune_match = commune_norm in addr_norm

    # Règles nom (génériques):
    # - On refuse les overlaps trop faibles entre tokens distinctifs quand le nom a plusieurs tokens,
    #   pour éviter les collisions sur des mots "courants" (ex: "Délices", "Services", etc.).
    # - On autorise les noms très courts si leur token distinctif est présent dans le candidat.
    name_near_exact = name_ratio >= 0.93
    ref_dist_size = len(ref_dist)
    cand_dist_size = len(cand_dist)
    has_anchor_overlap = (
        distinctive_overlap >= 2
        or (ref_dist_size == 1 and distinctive_overlap == 1)
        or name_near_exact
        or (ref_dist_fully_in_candidate and ref_dist_size <= 2)
    )

    name_strong = (
        name_near_exact
        or (
            has_anchor_overlap
            and (
                name_ratio >= 0.86
                or token_score >= 0.6
                or (distinctive_jaccard >= 0.6 and distinctive_overlap >= 2)
            )
        )
    )

    name_ok = (
        name_near_exact
        or (
            has_anchor_overlap
            and (
                name_ratio >= 0.8
                or token_score >= 0.5
                or (distinctive_overlap >= 2 and distinctive_jaccard >= 0.45)
            )
        )
    )

    hard_reasons: list[str] = []

    if ref_postal:
        if cand_postal is None:
            hard_reasons.append("postal_missing")
        elif cand_postal != ref_postal:
            hard_reasons.append("postal_mismatch")

    if not name_ok:
        hard_reasons.append("name_mismatch")

    needs_distance_check = False
    if ref_number and cand_number:
        if ref_number != cand_number:
            if ref_postal and cand_postal == ref_postal and name_strong:
                needs_distance_check = True
            else:
                hard_reasons.append("house_number_mismatch")

    # Score (pour classer les candidats, pas pour décider seul)
    score = 0.0
    score += 0.65 * name_ratio + 0.35 * token_score
    if ref_postal and cand_postal == ref_postal:
        score += 0.25
    if commune_match:
        score += 0.1
    if ref_number and cand_number and ref_number == cand_number:
        score += 0.25
    if ref_number and cand_number is None:
        score -= 0.1
    if commune_match is False:
        score -= 0.15
    score = max(0.0, min(1.0, score))

    accept = False
    if hard_reasons:
        accept = False
    elif needs_distance_check:
        if distance_m is not None:
            accept = distance_m <= distance_threshold_m
        else:
            accept = False
    else:
        accept = True

    details: dict[str, Any] = {
        "name_ratio": metrics["name_ratio"],
        "token_score": metrics["token_score"],
        "distinctive_overlap": distinctive_overlap,
        "distinctive_jaccard": metrics.get("distinctive_jaccard"),
        "ref_postal": ref_postal,
        "cand_postal": cand_postal,
        "postal_match": postal_match,
        "commune": normalize_text(ref_commune) if ref_commune else None,
        "commune_match": commune_match,
        "ref_house_number": ref_number,
        "cand_house_number": cand_number,
        "needs_distance_check": needs_distance_check,
        "distance_m": round(float(distance_m), 1) if distance_m is not None else None,
        "distance_threshold_m": distance_threshold_m,
        "hard_reasons": hard_reasons,
        "score": round(score, 4),
    }

    return CandidateMatchDecision(
        accept=accept,
        needs_distance_check=needs_distance_check,
        score=score,
        details=details,
    )


def haversine_distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Distance haversine en mètres."""

    r = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c
