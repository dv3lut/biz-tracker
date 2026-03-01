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
from app.utils.dates import utcnow
from app.utils.google_listing import (
    FILTERABLE_LISTING_STATUSES,
    default_listing_statuses,
    normalize_listing_age_status,
    normalize_listing_status_filters,
)
from app.utils.naf import normalize_naf_code
from app.utils.regions import ALL_DEPARTMENT_CODES, resolve_department_code


def get_active_clients(session: Session) -> list[models.Client]:
    """Return clients whose activation window includes today."""

    today = date.today()
    stmt = (
        select(models.Client)
        .options(
            selectinload(models.Client.recipients),
            selectinload(models.Client.subscriptions)
            .selectinload(models.ClientSubscription.subcategory)
            .selectinload(models.NafSubCategory.categories),
            selectinload(models.Client.stripe_subscriptions),
            selectinload(models.Client.departments),
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
            selectinload(models.Client.subscriptions)
            .selectinload(models.ClientSubscription.subcategory)
            .selectinload(models.NafSubCategory.categories),
            selectinload(models.Client.stripe_subscriptions),
            selectinload(models.Client.departments),
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
class ClientFilterSummary:
    listing_statuses: list[str]
    naf_codes: list[str]


@dataclass
class ClientEmailPayload:
    client: models.Client
    subject: str
    text_body: str
    html_body: str | None = None
    establishments: Sequence[models.Establishment] | None = None
    filters: ClientFilterSummary | None = None
    attachments: Sequence[tuple[str, bytes, str]] | None = None
    extra_recipients: Sequence[str] | None = None


def resolve_enabled_department_codes(
    session: Session,
    *,
    on_date: date | None = None,
) -> set[str] | None:
    """Return the set of enabled department codes across active clients.

    Returns None when at least one active client targets all departments.
    Returns an empty set when no active client is configured.
    """

    clients = get_all_clients(session)
    if not clients:
        return set()
    reference_date = on_date or date.today()
    department_codes: set[str] = set()
    for client in clients:
        if not is_client_active(client, on_date=reference_date):
            continue
        client_departments = {
            department.code
            for department in getattr(client, "departments", [])
            if getattr(department, "code", None)
        }
        if not client_departments:
            return None
        department_codes.update(client_departments)
    return department_codes


def summarize_client_filters(client: models.Client) -> ClientFilterSummary:
    """Return a snapshot of listing statuses and NAF codes configured for a client."""

    listing_statuses = resolve_client_listing_statuses(client)
    naf_codes: list[str] = []
    seen_codes: set[str] = set()
    for subscription in getattr(client, "subscriptions", []) or []:
        subcategory = getattr(subscription, "subcategory", None)
        if not subcategory or not getattr(subcategory, "is_active", True):
            continue
        normalized_code = normalize_naf_code(getattr(subcategory, "naf_code", None))
        if not normalized_code or normalized_code in seen_codes:
            continue
        seen_codes.add(normalized_code)
        naf_codes.append(normalized_code)

    return ClientFilterSummary(listing_statuses=listing_statuses, naf_codes=naf_codes)


def resolve_client_listing_statuses(client: models.Client) -> list[str]:
    """Return the normalized list of listing statuses allowed for a client."""

    raw_statuses = getattr(client, "listing_statuses", None)
    try:
        statuses = normalize_listing_status_filters(raw_statuses)
    except ValueError:
        statuses = []
    if not statuses:
        return default_listing_statuses()
    return statuses


def resolve_client_department_codes(client: models.Client) -> set[str] | None:
    """Return the normalized department codes for a client, or None if all are allowed."""
    all_departments = set(ALL_DEPARTMENT_CODES)
    department_codes = {
        department.code
        for department in getattr(client, "departments", [])
        if getattr(department, "code", None)
    }
    if department_codes:
        department_codes = department_codes & all_departments
    if not department_codes or department_codes == all_departments:
        return None
    return department_codes


def resolve_client_subscription_codes(client: models.Client) -> set[str]:
    """Return the set of normalized NAF codes configured for a client."""
    codes: set[str] = set()
    for subscription in getattr(client, "subscriptions", []) or []:
        subcategory = getattr(subscription, "subcategory", None)
        if not subcategory or not getattr(subcategory, "is_active", True):
            continue
        normalized_code = normalize_naf_code(getattr(subcategory, "naf_code", None))
        if normalized_code:
            codes.add(normalized_code)
    return codes


def client_allows_listing_status(client: models.Client, listing_status: str | None) -> bool:
    """Return True if the client's filters include the provided listing status."""

    normalized_status = normalize_listing_age_status(listing_status)
    allowed = resolve_client_listing_statuses(client)
    return normalized_status in allowed


def filter_clients_by_listing_status(
    clients: Sequence[models.Client],
    listing_status: str | None,
) -> tuple[list[models.Client], bool]:
    """Filter clients according to the provided listing status and flag if filtering occurred."""

    if not clients:
        return [], False
    normalized_status = normalize_listing_age_status(listing_status)
    filtered = [client for client in clients if client_allows_listing_status(client, normalized_status)]
    filtering_applied = len(filtered) != len(clients)
    return filtered, filtering_applied


def build_subscription_index(
    clients: Sequence[models.Client],
) -> tuple[dict[UUID, set[str]], dict[str, list[models.Client]]]:
    """Return mapping client->codes and code->clients for active subscriptions."""

    subscription_map: dict[UUID, set[str]] = {}
    code_index: dict[str, dict[UUID, models.Client]] = {}
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
            code_index.setdefault(code, {})[client.id] = client
        if codes:
            subscription_map[client.id] = codes
    return subscription_map, {code: list(clients_map.values()) for code, clients_map in code_index.items()}


def build_subcategory_department_index(
    clients: Sequence[models.Client],
    *,
    include_inactive_subcategories: bool = False,
) -> tuple[dict[UUID, set[UUID]], set[UUID]]:
    """Return department coverage per subcategory for the provided clients.

    Returns:
        - a mapping subcategory_id -> set of department_ids
        - a set of subcategory_ids that target all departments
    """

    subcategory_departments: dict[UUID, set[UUID]] = {}
    subcategory_all_departments: set[UUID] = set()

    for client in clients:
        client_departments = [
            department
            for department in getattr(client, "departments", [])
            if getattr(department, "id", None) is not None
        ]
        has_all_departments = len(client_departments) == 0
        department_ids = {department.id for department in client_departments}

        for subscription in getattr(client, "subscriptions", []) or []:
            subcategory = getattr(subscription, "subcategory", None)
            if not subcategory:
                continue
            if not include_inactive_subcategories and not getattr(subcategory, "is_active", True):
                continue
            subcategory_id = subcategory.id
            if has_all_departments:
                subcategory_all_departments.add(subcategory_id)
                subcategory_departments.pop(subcategory_id, None)
                continue
            if subcategory_id in subcategory_all_departments:
                continue
            subcategory_departments.setdefault(subcategory_id, set()).update(department_ids)

    return subcategory_departments, subcategory_all_departments


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
    """Map establishments to clients according to subscriptions and allowed listing statuses."""

    subscription_map, code_index = build_subscription_index(clients)
    status_map: dict[UUID, set[str]] = {}
    status_filtering_enabled = False
    department_map: dict[UUID, set[str] | None] = {}
    department_filtering_enabled = False
    all_departments = set(ALL_DEPARTMENT_CODES)
    for client in clients:
        statuses = set(resolve_client_listing_statuses(client))
        status_map[client.id] = statuses
        if len(statuses) < len(FILTERABLE_LISTING_STATUSES):
            status_filtering_enabled = True
        department_codes = {
            department.code
            for department in getattr(client, "departments", [])
            if getattr(department, "code", None)
        }
        if department_codes:
            department_codes = department_codes & all_departments
        if not department_codes or department_codes == all_departments:
            department_map[client.id] = None
        else:
            department_filtering_enabled = True
            department_map[client.id] = department_codes

    filters_configured = bool(subscription_map) or status_filtering_enabled or department_filtering_enabled

    if not establishments:
        return {}, filters_configured

    if not subscription_map:
        assignments: dict[UUID, list[models.Establishment]] = {}
        for client in clients:
            allowed_statuses = status_map.get(client.id, set())
            allowed_departments = department_map.get(client.id)
            matches = [
                establishment
                for establishment in establishments
                if _establishment_matches_listing_status(establishment, allowed_statuses)
                and _establishment_matches_department(establishment, allowed_departments)
            ]
            if matches:
                assignments[client.id] = matches
        return assignments, filters_configured

    assignments = defaultdict(list)
    seen_sirets: dict[UUID, set[str]] = defaultdict(set)
    for establishment in establishments:
        code = normalize_naf_code(establishment.naf_code)
        if not code:
            continue
        department_code = resolve_department_code(
            getattr(establishment, "code_commune", None),
            getattr(establishment, "code_postal", None),
        )
        for client in code_index.get(code, []):
            allowed_statuses = status_map.get(client.id, set())
            if not _establishment_matches_listing_status(establishment, allowed_statuses):
                continue
            allowed_departments = department_map.get(client.id)
            if not _department_allows_establishment(department_code, allowed_departments):
                continue
            if establishment.siret in seen_sirets[client.id]:
                continue
            seen_sirets[client.id].add(establishment.siret)
            assignments[client.id].append(establishment)

    filtered = {client_id: items for client_id, items in assignments.items() if items}
    return filtered, filters_configured


def _establishment_matches_listing_status(
    establishment: models.Establishment,
    allowed_statuses: set[str],
) -> bool:
    """Check if establishment matches allowed listing statuses.
    
    Special rule: 'not_recent_creation' establishments with contacts
    (phone, email, or website) are treated as valid matches,
    similar to 'recent_creation' establishments.
    """
    directors = getattr(establishment, "directors", None) or []
    has_linkedin_profile = any(
        getattr(director, "is_physical_person", False)
        and bool(getattr(director, "linkedin_profile_url", None))
        for director in directors
    )
    if has_linkedin_profile:
        return True

    # Listing age status only describes a *found* Google listing.
    # Non-found establishments (not_found, etc.) bypass this check
    # so they can appear in the "no Google" section of client emails.
    google_check = (getattr(establishment, "google_check_status", None) or "").lower()
    if google_check and google_check != "found":
        return True

    normalized = normalize_listing_age_status(getattr(establishment, "google_listing_age_status", None))
    if not allowed_statuses:
        return normalized in FILTERABLE_LISTING_STATUSES
    
    # Si le statut normalisé est directement autorisé
    if normalized in allowed_statuses:
        return True
    
    # Règle spéciale : si c'est une création ancienne avec contacts,
    # on l'inclut si "recent_creation" est autorisé
    if normalized == "not_recent_creation" and "recent_creation" in allowed_statuses:
        has_phone = bool(getattr(establishment, "google_contact_phone", None))
        has_email = bool(getattr(establishment, "google_contact_email", None))
        has_website = bool(getattr(establishment, "google_contact_website", None))
        if has_phone or has_email or has_website:
            return True
    
    return False


def _establishment_matches_department(
    establishment: models.Establishment,
    allowed_departments: set[str] | None,
) -> bool:
    department_code = resolve_department_code(
        getattr(establishment, "code_commune", None),
        getattr(establishment, "code_postal", None),
    )
    return _department_allows_establishment(department_code, allowed_departments)


def _department_allows_establishment(
    department_code: str | None,
    allowed_departments: set[str] | None,
) -> bool:
    if allowed_departments is None:
        return True
    if not department_code:
        return False
    if department_code == "20" and ("2A" in allowed_departments or "2B" in allowed_departments):
        return True
    return department_code in allowed_departments


def count_establishments_outside_client_departments(
    client: models.Client,
    establishments: Sequence[models.Establishment],
) -> int:
    """Count establishments matching client filters but outside selected departments."""
    allowed_departments = resolve_client_department_codes(client)
    if allowed_departments is None:
        return 0
    allowed_statuses = set(resolve_client_listing_statuses(client))
    subscription_codes = resolve_client_subscription_codes(client)
    has_subscription_filter = bool(subscription_codes)
    seen_sirets: set[str] = set()
    outside_count = 0

    for establishment in establishments:
        siret = getattr(establishment, "siret", None)
        if siret and siret in seen_sirets:
            continue
        if not _establishment_matches_listing_status(establishment, allowed_statuses):
            continue
        if has_subscription_filter:
            naf_code = normalize_naf_code(getattr(establishment, "naf_code", None))
            if not naf_code or naf_code not in subscription_codes:
                continue
        department_code = resolve_department_code(
            getattr(establishment, "code_commune", None),
            getattr(establishment, "code_postal", None),
        )
        if _department_allows_establishment(department_code, allowed_departments):
            continue
        if siret:
            seen_sirets.add(siret)
        outside_count += 1

    return outside_count


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
        extra_recipients = [email for email in (payload.extra_recipients or []) if email]
        recipients = sorted({*recipients, *extra_recipients})
        if not recipients:
            continue
        if timestamp is None:
            timestamp = utcnow()
        try:
            email_service.send(
                payload.subject,
                payload.text_body,
                recipients,
                html_body=payload.html_body,
                attachments=payload.attachments,
            )
        except Exception as exc:  # noqa: BLE001 - let caller handle logging
            failed.append((client, exc))
            continue

        client.emails_sent_count += 1
        client.last_email_sent_at = timestamp
        delivered.append(client)
        recipient_map[str(client.id)] = recipients

    return ClientDispatchResult(delivered=delivered, failed=failed, recipients=recipient_map, sent_at=timestamp)
