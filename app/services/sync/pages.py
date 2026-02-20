"""Pagination helpers used by the synchronization collector."""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from app.db import models
from app.observability import log_event, serialize_establishment
from app.utils.dates import utcnow

from .context import SyncContext, UpdatedEstablishmentInfo

if TYPE_CHECKING:  # pragma: no cover - used for type checking only
    from .collector import SyncCollectorMixin

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

        payload = context.client.search_establishments(
            query=query,
            nombre=page_size,
            curseur=cursor_value,
            champs=champs,
            date=collector._settings.sirene.current_period_date,
            tri=tri,
        )
        header = payload.get("header", {})
        etablissements = payload.get("etablissements", [])
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

        current_cursor = cursor_value or "*"
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
