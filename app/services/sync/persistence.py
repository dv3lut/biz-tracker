"""Database persistence helpers for synchronization runs."""
from __future__ import annotations

from datetime import date, datetime
from typing import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.observability import log_event
from app.services.establishment_mapper import extract_fields
from app.utils.dates import utcnow
from app.utils.naf import normalize_naf_code

from .context import UpdatedEstablishmentInfo


class SyncPersistenceMixin:
    """Expose reusable persistence helpers leveraged by the sync collector."""

    _naf_code_cache: list[str] | None = None

    def _build_restaurant_query(
        self,
        naf_codes: Sequence[str],
        *,
        since_creation: date | None = None,
        creation_range: tuple[date, date] | None = None,
        last_treatment_from: date | None = None,
        last_treatment_to: date | None = None,
    ) -> str:
        normalized_codes: list[str] = []
        for code in naf_codes:
            normalized = normalize_naf_code(code)
            if normalized:
                normalized_codes.append(normalized)
        if not normalized_codes:
            raise RuntimeError("Aucun code NAF actif n'est disponible pour construire la requête Sirene.")

        unique_codes = sorted(set(normalized_codes))
        naf_terms = [f"activitePrincipaleEtablissement:{code}" for code in unique_codes]
        naf_query = " OR ".join(naf_terms)
        if len(naf_terms) > 1:
            naf_query = f"({naf_query})"
        period_clause = f"periode({naf_query} AND etatAdministratifEtablissement:A)"
        clauses = [period_clause]
        if creation_range:
            start, end = creation_range
            creation_clause = f"dateCreationEtablissement:[{start.isoformat()} TO {end.isoformat()}]"
            clauses.append(creation_clause)
        elif since_creation:
            creation_clause = f"dateCreationEtablissement:[{since_creation.isoformat()} TO *]"
            clauses.append(creation_clause)

        if last_treatment_from or last_treatment_to:
            if last_treatment_from and last_treatment_to:
                treatment_clause = (
                    f"dateDernierTraitementEtablissement:[{last_treatment_from.isoformat()} TO {last_treatment_to.isoformat()}]"
                )
            elif last_treatment_from:
                treatment_clause = f"dateDernierTraitementEtablissement:[{last_treatment_from.isoformat()} TO *]"
            else:
                treatment_clause = f"dateDernierTraitementEtablissement:[* TO {last_treatment_to.isoformat()}]"
            clauses.append(treatment_clause)

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
            "prenomUsuelUniteLegale",
        }
        return ",".join(sorted(fields))

    def _upsert_establishments(
        self,
        session: Session,
        etablissements: Sequence[dict[str, object]],
        run_id: UUID,
        scope_key: str | None,
    ) -> tuple[
        list[models.Establishment],
        list[UpdatedEstablishmentInfo],
        list[models.Establishment],
    ]:
        new_entities: list[models.Establishment] = []
        updated_entities: list[UpdatedEstablishmentInfo] = []
        annuaire_candidates: list[models.Establishment] = []
        annuaire_candidate_sirets: set[str] = set()
        now = utcnow()
        for payload in etablissements:
            fields = extract_fields(payload)
            siret = fields.get("siret")
            if not siret:
                log_event(
                    "sync.debug.exit.001_missing_siret",
                    run_id=str(run_id),
                    scope_key=scope_key,
                    reason="missing_siret",
                )
                continue
            if fields.get("etat_administratif") != "A":
                existing = session.get(models.Establishment, siret)
                if existing:
                    session.delete(existing)
                    log_event(
                        "sync.debug.exit.002_inactive_deleted",
                        run_id=str(run_id),
                        scope_key=scope_key,
                        siret=siret,
                        reason="inactive_establishment_deleted",
                    )
                else:
                    log_event(
                        "sync.debug.exit.003_inactive_ignored",
                        run_id=str(run_id),
                        scope_key=scope_key,
                        siret=siret,
                        reason="inactive_establishment_not_found",
                    )
                continue
            entity = session.get(models.Establishment, siret)
            if entity:
                changed_fields: list[str] = []
                for key, value in fields.items():
                    if key in {"date_creation", "date_dernier_traitement_etablissement"}:
                        continue
                    current_value = getattr(entity, key)
                    if current_value != value:
                        setattr(entity, key, value)
                        changed_fields.append(key)
                entity.last_seen_at = now
                entity.last_run_id = run_id
                if changed_fields:
                    updated_entities.append(UpdatedEstablishmentInfo(entity, changed_fields))
                    log_event(
                        "sync.debug.path.004_existing_updated",
                        run_id=str(run_id),
                        scope_key=scope_key,
                        siret=siret,
                        changed_fields=changed_fields,
                    )
                elif self._needs_annuaire_enrichment(session, entity) and siret not in annuaire_candidate_sirets:
                    annuaire_candidates.append(entity)
                    annuaire_candidate_sirets.add(siret)
                    log_event(
                        "sync.debug.path.005_existing_annuaire_candidate",
                        run_id=str(run_id),
                        scope_key=scope_key,
                        siret=siret,
                        reason="existing_without_changes_but_annuaire_needed",
                    )
                else:
                    log_event(
                        "sync.debug.exit.006_existing_no_change",
                        run_id=str(run_id),
                        scope_key=scope_key,
                        siret=siret,
                        reason="existing_no_field_change",
                    )
            else:
                fields["created_run_id"] = run_id
                fields["last_run_id"] = run_id
                entity = models.Establishment(**fields)
                entity.first_seen_at = now
                entity.last_seen_at = now
                session.add(entity)
                new_entities.append(entity)
                log_event(
                    "sync.debug.path.007_new_establishment_added",
                    run_id=str(run_id),
                    scope_key=scope_key,
                    siret=siret,
                )
        session.flush()
        return new_entities, updated_entities, annuaire_candidates

    def _needs_annuaire_enrichment(
        self,
        session: Session,
        establishment: models.Establishment,
    ) -> bool:
        if establishment.legal_unit_name is None:
            return True
        director_id = (
            session.execute(
                select(models.Director.id)
                .where(models.Director.establishment_siret == establishment.siret)
                .limit(1)
            )
            .scalars()
            .first()
        )
        return director_id is None
