"""Text normalization and matching helpers for Google Places."""
from __future__ import annotations

import logging
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Iterable

from app.db import models

_LOGGER = logging.getLogger(__name__)
_POSTAL_CODE_PATTERN = re.compile(r"\b(\d{5})\b")


def sanitize_placeholder(value: str | None, placeholder_tokens: set[str]) -> str:
    if not value:
        return ""
    cleaned = value.strip()
    if not cleaned:
        return ""
    normalized = "".join(ch for ch in cleaned.upper() if ch.isalnum())
    if not normalized:
        return ""
    if normalized in placeholder_tokens:
        return ""
    if len(normalized) % 2 == 0 and all(normalized[i : i + 2] == "ND" for i in range(0, len(normalized), 2)):
        return ""
    return cleaned


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower().strip()


def tokenize_name(value: str | None) -> list[str]:
    if not value:
        return []
    normalized = normalize_text(value)
    if not normalized:
        return []
    return [token for token in re.split(r"[^a-z0-9]+", normalized) if len(token) >= 2]


def tokenize_text(value: str | None) -> set[str]:
    if not value:
        return set()
    normalized = normalize_text(value)
    tokens: set[str] = set()
    for fragment in re.split(r"[^a-z0-9]+", normalized):
        if len(fragment) < 3:
            continue
        tokens.update(expand_keyword_variants(fragment))
    return tokens


def expand_keyword_variants(token: str) -> set[str]:
    variants = {token}
    if len(token) > 3 and token.endswith("s"):
        variants.add(token[:-1])
    if len(token) > 4 and token.endswith("es"):
        variants.add(token[:-2])
    if len(token) > 4 and token.endswith("ies"):
        variants.add(token[:-3] + "y")
    if len(token) > 5 and token.endswith("ation"):
        variants.add(token[:-5] + "ant")
    if len(token) > 5 and token.endswith("erie"):
        variants.add(token[:-4] + "er")
    return variants


def token_similarity(ref_tokens: list[str], candidate_tokens: list[str]) -> float:
    if not ref_tokens or not candidate_tokens:
        return 0.0
    ref_set = set(ref_tokens)
    cand_set = set(candidate_tokens)
    intersection = len(ref_set & cand_set)
    if intersection == 0:
        return 0.0
    union = len(ref_set | cand_set)
    return intersection / union if union else 0.0


def extract_postal_code(address: str | None) -> str | None:
    if not address:
        return None
    match = _POSTAL_CODE_PATTERN.search(address)
    return match.group(1) if match else None


def split_google_type_tokens(google_type: str) -> set[str]:
    tokens: set[str] = set()
    if not google_type:
        return tokens
    fragments = re.split(r"[^a-z0-9]+", google_type)
    for fragment in fragments:
        if len(fragment) >= 3:
            tokens.add(fragment)
    return tokens


def keyword_similarity(token: str, keyword: str) -> float:
    if not token or not keyword:
        return 0.0
    if token == keyword:
        return 1.0
    return SequenceMatcher(None, token, keyword).ratio()


def build_place_query(establishment: models.Establishment, placeholder_tokens: set[str]) -> str:
    parts = [
        sanitize_placeholder(establishment.name, placeholder_tokens),
        sanitize_placeholder(establishment.libelle_commune, placeholder_tokens),
    ]
    if not parts[-1]:
        parts[-1] = sanitize_placeholder(establishment.libelle_commune_etranger, placeholder_tokens)
    parts.append(sanitize_placeholder(establishment.code_postal, placeholder_tokens))
    filtered = [part for part in parts if part]
    return " ".join(filtered)


def matches_expected_google_category(
    google_types: Iterable[str] | None,
    expected_keywords: set[str],
    *,
    neutral_types: set[str],
    similarity_threshold: float,
) -> tuple[bool, float | None]:
    if not expected_keywords:
        return True, 1.0
    if not google_types:
        return False, None
    candidate_tokens: list[str] = []
    for raw_type in google_types:
        if not isinstance(raw_type, str):
            continue
        normalized = raw_type.strip().lower()
        if not normalized or normalized in neutral_types:
            continue
        candidate_tokens.append(normalized)
        candidate_tokens.extend(split_google_type_tokens(normalized))
    if not candidate_tokens:
        _LOGGER.debug(
            "Types Google %s ignorés car uniquement neutres/inexacts pour les mots-clés %s",
            list(google_types),
            sorted(expected_keywords),
        )
        return False, None

    best_similarity = 0.0
    matched = False
    for token in candidate_tokens:
        for keyword in expected_keywords:
            similarity = keyword_similarity(token, keyword)
            if similarity >= similarity_threshold:
                matched = True
            if similarity > best_similarity:
                best_similarity = similarity
    if matched:
        return True, max(best_similarity, similarity_threshold)

    _LOGGER.debug(
        "Types Google %s rejetés : similarité maximale %.2f < %.2f pour les mots-clés %s",
        sorted(set(candidate_tokens)),
        best_similarity,
        similarity_threshold,
        sorted(expected_keywords),
    )
    return False, best_similarity if best_similarity > 0 else None


__all__ = [
    "build_place_query",
    "expand_keyword_variants",
    "extract_postal_code",
    "keyword_similarity",
    "matches_expected_google_category",
    "normalize_text",
    "sanitize_placeholder",
    "split_google_type_tokens",
    "token_similarity",
    "tokenize_name",
    "tokenize_text",
]
