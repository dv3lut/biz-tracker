from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.services.google_business.google_matching import tokenize_text


def sanitize_naf_code(naf_code: str | None) -> str:
    if not naf_code:
        return ""
    return "".join(ch for ch in naf_code.upper() if ch.isalnum())


def build_naf_keyword_map(session: Session) -> dict[str, set[str]]:
    stmt = (
        select(
            models.NafSubCategory.naf_code,
            models.NafSubCategory.name,
            models.NafCategory.name,
            models.NafCategory.keywords,
        )
        .join(models.NafCategory, models.NafCategory.id == models.NafSubCategory.category_id)
        .where(models.NafSubCategory.is_active.is_(True))
    )
    mapping: dict[str, set[str]] = {}
    for naf_code, sub_name, category_name, category_keywords in session.execute(stmt):
        normalized_code = sanitize_naf_code(naf_code)
        if not normalized_code:
            continue
        keywords = tokenize_text(sub_name)
        keywords |= tokenize_text(category_name)
        if category_keywords:
            for keyword in category_keywords:
                keywords |= tokenize_text(keyword)
        if keywords:
            mapping[normalized_code] = keywords
    return mapping


def resolve_expected_keywords(
    naf_keyword_map: dict[str, set[str]],
    establishment: models.Establishment,
) -> set[str]:
    keywords = set(tokenize_text(establishment.naf_libelle))
    naf_code = sanitize_naf_code(establishment.naf_code)
    if naf_code:
        keywords |= naf_keyword_map.get(naf_code, set())
    return keywords
