"""Helpers to manage client and admin email recipients."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from typing import Sequence
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.db import models
from app.services.email_service import EmailService
from app.utils.naf import normalize_naf_code


def get_active_clients(session: Session) -> list[models.Client]:
    """Return clients whose activation window includes today."""

    today = date.today()
    stmt = (
        select(models.Client)
        .options(
            selectinload(models.Client.recipients),
            selectinload(models.Client.subscriptions).selectinload(models.ClientSubscription.subcategory),
        )
        .where(
            models.Client.start_date <= today,
            or_(models.Client.end_date.is_(None), models.Client.end_date >= today),
        )
        .order_by(models.Client.name)
    )
    return list(session.execute(stmt).scalars())


def is_client_active(client: models.Client, *, on_date: date | None = None) -> bool:
    """Check whether the client is active for the given date (defaults to today)."""

    reference_date = on_date or date.today()
    if client.start_date > reference_date:
        return False
    if client.end_date and client.end_date < reference_date:
        return False
    return True


def get_admin_emails(session: Session) -> list[str]:
    """Fetch the sorted list of administrative summary recipients."""

    emails = session.execute(
        select(models.AdminRecipient.email).order_by(models.AdminRecipient.email)
    ).scalars()
    return [email for email in emails if email]


def get_all_clients(session: Session) -> list[models.Client]:
    """Return every client with recipients eagerly loaded."""

    stmt = (
        select(models.Client)
        .options(
            selectinload(models.Client.recipients),
            selectinload(models.Client.subscriptions).selectinload(models.ClientSubscription.subcategory),
        )
        .order_by(models.Client.name)
    )
    return list(session.execute(stmt).scalars())


def collect_client_emails(clients: list[models.Client]) -> list[str]:
    """Flatten recipient addresses from the provided clients and deduplicate them."""

    emails: set[str] = set()
    for client in clients:
        for recipient in client.recipients:
            if recipient.email:
                emails.add(recipient.email)
    return sorted(emails)


@dataclass
class ClientDispatchResult:
    delivered: list[models.Client]
    failed: list[tuple[models.Client, Exception]]
    recipients: dict[str, list[str]]
    sent_at: datetime | None


@dataclass
class ClientEmailPayload:
    client: models.Client
    subject: str
    text_body: str
    html_body: str | None = None
    establishments: Sequence[models.Establishment] | None = None


def build_subscription_index(
    clients: Sequence[models.Client],
) -> tuple[dict[UUID, set[str]], dict[str, list[models.Client]]]:
    """Return mapping client->codes and code->clients for active subscriptions."""

    subscription_map: dict[UUID, set[str]] = {}
    code_index: dict[str, list[models.Client]] = {}
    for client in clients:
        codes: set[str] = set()
        for subscription in getattr(client, "subscriptions", []) or []:
            subcategory = subscription.subcategory
            if not subcategory or not subcategory.is_active:
                continue
            code = normalize_naf_code(subcategory.naf_code)
            if not code:
                continue
            codes.add(code)
            code_index.setdefault(code, []).append(client)
        if codes:
            subscription_map[client.id] = codes
    return subscription_map, code_index


def filter_clients_for_naf_code(
    clients: Sequence[models.Client],
    naf_code: str | None,
) -> tuple[list[models.Client], bool]:
    """Return clients subscribed to the provided code and whether filtering occurred."""

    subscription_map, code_index = build_subscription_index(clients)
    normalized = normalize_naf_code(naf_code)
    if not subscription_map or not normalized:
        return list(clients), False
    return list(code_index.get(normalized, [])), True


def assign_establishments_to_clients(
    clients: Sequence[models.Client],
    establishments: Sequence[models.Establishment],
) -> tuple[dict[UUID, list[models.Establishment]], bool]:
    """Map establishments to clients according to active subscriptions."""

    subscription_map, code_index = build_subscription_index(clients)
    if not subscription_map:
        return {client.id: list(establishments) for client in clients if establishments}, False

    assignments: dict[UUID, list[models.Establishment]] = defaultdict(list)
    seen_sirets: dict[UUID, set[str]] = defaultdict(set)
    for establishment in establishments:
        code = normalize_naf_code(establishment.naf_code)
        if not code:
            continue
        for client in code_index.get(code, []):
            if establishment.siret in seen_sirets[client.id]:
                continue
            seen_sirets[client.id].add(establishment.siret)
            assignments[client.id].append(establishment)

    filtered = {client_id: items for client_id, items in assignments.items() if items}
    return filtered, True


def dispatch_email_to_clients(
    email_service: EmailService,
    payloads: Sequence[ClientEmailPayload],
) -> ClientDispatchResult:
    """Send segmented messages to clients and update counters."""

    delivered: list[models.Client] = []
    failed: list[tuple[models.Client, Exception]] = []
    recipient_map: dict[str, list[str]] = {}
    timestamp: datetime | None = None
    today = date.today()

    for payload in payloads:
        client = payload.client
        if not is_client_active(client, on_date=today):
            continue
        recipients = [recipient.email for recipient in client.recipients if recipient.email]
        if not recipients:
            continue
        if timestamp is None:
            timestamp = datetime.utcnow()
        try:
            email_service.send(payload.subject, payload.text_body, recipients, html_body=payload.html_body)
        except Exception as exc:  # noqa: BLE001 - let caller handle logging
            failed.append((client, exc))
            continue

        client.emails_sent_count += 1
        client.last_email_sent_at = timestamp
        delivered.append(client)
        recipient_map[str(client.id)] = recipients

    return ClientDispatchResult(delivered=delivered, failed=failed, recipients=recipient_map, sent_at=timestamp)
