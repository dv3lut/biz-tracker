"""Helper functions for the admin client router."""
from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.schemas import ClientCreate, ClientOut, ClientUpdate
from app.db import models
from app.services.regions_service import list_departments

from .common import normalize_emails


def _validate_activation_window(start_date: date, end_date: date | None) -> None:
    if end_date and end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="La date de fin doit être postérieure ou égale à la date de début.",
        )


def _normalize_name(name: str) -> str:
    normalized = name.strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Le nom du client est obligatoire.",
        )
    return normalized


def _client_eager_load() -> tuple[selectinload, ...]:
    return (
        selectinload(models.Client.recipients),
        selectinload(models.Client.subscriptions).selectinload(models.ClientSubscription.subcategory),
        selectinload(models.Client.stripe_subscriptions),
        selectinload(models.Client.departments),
        selectinload(models.Client.subscription_events),
    )


def _get_client_or_404(session: Session, client_id: UUID) -> models.Client:
    stmt = (
        select(models.Client)
        .where(models.Client.id == client_id)
        .options(*_client_eager_load())
    )
    client = session.execute(stmt).scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client introuvable.")
    return client


def _apply_recipients(client: models.Client, recipients: list[str]) -> None:
    normalized = normalize_emails(recipients)
    existing_by_email = {recipient.email: recipient for recipient in client.recipients}
    updated: list[models.ClientRecipient] = []
    for email in normalized:
        current = existing_by_email.pop(email, None)
        if current is not None:
            updated.append(current)
        else:
            updated.append(models.ClientRecipient(email=email))
    client.recipients = updated


def _apply_subscriptions(session: Session, client: models.Client, subscription_ids: list[UUID]) -> None:
    unique_ids: list[UUID] = []
    seen: set[UUID] = set()
    for sub_id in subscription_ids:
        if sub_id in seen:
            continue
        seen.add(sub_id)
        unique_ids.append(sub_id)

    if not unique_ids:
        client.subscriptions = []
        return

    stmt = (
        select(models.NafSubCategory)
        .where(
            models.NafSubCategory.id.in_(unique_ids),
            models.NafSubCategory.is_active.is_(True),
        )
    )
    subcategories = session.execute(stmt).scalars().all()
    found_ids = {subcategory.id for subcategory in subcategories}
    missing = set(unique_ids) - found_ids
    if missing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sous-catégorie introuvable ou inactive.")

    ordering = {identifier: index for index, identifier in enumerate(unique_ids)}
    subcategories.sort(key=lambda sub: ordering[sub.id])

    current = {subscription.subcategory_id: subscription for subscription in client.subscriptions}
    updated: list[models.ClientSubscription] = []
    for subcategory in subcategories:
        existing = current.get(subcategory.id)
        if existing is not None:
            updated.append(existing)
            continue
        updated.append(models.ClientSubscription(subcategory_id=subcategory.id, subcategory=subcategory))

    client.subscriptions = updated


def _resolve_department_ids(session: Session, department_ids: list[UUID]) -> list[UUID]:
    if department_ids:
        return department_ids
    departments = list_departments(session)
    return [department.id for department in departments]


def _apply_departments(session: Session, client: models.Client, department_ids: list[UUID]) -> None:
    unique_ids: list[UUID] = []
    seen: set[UUID] = set()
    for department_id in department_ids:
        if department_id in seen:
            continue
        seen.add(department_id)
        unique_ids.append(department_id)

    if not unique_ids:
        client.department_links = []
        return

    stmt = select(models.Department).where(models.Department.id.in_(unique_ids))
    departments = session.execute(stmt).scalars().all()
    found_ids = {department.id for department in departments}
    missing = set(unique_ids) - found_ids
    if missing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Département introuvable.")

    ordering = {identifier: index for index, identifier in enumerate(unique_ids)}
    departments.sort(key=lambda department: ordering[department.id])

    current = {link.department_id: link for link in client.department_links}
    updated: list[models.ClientDepartment] = []
    for department in departments:
        existing = current.get(department.id)
        if existing is not None:
            updated.append(existing)
            continue
        updated.append(models.ClientDepartment(department_id=department.id, department=department))

    client.department_links = updated


def list_clients_action(session: Session) -> list[ClientOut]:
    stmt = select(models.Client).options(*_client_eager_load()).order_by(models.Client.name)
    clients = session.execute(stmt).scalars().all()
    return [ClientOut.model_validate(client) for client in clients]


def get_client_action(client_id: UUID, session: Session) -> ClientOut:
    client = _get_client_or_404(session, client_id)
    return ClientOut.model_validate(client)


def create_client_action(payload: ClientCreate, session: Session) -> ClientOut:
    name = _normalize_name(payload.name)
    _validate_activation_window(payload.start_date, payload.end_date)

    client = models.Client(
        name=name,
        start_date=payload.start_date,
        end_date=payload.end_date,
        listing_statuses=list(payload.listing_statuses),
        include_admins_in_client_alerts=payload.include_admins_in_client_alerts,
    )
    session.add(client)
    _apply_recipients(client, payload.recipients)
    _apply_subscriptions(session, client, payload.subscription_ids)
    _apply_departments(session, client, _resolve_department_ids(session, payload.department_ids))

    try:
        session.flush()
    except IntegrityError as exc:  # noqa: BLE001 - surface as HTTP error
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Un client avec ce nom existe déjà.") from exc

    session.refresh(client)
    return ClientOut.model_validate(client)


def update_client_action(client_id: UUID, payload: ClientUpdate, session: Session) -> ClientOut:
    client = _get_client_or_404(session, client_id)

    start_date = payload.start_date or client.start_date
    end_date = payload.end_date if payload.end_date is not None else client.end_date
    _validate_activation_window(start_date, end_date)

    if payload.name is not None:
        client.name = _normalize_name(payload.name)
    client.start_date = start_date
    client.end_date = end_date
    if payload.listing_statuses is not None:
        client.listing_statuses = list(payload.listing_statuses)
    if payload.include_admins_in_client_alerts is not None:
        client.include_admins_in_client_alerts = payload.include_admins_in_client_alerts

    if payload.recipients is not None:
        _apply_recipients(client, payload.recipients)

    if payload.subscription_ids is not None:
        _apply_subscriptions(session, client, payload.subscription_ids)

    if payload.department_ids is not None:
        resolved_department_ids = _resolve_department_ids(session, payload.department_ids)
        _apply_departments(session, client, resolved_department_ids)

    try:
        session.flush()
    except IntegrityError as exc:  # noqa: BLE001 - surface as HTTP error
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Un client avec ce nom existe déjà.") from exc

    session.refresh(client)
    return ClientOut.model_validate(client)


def delete_client_action(client_id: UUID, session: Session) -> None:
    client = _get_client_or_404(session, client_id)
    session.delete(client)
    session.flush()
