"""Helpers to manage client and admin email recipients."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Sequence

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.db import models
from app.services.email_service import EmailService


def get_active_clients(session: Session) -> list[models.Client]:
    """Return clients whose activation window includes today."""

    today = date.today()
    stmt = (
        select(models.Client)
        .options(selectinload(models.Client.recipients))
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

    stmt = select(models.Client).options(selectinload(models.Client.recipients)).order_by(models.Client.name)
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


def dispatch_email_to_clients(
    email_service: EmailService,
    clients: Sequence[models.Client],
    subject: str,
    body: str,
    *,
    html_body: str | None = None,
) -> ClientDispatchResult:
    """Send a message to each client and update counters."""

    delivered: list[models.Client] = []
    failed: list[tuple[models.Client, Exception]] = []
    recipient_map: dict[str, list[str]] = {}
    timestamp: datetime | None = None
    today = date.today()

    for client in clients:
        if not is_client_active(client, on_date=today):
            continue
        recipients = [recipient.email for recipient in client.recipients if recipient.email]
        if not recipients:
            continue
        if timestamp is None:
            timestamp = datetime.utcnow()
        try:
            email_service.send(subject, body, recipients, html_body=html_body)
        except Exception as exc:  # noqa: BLE001 - let caller handle logging
            failed.append((client, exc))
            continue

        client.emails_sent_count += 1
        client.last_email_sent_at = timestamp
        delivered.append(client)
        recipient_map[str(client.id)] = recipients

    return ClientDispatchResult(delivered=delivered, failed=failed, recipients=recipient_map, sent_at=timestamp)
