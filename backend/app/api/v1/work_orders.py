"""
Router FastAPI per gli Ordini di Lavoro
Progetto: Garage Manager (Gestionale Officina)

Definisce gli endpoint API per la gestione degli ordini di lavoro,
incluse le operazioni CRUD e la gestione delle voci di lavoro.
"""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import BusinessValidationError, NotFoundError
from app.schemas.work_order import (
    WorkOrderCreate,
    WorkOrderItemCreate,
    WorkOrderItemRead,
    WorkOrderItemUpdate,
    WorkOrderList,
    WorkOrderRead,
    WorkOrderStatus,
    WorkOrderStatusUpdate,
    WorkOrderUpdate,
)
from app.services.work_order_service import WorkOrderService

# Logger per questo modulo
logger = logging.getLogger(__name__)

# Istanza del service
work_order_service = WorkOrderService()

# Router con prefix e tag
router = APIRouter(
    prefix="/work-orders",
    tags=["Ordini di Lavoro"],
)


# -------------------------------------------------------------------
# Endpoints per Ordini di Lavoro
# -------------------------------------------------------------------

@router.get(
    "/",
    name="ordini_lista",
    summary="Lista ordini di lavoro",
    description="Recupera la lista paginata degli ordini di lavoro con eventuali filtri.",
    response_model=WorkOrderList,
    status_code=status.HTTP_200_OK,
)
async def get_work_orders(
    page: int = Query(1, ge=1, description="Numero pagina"),
    per_page: int = Query(10, ge=1, le=100, description="Elementi per pagina"),
    status_filter: Optional[WorkOrderStatus] = Query(
        None,
        description="Filtro per stato dell'ordine",
    ),
    client_id: Optional[uuid.UUID] = Query(None, description="Filtro per cliente"),
    vehicle_id: Optional[uuid.UUID] = Query(None, description="Filtro per veicolo"),
    search: Optional[str] = Query(None, description="Termine di ricerca su descrizione e diagnosi"),
    db: AsyncSession = Depends(get_db),
) -> WorkOrderList:
    """
    Recupera la lista paginata degli ordini di lavoro.
    
    Args:
        page: Numero pagina (default 1)
        per_page: Elementi per pagina (default 10, max 100)
        status_filter: Filtro opzionale per stato
        client_id: Filtro opzionale per cliente
        vehicle_id: Filtro opzionale per veicolo
        search: Termine di ricerca su problem_description e diagnosis
        db: Sessione database
        
    Returns:
        WorkOrderList: Lista paginata con metadati
    """
    work_orders, total = await work_order_service.get_all(
        db=db,
        status_filter=status_filter,
        client_id=client_id,
        vehicle_id=vehicle_id,
        page=page,
        per_page=per_page,
        search=search,
    )

    return WorkOrderList(
        items=[WorkOrderRead.model_validate(wo) for wo in work_orders],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=0,  # calcolato automaticamente dal model_validator
    )


@router.get(
    "/{work_order_id}",
    name="ordine_dettaglio",
    summary="Dettaglio ordine di lavoro",
    description="Recupera i dettagli di un ordine di lavoro specifico.",
    response_model=WorkOrderRead,
    status_code=status.HTTP_200_OK,
)
async def get_work_order(
    work_order_id: uuid.UUID = Path(..., description="UUID dell'ordine di lavoro"),
    db: AsyncSession = Depends(get_db),
) -> WorkOrderRead:
    """
    Recupera i dettagli di un ordine di lavoro.
    
    Args:
        work_order_id: UUID dell'ordine di lavoro
        db: Sessione database
        
    Returns:
        WorkOrderRead: Dettagli dell'ordine con voci e totali
        
    Raises:
        NotFoundError: Se l'ordine non esiste
    """
    work_order = await work_order_service.get_by_id(db, work_order_id)
    return WorkOrderRead.model_validate(work_order)


@router.post(
    "/",
    name="ordine_crea",
    summary="Crea ordine di lavoro",
    description="Crea un nuovo ordine di lavoro. Opzionalmente include le voci di lavoro iniziali.",
    response_model=WorkOrderRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_work_order(
    data: WorkOrderCreate,
    db: AsyncSession = Depends(get_db),
) -> WorkOrderRead:
    """
    Crea un nuovo ordine di lavoro.
    
    Args:
        data: Dati per la creazione dell'ordine
        db: Sessione database
        
    Returns:
        WorkOrderRead: L'ordine creato
        
    Raises:
        NotFoundError: Se il cliente o il veicolo non esistono
        ValidationError: Se il veicolo non appartiene al cliente
    """
    work_order = await work_order_service.create(db, data)
    await db.commit()
    return WorkOrderRead.model_validate(work_order)


@router.put(
    "/{work_order_id}",
    name="ordine_aggiorna",
    summary="Aggiorna ordine di lavoro",
    description="Aggiorna i dati di un ordine di lavoro esistente. "
               "NOTA: per cambiare lo stato usare l'endpoint PATCH /status.",
    response_model=WorkOrderRead,
    status_code=status.HTTP_200_OK,
)
async def update_work_order(
    work_order_id: uuid.UUID = Path(..., description="UUID dell'ordine di lavoro"),
    data: WorkOrderUpdate = ...,
    db: AsyncSession = Depends(get_db),
) -> WorkOrderRead:
    """
    Aggiorna un ordine di lavoro.
    
    Args:
        work_order_id: UUID dell'ordine da aggiornare
        data: Dati per l'aggiornamento
        db: Sessione database
        
    Returns:
        WorkOrderRead: L'ordine aggiornato
        
    Raises:
        NotFoundError: Se l'ordine non esiste
    """
    work_order = await work_order_service.update(db, work_order_id, data)
    await db.commit()
    return WorkOrderRead.model_validate(work_order)


@router.delete(
    "/{work_order_id}",
    name="ordine_elimina",
    summary="Elimina ordine di lavoro",
    description="Elimina un ordine di lavoro. Solo ordini in stato 'draft' o 'cancelled' "
               "possono essere eliminati.",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_work_order(
    work_order_id: uuid.UUID = Path(..., description="UUID dell'ordine di lavoro"),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Elimina un ordine di lavoro.
    
    Args:
        work_order_id: UUID dell'ordine da eliminare
        db: Sessione database
        
    Raises:
        NotFoundError: Se l'ordine non esiste
        ValidationError: Se l'ordine non è in stato draft o cancelled
    """
    await work_order_service.delete(db, work_order_id)
    await db.commit()


@router.patch(
    "/{work_order_id}/status",
    name="ordine_cambia_stato",
    summary="Cambia stato ordine di lavoro",
    description="Cambia lo stato di un ordine di lavoro. Valida la transizione "
               "usando la macchina a stati definita.",
    response_model=WorkOrderRead,
    status_code=status.HTTP_200_OK,
)
async def change_work_order_status(
    work_order_id: uuid.UUID = Path(..., description="UUID dell'ordine di lavoro"),
    data: WorkOrderStatusUpdate = ...,
    db: AsyncSession = Depends(get_db),
) -> WorkOrderRead:
    """
    Cambia lo stato di un ordine di lavoro.
    
    Args:
        work_order_id: UUID dell'ordine
        data: Nuovo stato desiderato
        db: Sessione database
        
    Returns:
        WorkOrderRead: L'ordine con stato aggiornato
        
    Raises:
        NotFoundError: Se l'ordine non esiste
        ValidationError: Se la transizione non è valida
    """
    work_order = await work_order_service.change_status(db, work_order_id, data.status)
    await db.commit()
    return WorkOrderRead.model_validate(work_order)


# -------------------------------------------------------------------
# Endpoints per Voci di Lavoro (nested)
# -------------------------------------------------------------------

@router.post(
    "/{work_order_id}/items",
    name="voce_aggiungi",
    summary="Aggiungi voce di lavoro",
    description="Aggiunge una voce di lavoro (manodopera o intervento) a un ordine.",
    response_model=WorkOrderItemRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_work_order_item(
    work_order_id: uuid.UUID = Path(..., description="UUID dell'ordine di lavoro"),
    item_data: WorkOrderItemCreate = ...,
    db: AsyncSession = Depends(get_db),
) -> WorkOrderItemRead:
    """
    Aggiunge una voce di lavoro a un ordine.
    
    Args:
        work_order_id: UUID dell'ordine
        item_data: Dati della voce da aggiungere
        db: Sessione database
        
    Returns:
        WorkOrderItemRead: La voce creata
        
    Raises:
        NotFoundError: Se l'ordine non esiste
        ValidationError: Se l'ordine non è in stato draft o in_progress
    """
    item = await work_order_service.add_item(db, work_order_id, item_data)
    await db.commit()
    return WorkOrderItemRead.model_validate(item)


@router.put(
    "/{work_order_id}/items/{item_id}",
    name="voce_aggiorna",
    summary="Aggiorna voce di lavoro",
    description="Aggiorna una voce di lavoro esistente.",
    response_model=WorkOrderItemRead,
    status_code=status.HTTP_200_OK,
)
async def update_work_order_item(
    work_order_id: uuid.UUID = Path(..., description="UUID dell'ordine di lavoro"),
    item_id: uuid.UUID = Path(..., description="UUID della voce di lavoro"),
    item_data: WorkOrderItemUpdate = ...,
    db: AsyncSession = Depends(get_db),
) -> WorkOrderItemRead:
    """
    Aggiorna una voce di lavoro.
    
    Args:
        work_order_id: UUID dell'ordine
        item_id: UUID della voce da aggiornare
        item_data: Dati per l'aggiornamento
        db: Sessione database
        
    Returns:
        WorkOrderItemRead: La voce aggiornata
        
    Raises:
        NotFoundError: Se la voce non esiste
        ValidationError: Se l'ordine non permette modifiche
    """
    item = await work_order_service.update_item(db, work_order_id, item_id, item_data)
    await db.commit()
    return WorkOrderItemRead.model_validate(item)


@router.delete(
    "/{work_order_id}/items/{item_id}",
    name="voce_elimina",
    summary="Elimina voce di lavoro",
    description="Elimina una voce di lavoro da un ordine.",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_work_order_item(
    work_order_id: uuid.UUID = Path(..., description="UUID dell'ordine di lavoro"),
    item_id: uuid.UUID = Path(..., description="UUID della voce di lavoro"),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Elimina una voce di lavoro.
    
    Args:
        work_order_id: UUID dell'ordine
        item_id: UUID della voce da eliminare
        db: Sessione database
        
    Raises:
        NotFoundError: Se la voce non esiste
        ValidationError: Se l'ordine non permette la rimozione
    """
    await work_order_service.remove_item(db, work_order_id, item_id)
    await db.commit()
