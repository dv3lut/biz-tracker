"""Client management endpoints for the admin API."""
from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import get_db_session
from app.api.schemas import ClientCreate, ClientOut, ClientUpdate
from app.db import models

from .common import normalize_emails

router = APIRouter(tags=["admin"])


def _validate_activation_window(start_date: date, end_date: date | None) -> None:
    if end_date and end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La date de fin doit être postérieure ou égale à la date de début.",
        )


def _normalize_name(name: str) -> str:
    normalized = name.strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le nom du client est obligatoire.",
        )
    return normalized


def _get_client_or_404(session: Session, client_id: UUID) -> models.Client:
    stmt = (
        select(models.Client)
        .where(models.Client.id == client_id)
        .options(selectinload(models.Client.recipients))
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


@router.get("/clients", response_model=list[ClientOut], summary="Lister les clients configurés")
def list_clients(session: Session = Depends(get_db_session)) -> list[ClientOut]:
    stmt = select(models.Client).options(selectinload(models.Client.recipients)).order_by(models.Client.name)
    clients = session.execute(stmt).scalars().all()
    return [ClientOut.model_validate(client) for client in clients]


@router.get("/clients/{client_id}", response_model=ClientOut, summary="Consulter un client")
def get_client(client_id: UUID, session: Session = Depends(get_db_session)) -> ClientOut:
    client = _get_client_or_404(session, client_id)
    return ClientOut.model_validate(client)


@router.post(
    "/clients",
    response_model=ClientOut,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un nouveau client",
)
def create_client(payload: ClientCreate, session: Session = Depends(get_db_session)) -> ClientOut:
    name = _normalize_name(payload.name)
    _validate_activation_window(payload.start_date, payload.end_date)

    client = models.Client(name=name, start_date=payload.start_date, end_date=payload.end_date)
    session.add(client)
    _apply_recipients(client, payload.recipients)

    try:
        session.flush()
    except IntegrityError as exc:  # noqa: BLE001 - surface as HTTP error
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Un client avec ce nom existe déjà.") from exc

    session.refresh(client)
    return ClientOut.model_validate(client)


@router.put("/clients/{client_id}", response_model=ClientOut, summary="Mettre à jour un client")
def update_client(
    client_id: UUID,
    payload: ClientUpdate,
    session: Session = Depends(get_db_session),
) -> ClientOut:
    client = _get_client_or_404(session, client_id)

    start_date = payload.start_date or client.start_date
    end_date = payload.end_date if payload.end_date is not None else client.end_date
    _validate_activation_window(start_date, end_date)

    if payload.name is not None:
        client.name = _normalize_name(payload.name)
    client.start_date = start_date
    client.end_date = end_date

    if payload.recipients is not None:
        _apply_recipients(client, payload.recipients)

    try:
        session.flush()
    except IntegrityError as exc:  # noqa: BLE001 - surface as HTTP error
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Un client avec ce nom existe déjà.") from exc

    session.refresh(client)
    return ClientOut.model_validate(client)


@router.delete("/clients/{client_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Supprimer un client")
def delete_client(client_id: UUID, session: Session = Depends(get_db_session)) -> None:
    client = _get_client_or_404(session, client_id)
    session.delete(client)
    session.flush()
