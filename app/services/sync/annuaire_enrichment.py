"""Annuaire-entreprises enrichment for directors & legal unit name."""
from __future__ import annotations

import logging
from typing import Sequence

from sqlalchemy.orm import Session

from app.clients.annuaire_entreprises_client import AnnuaireEntreprisesClient, AnnuaireResult
from app.db import models
from app.observability import log_event

_LOGGER = logging.getLogger(__name__)


def enrich_establishments_from_annuaire(
    session: Session,
    establishments: Sequence[models.Establishment],
    *,
    run_id: str | None = None,
) -> dict[str, object]:
    """Fetch directors & legal-unit-name data and update establishments in-place.

    Returns a summary dict suitable for logging / run summary.
    """
    client = AnnuaireEntreprisesClient()
    if not client.enabled:
        log_event(
            "annuaire.enrichment.skipped",
            run_id=run_id,
            reason="disabled",
        )
        return {"skipped": True, "reason": "disabled"}

    if not establishments:
        return {"skipped": True, "reason": "no_establishments"}

    try:
        siren_map: dict[str, list[models.Establishment]] = {}
        for est in establishments:
            siren = est.siren
            if siren:
                siren_map.setdefault(siren, []).append(est)

        unique_sirens = list(siren_map.keys())
        results = client.fetch_batch(unique_sirens, run_id=run_id)

        enriched_count = 0
        director_found_count = 0
        legal_name_found_count = 0

        for siren, result in results.items():
            if not result.success:
                continue
            for est in siren_map.get(siren, []):
                _apply_annuaire_result(session, est, result)
                enriched_count += 1
                if result.directors:
                    director_found_count += 1
                if result.legal_unit_name:
                    legal_name_found_count += 1

        session.flush()

        summary = {
            "total_sirens": len(unique_sirens),
            "enriched_count": enriched_count,
            "director_found_count": director_found_count,
            "legal_name_found_count": legal_name_found_count,
            "failure_count": sum(1 for r in results.values() if not r.success),
        }
        log_event(
            "annuaire.enrichment.summary",
            run_id=run_id,
            **summary,
        )
        return summary
    finally:
        client.close()


def _apply_annuaire_result(
    session: Session,
    establishment: models.Establishment,
    result: AnnuaireResult,
) -> None:
    """Write annuaire data onto an establishment entity and persist directors."""
    if result.legal_unit_name:
        establishment.legal_unit_name = result.legal_unit_name

    # Replace existing directors with fresh data from the API
    establishment.directors.clear()
    for d in result.directors:
        director = models.Director(
            establishment_siret=establishment.siret,
            type_dirigeant=d.type_dirigeant,
            first_names=d.first_names,
            last_name=d.last_name,
            quality=d.quality,
            birth_month=d.birth_month,
            birth_year=d.birth_year,
            siren=d.siren,
            denomination=d.denomination,
            nationality=d.nationality,
        )
        establishment.directors.append(director)
