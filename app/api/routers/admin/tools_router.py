"""Admin endpoints for development tools."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.schemas import SireneNewBusinessesRequest, SireneNewBusinessesResponse, SireneNewBusinessOut
from app.api.schemas.tools import AnnuaireDebugResponse, SireneNewBusinessDirectorOut
from app.clients.annuaire_entreprises_client import AnnuaireEntreprisesClient
from app.clients.sirene_client import SireneClient
from app.observability import log_event
from app.services.establishment_mapper import extract_fields
from app.services.sync_service import SyncService
from app.utils.business_types import is_individual_company
from app.utils.regions import normalize_department_codes, resolve_department_code

router = APIRouter(tags=["admin"])


def _parse_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _build_leader_name(fields: dict[str, object]) -> str | None:
    prenom = str(fields.get("prenom_usuel") or fields.get("prenom1") or "").strip()
    nom = str(fields.get("nom_usage") or fields.get("nom") or "").strip()
    if prenom and nom:
        return f"{prenom} {nom}"
    if prenom:
        return prenom
    if nom:
        return nom
    return None


@router.post(
    "/tools/sirene/new-establishments",
    response_model=SireneNewBusinessesResponse,
    summary="Rechercher les nouveaux établissements Sirene",
)
def fetch_sirene_new_establishments(payload: SireneNewBusinessesRequest) -> SireneNewBusinessesResponse:
    end_date = payload.end_date or payload.start_date
    service = SyncService()
    query = service._build_restaurant_query(
        payload.naf_codes,
        creation_range=(payload.start_date, end_date),
    )

    client = SireneClient()
    try:
        response = client.search_establishments(
            query=query,
            nombre=payload.limit,
            curseur="*",
            champs=service._build_fields_parameter(),
            tri="dateCreationEtablissement desc",
        )
    finally:
        client.close()

    header = response.get("header") if isinstance(response, dict) else None
    if not isinstance(header, dict):
        header = {}

    total = _parse_int(header.get("total"))
    establishments_payload = response.get("etablissements", []) if isinstance(response, dict) else []
    if not isinstance(establishments_payload, list):
        establishments_payload = []

    region_filter = {code.strip().upper() for code in (payload.department_codes or []) if code}
    department_filter = set(normalize_department_codes(region_filter))
    establishments: list[SireneNewBusinessOut] = []
    for item in establishments_payload:
        if not isinstance(item, dict):
            continue
        fields = extract_fields(item)
        siret = fields.get("siret")
        if not siret:
            continue
        if department_filter:
            department_code = resolve_department_code(fields.get("code_commune"), fields.get("code_postal"))
            if not department_code:
                continue
            if department_code == "20" and ("2A" in department_filter or "2B" in department_filter):
                pass
            elif department_code not in department_filter:
                continue
        is_individual = is_individual_company(fields.get("categorie_juridique"))
        leader_name = _build_leader_name(fields)
        establishments.append(
            SireneNewBusinessOut(
                siret=siret,
                siren=fields.get("siren"),
                nic=fields.get("nic"),
                name=fields.get("name"),
                naf_code=fields.get("naf_code"),
                naf_label=fields.get("naf_libelle"),
                date_creation=fields.get("date_creation"),
                is_individual=is_individual,
                leader_name=leader_name,
                denomination_unite_legale=fields.get("denomination_unite_legale"),
                denomination_usuelle_unite_legale=fields.get("denomination_usuelle_unite_legale"),
                denomination_usuelle_etablissement=fields.get("denomination_usuelle_etablissement"),
                enseigne1=fields.get("enseigne1"),
                enseigne2=fields.get("enseigne2"),
                enseigne3=fields.get("enseigne3"),
                complement_adresse=fields.get("complement_adresse"),
                numero_voie=fields.get("numero_voie"),
                indice_repetition=fields.get("indice_repetition"),
                type_voie=fields.get("type_voie"),
                libelle_voie=fields.get("libelle_voie"),
                code_postal=fields.get("code_postal"),
                libelle_commune=fields.get("libelle_commune"),
                libelle_commune_etranger=fields.get("libelle_commune_etranger"),
            )
        )

    returned = len(establishments)
    if total == 0 and returned > 0:
        total = returned

    # Optionally enrich with annuaire data (directors + legal unit name)
    if payload.enrich_annuaire and establishments:
        _enrich_tools_results_from_annuaire(establishments)

    log_event(
        "tools.sirene.new_businesses",
        start_date=payload.start_date.isoformat(),
        end_date=end_date.isoformat(),
        naf_codes=payload.naf_codes,
        region_codes=None,
        department_codes=sorted(department_filter) if department_filter else None,
        total=total,
        returned=returned,
        limit=payload.limit,
        enrich_annuaire=payload.enrich_annuaire,
    )

    return SireneNewBusinessesResponse(
        total=total,
        returned=returned,
        establishments=establishments,
    )


@router.get(
    "/tools/annuaire/debug",
    response_model=AnnuaireDebugResponse,
    summary="Debug annuaire (dirigeants + unité légale) via SIRET/SIREN",
)
def debug_annuaire_api(
    siret: str = Query(..., min_length=9, max_length=14, description="SIRET (14) ou SIREN (9)"),
) -> AnnuaireDebugResponse:
    normalized = siret.replace(" ", "")
    siren = normalized[:9]
    client = AnnuaireEntreprisesClient()
    try:
        if not client.enabled:
            return AnnuaireDebugResponse(
                siret=normalized,
                siren=siren,
                success=False,
                status_code=None,
                error="annuaire disabled",
                payload=None,
            )
        result = client.fetch_debug(siren)
        result["siret"] = normalized
        result["siren"] = siren
        log_event(
            "tools.annuaire.debug",
            siret=normalized,
            siren=siren,
            success=result.get("success"),
            status_code=result.get("status_code"),
        )
        return AnnuaireDebugResponse(**result)
    finally:
        client.close()


def _enrich_tools_results_from_annuaire(
    establishments: list[SireneNewBusinessOut],
) -> None:
    """Enrich tools results with directors & legal unit name from the annuaire API."""
    siren_map: dict[str, list[SireneNewBusinessOut]] = {}
    for est in establishments:
        if est.siren:
            siren_map.setdefault(est.siren, []).append(est)

    if not siren_map:
        return

    client = AnnuaireEntreprisesClient()
    try:
        if not client.enabled:
            return
        results = client.fetch_batch(list(siren_map.keys()))
        for siren, annuaire_result in results.items():
            if not annuaire_result.success:
                continue
            for est in siren_map.get(siren, []):
                if annuaire_result.legal_unit_name:
                    est.legal_unit_name = annuaire_result.legal_unit_name
                est.directors = [
                    SireneNewBusinessDirectorOut(
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
                    for d in annuaire_result.directors
                ]
    finally:
        client.close()


__all__ = ["router"]
