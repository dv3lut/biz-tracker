"""Client management endpoints for the admin API."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.api.schemas import ClientCreate, ClientOut, ClientUpdate

from .client_handlers import (
    create_client_action,
    delete_client_action,
    get_client_action,
    list_clients_action,
    update_client_action,
)

router = APIRouter(tags=["admin"])


@router.get("/clients", response_model=list[ClientOut], summary="Lister les clients configurés")
def list_clients(session: Session = Depends(get_db_session)) -> list[ClientOut]:
    return list_clients_action(session)


@router.get("/clients/{client_id}", response_model=ClientOut, summary="Consulter un client")
def get_client(client_id: UUID, session: Session = Depends(get_db_session)) -> ClientOut:
    return get_client_action(client_id=client_id, session=session)


@router.post(
    "/clients",
    response_model=ClientOut,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un nouveau client",
)
def create_client(payload: ClientCreate, session: Session = Depends(get_db_session)) -> ClientOut:
    return create_client_action(payload=payload, session=session)


@router.put("/clients/{client_id}", response_model=ClientOut, summary="Mettre à jour un client")
def update_client(
    client_id: UUID,
    payload: ClientUpdate,
    session: Session = Depends(get_db_session),
) -> ClientOut:
    return update_client_action(client_id=client_id, payload=payload, session=session)


@router.delete("/clients/{client_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Supprimer un client")
def delete_client(client_id: UUID, session: Session = Depends(get_db_session)) -> None:
    delete_client_action(client_id=client_id, session=session)