"""Utilities to export data snapshots (Excel, CSV, etc.)."""
from __future__ import annotations

import json
from io import BytesIO
from typing import Iterable

from openpyxl import Workbook
from openpyxl.utils import get_column_letter

from app.db import models


def _format_datetime(value: object | None) -> str | None:
    if value is None:
        return None
    return getattr(value, "isoformat", lambda: str(value))()


def _compose_address(establishment: models.Establishment) -> str:
    parts = [
        establishment.numero_voie,
        establishment.indice_repetition,
        establishment.type_voie,
        establishment.libelle_voie,
    ]
    return " ".join(filter(None, parts)).strip()


def build_google_places_workbook(establishments: Iterable[models.Establishment]) -> BytesIO:
    """Generate an Excel workbook listing establishments enriched with Google Places."""

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Google Places"
    headers = [
        "SIRET",
        "Nom",
        "Adresse",
        "Code postal",
        "Commune",
        "Pays",
        "Google Place ID",
        "Google Place URL",
        "Statut Google",
        "Dernière vérification",
        "Dernière détection",
        "Run de création",
        "Run le plus récent",
        "Vu en premier",
        "Vu en dernier",
    ]
    sheet.append(headers)

    for establishment in establishments:
        sheet.append(
            [
                establishment.siret,
                establishment.name,
                _compose_address(establishment),
                establishment.code_postal,
                establishment.libelle_commune or establishment.libelle_commune_etranger,
                establishment.code_pays,
                establishment.google_place_id,
                establishment.google_place_url,
                establishment.google_check_status,
                _format_datetime(establishment.google_last_checked_at),
                _format_datetime(establishment.google_last_found_at),
                str(establishment.created_run_id) if establishment.created_run_id else None,
                str(establishment.last_run_id) if establishment.last_run_id else None,
                _format_datetime(establishment.first_seen_at),
                _format_datetime(establishment.last_seen_at),
            ]
        )

    sheet.freeze_panes = "A2"

    for column in sheet.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                value_length = len(str(cell.value)) if cell.value is not None else 0
            except Exception:  # pragma: no cover - defensive
                value_length = 0
            max_length = max(max_length, value_length)
        sheet.column_dimensions[column_letter].width = min(max(max_length + 2, 12), 60)

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer


def build_alerts_workbook(alerts: Iterable[models.Alert]) -> BytesIO:
    """Generate an Excel workbook listing alerts filtered by business creation date."""

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Alertes"
    headers = [
        "Date création",
        "Date alerte",
        "Date envoi",
        "SIRET",
        "Nom",
        "Adresse",
        "Code postal",
        "Commune",
        "Pays",
        "NAF",
        "Catégorie entreprise",
        "Catégorie juridique",
        "Run ID",
        "Scope",
        "Destinataires",
        "Payload",
    ]
    sheet.append(headers)

    for alert in alerts:
        establishment = alert.establishment
        if establishment is None:
            continue

        payload_str = json.dumps(alert.payload or {}, ensure_ascii=False)
        recipients = ", ".join(alert.recipients or [])
        sheet.append(
            [
                establishment.date_creation.isoformat() if establishment.date_creation else None,
                _format_datetime(alert.created_at),
                _format_datetime(alert.sent_at),
                establishment.siret,
                establishment.name,
                _compose_address(establishment),
                establishment.code_postal,
                establishment.libelle_commune or establishment.libelle_commune_etranger,
                establishment.code_pays,
                establishment.naf_code,
                establishment.categorie_entreprise,
                establishment.categorie_juridique,
                str(alert.run_id) if alert.run_id else None,
                alert.run.scope_key if alert.run else None,
                recipients,
                payload_str,
            ]
        )

    sheet.freeze_panes = "A2"

    for column in sheet.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                value_length = len(str(cell.value)) if cell.value is not None else 0
            except Exception:  # pragma: no cover - defensive
                value_length = 0
            max_length = max(max_length, value_length)
        sheet.column_dimensions[column_letter].width = min(max(max_length + 2, 12), 60)

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer
