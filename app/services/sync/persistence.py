"""Database persistence helpers for synchronization runs."""
from __future__ import annotations

from datetime import date, datetime
from typing import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.services.establishment_mapper import extract_fields

from .context import UpdatedEstablishmentInfo


class SyncPersistenceMixin:
    """Expose reusable persistence helpers leveraged by the sync collector."""

    _naf_code_cache: list[str] | None = None

    def _build_restaurant_query(self, naf_codes: Sequence[str], *, since_creation: date | None = None) -> str:
        normalized_codes = [code.strip() for code in naf_codes if code and code.strip()]
        if not normalized_codes:
            raise RuntimeError("Aucun code NAF actif n'est disponible pour construire la requête Sirene.")

        unique_codes = sorted(set(normalized_codes))
        naf_terms = [f"activitePrincipaleEtablissement:{code}" for code in unique_codes]
        naf_query = " OR ".join(naf_terms)
        if len(naf_terms) > 1:
            naf_query = f"({naf_query})"
        period_clause = f"periode({naf_query} AND etatAdministratifEtablissement:A)"
        clauses = [period_clause]
        if since_creation:
            creation_clause = f"dateCreationEtablissement:[{since_creation.isoformat()} TO *]"
            clauses.append(creation_clause)

        return " AND ".join(clauses)

    def _load_active_naf_codes(self, session: Session) -> list[str]:
        cached = getattr(self, "_naf_code_cache", None)
        if cached:
            return cached

        rows = (
            session.execute(
                select(models.NafSubCategory.naf_code)
                .where(models.NafSubCategory.is_active.is_(True))
                .order_by(models.NafSubCategory.naf_code.asc())
            )
            .scalars()
            .all()
        )
        naf_codes = [code for code in rows if code]
        if not naf_codes:
            raise RuntimeError(
                "Impossible de lancer la synchronisation : aucune sous-catégorie NAF active n'est configurée en base."
            )
        self._naf_code_cache = naf_codes
        return naf_codes

    def _build_fields_parameter(self) -> str:
        fields = {
            "identificationStandardEtablissement",
            "denominationUsuelleEtablissement",
            "enseigne1Etablissement",
            "enseigne2Etablissement",
            "enseigne3Etablissement",
            "categorieEntreprise",
            "categorieJuridiqueUniteLegale",
            "denominationUniteLegale",
            "denominationUsuelle1UniteLegale",
            "denominationUsuelle2UniteLegale",
            "denominationUsuelle3UniteLegale",
            "nomUsageUniteLegale",
            "nomUniteLegale",
            "prenom1UniteLegale",
        }
        return ",".join(sorted(fields))

    def _upsert_establishments(
        self,
        session: Session,
        etablissements: Sequence[dict[str, object]],
        run_id: UUID,
    ) -> tuple[list[models.Establishment], list[UpdatedEstablishmentInfo]]:
        new_entities: list[models.Establishment] = []
        updated_entities: list[UpdatedEstablishmentInfo] = []
        now = datetime.utcnow()
        for payload in etablissements:
            fields = extract_fields(payload)
            siret = fields.get("siret")
            if not siret:
                continue
            if fields.get("etat_administratif") != "A":
                existing = session.get(models.Establishment, siret)
                if existing:
                    session.delete(existing)
                continue
            entity = session.get(models.Establishment, siret)
            if entity:
                changed_fields: list[str] = []
                for key, value in fields.items():
                    current_value = getattr(entity, key)
                    if current_value != value:
                        setattr(entity, key, value)
                        changed_fields.append(key)
                entity.last_seen_at = now
                entity.last_run_id = run_id
                if changed_fields:
                    updated_entities.append(UpdatedEstablishmentInfo(entity, changed_fields))
            else:
                fields["created_run_id"] = run_id
                fields["last_run_id"] = run_id
                entity = models.Establishment(**fields)
                entity.first_seen_at = now
                entity.last_seen_at = now
                session.add(entity)
                new_entities.append(entity)
        session.flush()
        return new_entities, updated_entities
