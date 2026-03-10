"""Pagination helpers used by the synchronization collector."""
from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from app.db import models
from app.observability import log_event, serialize_establishment, serialize_exception
from app.services.client_service import get_admin_emails
from app.services.email_service import EmailService
from app.utils.dates import utcnow

from .context import SyncContext, UpdatedEstablishmentInfo

if TYPE_CHECKING:  # pragma: no cover - used for type checking only
    from .collector import SyncCollectorMixin


_LOGGER = logging.getLogger(__name__)


def _notify_admins_payload_issue(
    *,
    session: object,
    run_id: str,
    scope_key: str,
    page: int,
    cursor: str,
    field_name: str,
    payload_type: str,
    issue_kind: str,
    details: str,
) -> None:
    """Best-effort admin email notification for rare Sirene payload anomalies."""

    email_service = EmailService()
    recipients = get_admin_emails(session)
    payload = {
        "run_id": run_id,
        "scope_key": scope_key,
        "page": page,
        "cursor": cursor,
        "field": field_name,
        "payload_type": payload_type,
        "issue_kind": issue_kind,
    }

    if not recipients:
        log_event("sync.collection.payload.alert.skipped", reason="no_recipients", **payload)
        return
    if not email_service.is_enabled():
        log_event("sync.collection.payload.alert.skipped", reason="email_disabled", **payload)
        return
    if not email_service.is_configured():
        log_event("sync.collection.payload.alert.skipped", reason="email_not_configured", **payload)
        return

    subject = "Business tracker · Alerte payload Sirene invalide"
    body = "\n".join(
        [
            "Une anomalie de payload Sirene a été détectée pendant une synchronisation.",
            "",
            f"Run: {run_id}",
            f"Scope: {scope_key}",
            f"Type d'anomalie: {issue_kind}",
            f"Champ: {field_name}",
            f"Type reçu: {payload_type}",
            f"Page: {page}",
            f"Cursor: {cursor}",
            "",
            f"Détails: {details}",
        ]
    )
    try:
        email_service.send(subject, body, recipients)
    except Exception as exc:  # noqa: BLE001 - best effort notification only
        log_event(
            "sync.collection.payload.alert.error",
            level=logging.ERROR,
            reason="send_error",
            send_error=serialize_exception(exc),
            **payload,
        )
        _LOGGER.warning("Échec d'envoi de l'alerte email payload Sirene: %s", exc, exc_info=True)
        return

    log_event("sync.collection.payload.alert.sent", recipients=recipients, subject=subject, **payload)


def _coerce_mapping(
    value: object,
    *,
    session: object,
    field_name: str,
    run_id: str,
    scope_key: str,
    page: int,
    cursor: str,
) -> dict[str, object]:
    """Return a dict-like payload or raise a descriptive runtime error."""

    if isinstance(value, Mapping):
        return dict(value)

    message = (
        "Réponse Sirene invalide pendant la pagination "
        f"(field={field_name}, type={type(value).__name__}, page={page}, cursor={cursor})."
    )
    _notify_admins_payload_issue(
        session=session,
        run_id=run_id,
        scope_key=scope_key,
        page=page,
        cursor=cursor,
        field_name=field_name,
        payload_type=type(value).__name__,
        issue_kind="invalid_payload",
        details=message,
    )
    log_event(
        "sync.collection.payload.invalid",
        level=logging.ERROR,
        run_id=run_id,
        scope_key=scope_key,
        page=page,
        cursor=cursor,
        field=field_name,
        payload_type=type(value).__name__,
        payload_preview=repr(value)[:200],
        error={"type": "InvalidSirenePayload", "message": message},
    )
    _LOGGER.error(message)
    raise RuntimeError(message)


def _coerce_list_of_mappings(
    value: object,
    *,
    session: object,
    field_name: str,
    run_id: str,
    scope_key: str,
    page: int,
    cursor: str,
) -> list[dict[str, object]]:
    """Normalize payload list values to dictionaries and log malformed entries."""

    if value is None:
        return []
    if not isinstance(value, list):
        message = (
            "Réponse Sirene invalide pendant la pagination "
            f"(field={field_name}, type={type(value).__name__}, page={page}, cursor={cursor})."
        )
        _notify_admins_payload_issue(
            session=session,
            run_id=run_id,
            scope_key=scope_key,
            page=page,
            cursor=cursor,
            field_name=field_name,
            payload_type=type(value).__name__,
            issue_kind="invalid_payload",
            details=message,
        )
        log_event(
            "sync.collection.payload.invalid",
            level=logging.ERROR,
            run_id=run_id,
            scope_key=scope_key,
            page=page,
            cursor=cursor,
            field=field_name,
            payload_type=type(value).__name__,
            payload_preview=repr(value)[:200],
            error={"type": "InvalidSirenePayload", "message": message},
        )
        _LOGGER.error(message)
        raise RuntimeError(message)

    valid_items: list[dict[str, object]] = []
    invalid_types: list[str] = []
    for item in value:
        if isinstance(item, Mapping):
            valid_items.append(dict(item))
        else:
            invalid_types.append(type(item).__name__)

    if invalid_types:
        details = (
            "Réponse Sirene partiellement invalide "
            f"(field={field_name}, invalid_count={len(invalid_types)}, page={page}, cursor={cursor}, "
            f"types={invalid_types[:10]})."
        )
        _notify_admins_payload_issue(
            session=session,
            run_id=run_id,
            scope_key=scope_key,
            page=page,
            cursor=cursor,
            field_name=field_name,
            payload_type="list[mixed]",
            issue_kind="invalid_payload_items",
            details=details,
        )
        log_event(
            "sync.collection.payload.items.invalid",
            level=logging.WARNING,
            run_id=run_id,
            scope_key=scope_key,
            page=page,
            cursor=cursor,
            field=field_name,
            invalid_item_count=len(invalid_types),
            invalid_item_types=invalid_types[:10],
        )
        _LOGGER.warning(
            "Réponse Sirene partiellement invalide (field=%s, page=%s, cursor=%s, invalid_count=%s, types=%s)",
            field_name,
            page,
            cursor,
            len(invalid_types),
            invalid_types[:10],
        )

    return valid_items

@dataclass
class PageCollectionResult:
    """Summaries produced after iterating over Sirene pages."""

    new_entities: list[models.Establishment]
    new_payloads: list[dict[str, object]]
    updated_entities: list[UpdatedEstablishmentInfo]
    updated_payloads: list[dict[str, object]]
    annuaire_candidates: list[models.Establishment]
    page_count: int
    duration_seconds: float
    max_creation_date: date | None


def collect_pages(
    collector: "SyncCollectorMixin",
    context: SyncContext,
    query: str,
    champs: str,
    cursor_value: str,
    tri: str,
    months_back: int,
    since_creation: date | None,
    creation_range: tuple[date, date] | None,
    persist_state: bool,
) -> PageCollectionResult:
    state = context.state
    page_count = 0
    collection_started = time.perf_counter()

    creation_range_payload = None
    if creation_range:
        creation_range_payload = {
            "start": creation_range[0].isoformat(),
            "end": creation_range[1].isoformat(),
        }

    log_event(
        "sync.collection.started",
        run_id=str(context.run.id),
        scope_key=context.run.scope_key,
        months_back=months_back,
        since_creation=since_creation.isoformat() if since_creation else None,
        creation_range=creation_range_payload,
        page_size=collector._settings.sirene.page_size,
        initial_cursor=cursor_value,
    )

    new_entities_total: list[models.Establishment] = []
    new_entities_payload: list[dict[str, object]] = []
    updated_entities: list[UpdatedEstablishmentInfo] = []
    updated_payloads: list[dict[str, object]] = []
    annuaire_candidates: list[models.Establishment] = []
    max_creation_date: date | None = state.last_creation_date if persist_state else None

    while True:
        page_size = collector._settings.sirene.page_size
        page_count += 1
        page_started = time.perf_counter()
        current_cursor = cursor_value or "*"

        raw_payload = context.client.search_establishments(
            query=query,
            nombre=page_size,
            curseur=cursor_value,
            champs=champs,
            date=collector._settings.sirene.current_period_date,
            tri=tri,
        )
        payload = _coerce_mapping(
            raw_payload,
            session=context.session,
            field_name="payload",
            run_id=str(context.run.id),
            scope_key=context.run.scope_key,
            page=page_count,
            cursor=current_cursor,
        )
        header = _coerce_mapping(
            payload.get("header", {}),
            session=context.session,
            field_name="header",
            run_id=str(context.run.id),
            scope_key=context.run.scope_key,
            page=page_count,
            cursor=current_cursor,
        )
        etablissements = _coerce_list_of_mappings(
            payload.get("etablissements", []),
            session=context.session,
            field_name="etablissements",
            run_id=str(context.run.id),
            scope_key=context.run.scope_key,
            page=page_count,
            cursor=current_cursor,
        )
        sirets = [item.get("siret") for item in etablissements if item.get("siret")]
        unique_sirets_count = len(set(sirets))
        duplicate_sirets_count = len(sirets) - unique_sirets_count
        last_treatment_values = [
            item.get("dateDernierTraitementEtablissement")
            for item in etablissements
            if item.get("dateDernierTraitementEtablissement")
        ]
        last_treatment_min = min(last_treatment_values) if last_treatment_values else None
        last_treatment_max = max(last_treatment_values) if last_treatment_values else None
        log_event(
            "sync.debug.page.104_payload_profile",
            run_id=str(context.run.id),
            scope_key=context.run.scope_key,
            page=page_count,
            fetched=len(etablissements),
            unique_sirets_count=unique_sirets_count,
            duplicate_sirets_count=duplicate_sirets_count,
            last_treatment_min=last_treatment_min,
            last_treatment_max=last_treatment_max,
            sample_sirets=sirets[:5],
        )
        context.run.api_call_count += 1
        context.run.fetched_records += len(etablissements)

        new_entities, updated_batch, annuaire_batch = collector._upsert_establishments(
            context.session,
            etablissements,
            context.run.id,
            context.run.scope_key,
        )
        context.run.created_records += len(new_entities)
        context.run.updated_records += len(updated_batch)
        new_entities_total.extend(new_entities)
        updated_entities.extend(updated_batch)
        annuaire_candidates.extend(annuaire_batch)

        if new_entities:
            for entity in new_entities:
                creation_date = entity.date_creation
                if creation_date and (max_creation_date is None or creation_date > max_creation_date):
                    max_creation_date = creation_date
            batch_payload = [serialize_establishment(entity) for entity in new_entities]
            new_entities_payload.extend(batch_payload)
            log_event(
                "sync.new_establishments.batch",
                run_id=str(context.run.id),
                scope_key=context.run.scope_key,
                page=page_count,
                count=len(batch_payload),
                establishments=batch_payload,
            )
            for establishment_payload in batch_payload:
                log_event(
                    "sync.new_establishment",
                    run_id=str(context.run.id),
                    scope_key=context.run.scope_key,
                    establishment=establishment_payload,
                )

        if updated_batch:
            updated_batch_payload: list[dict[str, object]] = []
            for info in updated_batch:
                payload_item = serialize_establishment(info.establishment)
                payload_item["changed_fields"] = list(info.changed_fields)
                updated_batch_payload.append(payload_item)
                log_event(
                    "sync.updated_establishment",
                    run_id=str(context.run.id),
                    scope_key=context.run.scope_key,
                    establishment=payload_item,
                )
            updated_payloads.extend(updated_batch_payload)
            log_event(
                "sync.updated_establishments.batch",
                run_id=str(context.run.id),
                scope_key=context.run.scope_key,
                page=page_count,
                count=len(updated_batch_payload),
                establishments=updated_batch_payload,
            )

        next_cursor = header.get("curseurSuivant")
        total_value = header.get("total")
        if persist_state:
            state.last_cursor = next_cursor
            context.run.last_cursor = next_cursor
            try:
                state.last_total = int(total_value) if total_value is not None else state.last_total
            except (TypeError, ValueError):
                collector._logger.debug("Valeur 'total' non exploitable: %s", total_value)
            state.last_synced_at = utcnow()
            context.session.flush()
            context.session.commit()

        page_duration = time.perf_counter() - page_started
        log_event(
            "sync.page.processed",
            run_id=str(context.run.id),
            scope_key=context.run.scope_key,
            page=page_count,
            fetched=len(etablissements),
            created=len(new_entities),
            api_call_count=context.run.api_call_count,
            cursor=current_cursor,
            next_cursor=next_cursor,
            reported_total=total_value,
            duration_seconds=page_duration,
        )

        if not etablissements:
            log_event(
                "sync.debug.exit.101_stop_pagination_empty_page",
                run_id=str(context.run.id),
                scope_key=context.run.scope_key,
                page=page_count,
                reason="empty_page",
            )
            if persist_state:
                state.cursor_completed = True
            break

        if not next_cursor:
            log_event(
                "sync.debug.exit.102_stop_pagination_no_next_cursor",
                run_id=str(context.run.id),
                scope_key=context.run.scope_key,
                page=page_count,
                reason="missing_next_cursor",
            )
            if persist_state:
                state.cursor_completed = True
            break

        if next_cursor == header.get("curseur"):
            log_event(
                "sync.debug.exit.103_stop_pagination_stuck_cursor",
                run_id=str(context.run.id),
                scope_key=context.run.scope_key,
                page=page_count,
                cursor=current_cursor,
                next_cursor=next_cursor,
                reason="next_cursor_equals_current",
            )
            if persist_state:
                state.cursor_completed = True
            break

        cursor_value = next_cursor

    duration = time.perf_counter() - collection_started
    return PageCollectionResult(
        new_entities=new_entities_total,
        new_payloads=new_entities_payload,
        updated_entities=updated_entities,
        updated_payloads=updated_payloads,
        page_count=page_count,
        duration_seconds=duration,
        max_creation_date=max_creation_date,
        annuaire_candidates=annuaire_candidates,
    )
