"""Shared helpers for admin routers."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Sequence

from app.api.schemas import AlertOut, SyncRunOut
from app.services.sync.mode import DEFAULT_SYNC_MODE, SyncMode
from app.db import models
from app.utils.dates import utcnow


def compute_run_metrics(
    run: models.SyncRun,
    state: models.SyncState | None,
) -> tuple[int | None, float | None, float | None, datetime | None]:
    target_raw = state.last_total if state and state.last_total is not None else run.max_records
    total_expected: int | None
    try:
        total_candidate = int(target_raw) if target_raw is not None else None
    except (TypeError, ValueError):
        total_candidate = None
    total_expected = total_candidate if total_candidate and total_candidate > 0 else None

    progress: float | None = None
    if total_expected:
        progress = min(run.fetched_records / total_expected, 1.0)

    estimated_remaining_seconds: float | None = None
    estimated_completion_at: datetime | None = None
    if run.status == "running" and total_expected and run.fetched_records > 0:
        now = utcnow()
        elapsed_seconds = max((now - run.started_at).total_seconds(), 0.0)
        if elapsed_seconds > 0:
            rate = run.fetched_records / elapsed_seconds
            if rate > 0:
                remaining = max(total_expected - run.fetched_records, 0)
                estimated_remaining_seconds = remaining / rate if remaining > 0 else 0.0
                estimated_completion_at = now + timedelta(seconds=estimated_remaining_seconds)

    return total_expected, progress, estimated_remaining_seconds, estimated_completion_at


def serialize_run(run: models.SyncRun | None, *, state: models.SyncState | None = None) -> SyncRunOut | None:
    if run is None:
        return None
    enriched = SyncRunOut.model_validate(run)
    total_expected, progress, remaining_seconds, eta = compute_run_metrics(run, state)
    enriched.total_expected_records = total_expected
    enriched.progress = progress
    enriched.estimated_remaining_seconds = remaining_seconds
    enriched.estimated_completion_at = eta
    try:
        mode = SyncMode(enriched.mode)
    except ValueError:
        mode = DEFAULT_SYNC_MODE
    if not mode.requires_sirene_fetch:
        enriched.total_expected_records = None
        enriched.progress = None
        enriched.estimated_remaining_seconds = None
        enriched.estimated_completion_at = None
    return enriched


def serialize_alert(alert: models.Alert | None) -> AlertOut | None:
    if alert is None:
        return None
    return AlertOut.model_validate(alert)


def format_establishment_summary(establishment: models.Establishment, *, include_google: bool = True) -> list[str]:
    lines = [
        f"- {establishment.name or '(nom indisponible)'}",
        f"  SIRET: {establishment.siret} | NAF: {establishment.naf_code or 'N/A'}",
    ]
    address_parts = [
        element
        for element in [
            establishment.numero_voie,
            establishment.type_voie,
            establishment.libelle_voie,
        ]
        if element
    ]
    commune_parts = [
        part
        for part in [
            establishment.code_postal,
            establishment.libelle_commune or establishment.libelle_commune_etranger,
        ]
        if part
    ]
    lines.append(f"  Adresse: {' '.join(address_parts) if address_parts else 'N/A'}")
    lines.append(f"           {' '.join(commune_parts) if commune_parts else ''}")
    if establishment.date_creation:
        lines.append(f"  Création: {establishment.date_creation.isoformat()}")
    if include_google:
        if establishment.google_place_url:
            lines.append(f"  Google: {establishment.google_place_url}")
        if establishment.google_place_id:
            lines.append(f"  Place ID: {establishment.google_place_id}")
        if establishment.google_match_confidence is not None:
            lines.append(f"  Score correspondance: {establishment.google_match_confidence:.2f}")
    return lines


def normalize_emails(emails: Sequence[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for email in emails:
        if not email:
            continue
        candidate = email.strip().lower()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)
    return normalized
