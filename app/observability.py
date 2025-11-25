"""Utilities for emitting structured observability events."""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any, Mapping, MutableMapping
from uuid import UUID

from app.config import get_settings

_OBSERVABILITY_LOGGER = logging.getLogger("observability")


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


def _normalize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_normalize(item) for item in value]
    if isinstance(value, (datetime, date, UUID)):
        return _json_default(value)
    return value


def log_event(event_name: str, *, level: int = logging.INFO, message: str | None = None, **fields: Any) -> None:
    settings = get_settings()
    payload: MutableMapping[str, Any] = {
        "@timestamp": datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
        "event": {"name": event_name},
        "service": {"name": settings.logging.service_name},
    }
    if message:
        payload["message"] = message
    if fields:
        payload.update({key: _normalize(value) for key, value in fields.items()})

    serialized = json.dumps(payload, default=_json_default, ensure_ascii=False, separators=(",", ":"))
    _OBSERVABILITY_LOGGER.log(
        level,
        serialized,
        extra={
            "elastic_doc": payload,
            "service_name": settings.logging.service_name,
        },
    )


def serialize_establishment(establishment: "Any") -> dict[str, Any]:
    from app.db import models

    if not isinstance(establishment, models.Establishment):
        raise TypeError("serialize_establishment expects a models.Establishment instance")

    return {
        "siret": establishment.siret,
        "siren": establishment.siren,
        "naf": {
            "code": establishment.naf_code,
            "libelle": establishment.naf_libelle,
        },
        "identity": {
            "name": establishment.name,
            "denomination_unite_legale": establishment.denomination_unite_legale,
            "denomination_usuelle_unite_legale": establishment.denomination_usuelle_unite_legale,
            "denomination_usuelle_etablissement": establishment.denomination_usuelle_etablissement,
            "enseigne": [value for value in [establishment.enseigne1, establishment.enseigne2, establishment.enseigne3] if value],
            "categorie_juridique": establishment.categorie_juridique,
            "categorie_entreprise": establishment.categorie_entreprise,
            "tranche_effectifs": establishment.tranche_effectifs,
            "annee_effectifs": establishment.annee_effectifs,
            "nom_usage": establishment.nom_usage,
            "nom": establishment.nom,
            "prenom1": establishment.prenom1,
        },
        "adresse": {
            "numero_voie": establishment.numero_voie,
            "indice_repetition": establishment.indice_repetition,
            "type_voie": establishment.type_voie,
            "libelle_voie": establishment.libelle_voie,
            "complement_adresse": establishment.complement_adresse,
            "code_postal": establishment.code_postal,
            "libelle_commune": establishment.libelle_commune,
            "libelle_commune_etranger": establishment.libelle_commune_etranger,
            "code_commune": establishment.code_commune,
            "code_pays": establishment.code_pays,
            "libelle_pays": establishment.libelle_pays,
            "code_cedex": establishment.code_cedex,
            "libelle_cedex": establishment.libelle_cedex,
            "distribution_speciale": establishment.distribution_speciale,
        },
        "dates": {
            "date_creation": establishment.date_creation,
            "date_debut_activite": establishment.date_debut_activite,
            "date_dernier_traitement_etablissement": establishment.date_dernier_traitement_etablissement,
            "date_dernier_traitement_unite_legale": establishment.date_dernier_traitement_unite_legale,
            "first_seen_at": establishment.first_seen_at,
            "last_seen_at": establishment.last_seen_at,
            "updated_at": establishment.updated_at,
        },
        "etat_administratif": establishment.etat_administratif,
        "google": {
            "place_id": establishment.google_place_id,
            "place_url": establishment.google_place_url,
            "last_checked_at": establishment.google_last_checked_at,
            "last_found_at": establishment.google_last_found_at,
            "check_status": establishment.google_check_status,
            "match_confidence": establishment.google_match_confidence,
        },
        "run": {
            "created_run_id": str(establishment.created_run_id) if establishment.created_run_id else None,
            "last_run_id": str(establishment.last_run_id) if establishment.last_run_id else None,
        },
    }


def serialize_alert(alert: "Any") -> dict[str, Any]:
    from app.db import models

    if not isinstance(alert, models.Alert):
        raise TypeError("serialize_alert expects a models.Alert instance")

    return {
        "id": str(alert.id),
        "run_id": str(alert.run_id),
        "siret": alert.siret,
        "recipients": list(alert.recipients or []),
        "payload": _normalize(alert.payload),
        "created_at": alert.created_at,
        "sent_at": alert.sent_at,
    }


def serialize_sync_run(run: "Any") -> dict[str, Any]:
    from app.db import models

    if not isinstance(run, models.SyncRun):
        raise TypeError("serialize_sync_run expects a models.SyncRun instance")

    return {
        "id": str(run.id),
        "scope_key": run.scope_key,
        "run_type": run.run_type,
        "status": run.status,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "api_call_count": run.api_call_count,
        "fetched_records": run.fetched_records,
        "created_records": run.created_records,
        "last_cursor": run.last_cursor,
        "notes": run.notes,
        "resumed_from_run_id": str(run.resumed_from_run_id) if run.resumed_from_run_id else None,
    }
