"""Pagination helpers used by the synchronization collector."""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING

from app.db import models
from app.observability import log_event, serialize_establishment

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
    page_count: int
    duration_seconds: float


def collect_pages(
    collector: "SyncCollectorMixin",
    context: SyncContext,
    query: str,
    champs: str,
    cursor_value: str,
    tri: str,
    months_back: int,
    since_creation: date,
) -> PageCollectionResult:
    state = context.state
    page_count = 0
    collection_started = time.perf_counter()

    log_event(
        "sync.collection.started",
        run_id=str(context.run.id),
        scope_key=context.run.scope_key,
        months_back=months_back,
        since_creation=since_creation,
        page_size=collector._settings.sirene.page_size,
        initial_cursor=cursor_value,
    )

    new_entities_total: list[models.Establishment] = []
    new_entities_payload: list[dict[str, object]] = []
    updated_entities: list[UpdatedEstablishmentInfo] = []
    updated_payloads: list[dict[str, object]] = []

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

        new_entities, updated_batch = collector._upsert_establishments(context.session, etablissements, context.run.id)
        context.run.created_records += len(new_entities)
        context.run.updated_records += len(updated_batch)
        new_entities_total.extend(new_entities)
        updated_entities.extend(updated_batch)

        if new_entities:
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
        state.last_cursor = next_cursor
        context.run.last_cursor = next_cursor
        total_value = header.get("total")
        try:
            state.last_total = int(total_value) if total_value is not None else state.last_total
        except (TypeError, ValueError):
            collector._logger.debug("Valeur 'total' non exploitable: %s", total_value)
        state.last_synced_at = datetime.utcnow()
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

        if not etablissements or not next_cursor or next_cursor == header.get("curseur"):
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
    )
