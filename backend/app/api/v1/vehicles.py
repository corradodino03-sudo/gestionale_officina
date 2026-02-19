"""
Router FastAPI per l'entità Vehicle
Progetto: Garage Manager (Gestionale Officina)

Definisce gli endpoint API per la gestione dei veicoli.
"""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.schemas.vehicle import (
    VehicleCreate,
    VehicleList,
    VehicleRead,
    VehicleUpdate,
)
from app.services.vehicle_service import vehicle_service

# Logger per questo modulo
logger = logging.getLogger(__name__)

# Router con prefix e tag
router = APIRouter(
    prefix="/vehicles",
    tags=["Veicoli"],
)


# -------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------

# IMPORTANTE: l'ordine delle route è intenzionale.
# GET /client/{client_id} deve essere definito PRIMA di GET /{vehicle_id}
# per evitare che FastAPI interpreti "client" come un UUID vehicle_id.

@router.get(
    "/",
    name="veicoli_lista",
    summary="Lista veicoli",
    description="Recupera la lista paginata dei veicoli con eventuale filtro per cliente e ricerca.",
    response_model=VehicleList,
    status_code=status.HTTP_200_OK,
)
async def get_vehicles(
    client_id: Optional[uuid.UUID] = Query(None, description="UUID del cliente per filtro"),
    page: int = Query(1, ge=1, description="Numero pagina"),
    per_page: int = Query(10, ge=1, le=100, description="Elementi per pagina"),
    search: Optional[str] = Query(None, description="Termine di ricerca su targa, marca, modello, VIN"),
    db: AsyncSession = Depends(get_db),
) -> VehicleList:
    """
    Recupera la lista paginata dei veicoli.
    
    Args:
        client_id: UUID del cliente per filtrare i veicoli (opzionale)
        page: Numero pagina (default 1)
        per_page: Elementi per pagina (default 10, max 100)
        search: Termine di ricerca opzionale su targa, marca, modello, VIN
        db: Sessione database
        
    Returns:
        VehicleList: Lista paginata con metadati
    """
    vehicles, total = await vehicle_service.get_all(
        db=db,
        client_id=client_id,
        page=page,
        per_page=per_page,
        search=search,
    )

    return VehicleList(
        items=[VehicleRead.model_validate(v) for v in vehicles],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get(
    "/client/{client_id}",
    name="veicoli_cliente",
    summary="Veicoli di un cliente",
    description="Recupera tutti i veicoli associati a un cliente specifico.",
    response_model=list[VehicleRead],
    status_code=status.HTTP_200_OK,
)
async def get_vehicles_by_client(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[VehicleRead]:
    """
    Recupera tutti i veicoli di un cliente specifico.
    
    Args:
        client_id: UUID del cliente
        db: Sessione database
        
    Returns:
        Lista dei veicoli del cliente
        
    Raises:
        NotFoundError: Se il cliente non esiste
    """
    vehicles = await vehicle_service.get_by_client(
        db=db,
        client_id=client_id,
    )

    return [VehicleRead.model_validate(v) for v in vehicles]


@router.get(
    "/{vehicle_id}",
    name="veicolo_dettaglio",
    summary="Dettaglio veicolo",
    description="Recupera i dettagli di un veicolo specifico.",
    response_model=VehicleRead,
    status_code=status.HTTP_200_OK,
)
async def get_vehicle(
    vehicle_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> VehicleRead:
    """
    Recupera i dettagli di un veicolo.
    
    Args:
        vehicle_id: UUID del veicolo
        db: Sessione database
        
    Returns:
        VehicleRead: Dettagli del veicolo
        
    Raises:
        NotFoundError: Se il veicolo non esiste
    """
    vehicle = await vehicle_service.get_by_id(
        db=db,
        vehicle_id=vehicle_id,
    )
    return VehicleRead.model_validate(vehicle)


@router.post(
    "/",
    name="veicolo_crea",
    summary="Crea veicolo",
    description="Crea un nuovo veicolo associato a un cliente.",
    response_model=VehicleRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_vehicle(
    vehicle_data: VehicleCreate,
    db: AsyncSession = Depends(get_db),
) -> VehicleRead:
    """
    Crea un nuovo veicolo.
    
    Args:
        vehicle_data: Dati del veicolo da creare
        db: Sessione database
        
    Returns:
        VehicleRead: Dettagli del veicolo creato
        
    Raises:
        NotFoundError: Se il cliente non esiste
        409 Conflict: Se la targa o il VIN sono già in uso
    """
    vehicle = await vehicle_service.create(
        db=db,
        vehicle_data=vehicle_data,
    )
    await db.commit()
    return VehicleRead.model_validate(vehicle)


@router.put(
    "/{vehicle_id}",
    name="veicolo_aggiorna",
    summary="Aggiorna veicolo",
    description="Aggiorna i dati di un veicolo esistente.",
    response_model=VehicleRead,
    status_code=status.HTTP_200_OK,
)
async def update_vehicle(
    vehicle_id: uuid.UUID,
    vehicle_data: VehicleUpdate,
    db: AsyncSession = Depends(get_db),
) -> VehicleRead:
    """
    Aggiorna un veicolo esistente.
    
    Args:
        vehicle_id: UUID del veicolo da aggiornare
        vehicle_data: Dati parziali del veicolo
        db: Sessione database
        
    Returns:
        VehicleRead: Dettagli del veicolo aggiornato
        
    Raises:
        NotFoundError: Se il veicolo non esiste
        NotFoundError: Se il cliente non esiste
        409 Conflict: Se la targa o il VIN sono già in uso
    """
    vehicle = await vehicle_service.update(
        db=db,
        vehicle_id=vehicle_id,
        vehicle_data=vehicle_data,
    )
    await db.commit()
    return VehicleRead.model_validate(vehicle)


@router.delete(
    "/{vehicle_id}",
    name="veicolo_elimina",
    summary="Elimina veicolo",
    description="Elimina un veicolo esistente.",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_vehicle(
    vehicle_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Elimina un veicolo.
    
    Args:
        vehicle_id: UUID del veicolo da eliminare
        db: Sessione database
        
    Raises:
        NotFoundError: Se il veicolo non esiste
    """
    await vehicle_service.delete(
        db=db,
        vehicle_id=vehicle_id,
    )
    await db.commit()
