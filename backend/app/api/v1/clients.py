"""
Router FastAPI per l'entità Client
Progetto: Garage Manager (Gestionale Officina)

Definisce gli endpoint API per la gestione dei clienti.
"""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import DuplicateError, NotFoundError
from app.schemas.client import (
    ClientCreate,
    ClientList,
    ClientRead,
    ClientUpdate,
)
from app.services.client_service import client_service

# Logger per questo modulo
logger = logging.getLogger(__name__)

# Router con prefix e tag
router = APIRouter(
    prefix="/clients",
    tags=["Clienti"],
)


# -------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------
@router.get(
    "/",
    name="clienti_lista",
    summary="Lista clienti",
    description="Recupera la lista paginata dei clienti con eventuale filtro di ricerca.",
    response_model=ClientList,
    status_code=status.HTTP_200_OK,
)
async def get_clients(
    page: int = Query(1, ge=1, description="Numero pagina"),
    per_page: int = Query(10, ge=1, le=100, description="Elementi per pagina"),
    search: Optional[str] = Query(None, description="Termine di ricerca"),
    db: AsyncSession = Depends(get_db),
) -> ClientList:
    """
    Recupera la lista paginata dei clienti.
    
    Args:
        page: Numero pagina (default 1)
        per_page: Elementi per pagina (default 10, max 100)
        search: Termine di ricerca opzionale su nome, cognome, tax_id, telefono, email
        db: Sessione database
        
    Returns:
        ClientList: Lista paginata con metadati
    """
    clients, total = await client_service.get_all(
        db=db,
        page=page,
        per_page=per_page,
        search=search,
    )

    return ClientList(
        items=[ClientRead.model_validate(c) for c in clients],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get(
    "/{client_id}",
    name="cliente_dettaglio",
    summary="Dettaglio cliente",
    description="Recupera i dettagli di un cliente specifico.",
    response_model=ClientRead,
    status_code=status.HTTP_200_OK,
)
async def get_client(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ClientRead:
    """
    Recupera i dettagli di un cliente.
    
    Args:
        client_id: UUID del cliente
        db: Sessione database
        
    Returns:
        ClientRead: Dettagli del cliente
        
    Raises:
        NotFoundError: Se il cliente non esiste
    """
    client = await client_service.get_by_id(db=db, client_id=client_id)
    return ClientRead.model_validate(client)


@router.post(
    "/",
    name="cliente_crea",
    summary="Crea cliente",
    description="Crea un nuovo cliente.",
    response_model=ClientRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_client(
    client_data: ClientCreate,
    db: AsyncSession = Depends(get_db),
) -> ClientRead:
    """
    Crea un nuovo cliente.
    
    Args:
        client_data: Dati del cliente da creare
        db: Sessione database
        
    Returns:
        ClientRead: Dettagli del cliente creato
        
    Raises:
        DuplicateError: Se il tax_id è già in uso
    """
    client = await client_service.create(db=db, client_data=client_data)
    return ClientRead.model_validate(client)


@router.put(
    "/{client_id}",
    name="cliente_aggiorna",
    summary="Aggiorna cliente",
    description="Aggiorna i dati di un cliente esistente.",
    response_model=ClientRead,
    status_code=status.HTTP_200_OK,
)
async def update_client(
    client_id: uuid.UUID,
    client_data: ClientUpdate,
    db: AsyncSession = Depends(get_db),
) -> ClientRead:
    """
    Aggiorna un cliente esistente.
    
    Args:
        client_id: UUID del cliente da aggiornare
        client_data: Dati parziali del cliente
        db: Sessione database
        
    Returns:
        ClientRead: Dettagli del cliente aggiornato
        
    Raises:
        NotFoundError: Se il cliente non esiste
        DuplicateError: Se il tax_id è già in uso
    """
    client = await client_service.update(
        db=db,
        client_id=client_id,
        client_data=client_data,
    )
    return ClientRead.model_validate(client)


@router.delete(
    "/{client_id}",
    name="cliente_elimina",
    summary="Elimina cliente",
    description="Elimina un cliente esistente.",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_client(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Elimina un cliente.
    
    Args:
        client_id: UUID del cliente da eliminare
        db: Sessione database
        
    Raises:
        NotFoundError: Se il cliente non esiste
    """
    await client_service.delete(db=db, client_id=client_id)
    return None
