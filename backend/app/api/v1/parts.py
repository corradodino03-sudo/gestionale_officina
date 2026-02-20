"""
Router FastAPI per l'entità Part (Ricambi e Magazzino)
Progetto: Garage Manager (Gestionale Officina)

Definisce gli endpoint API per la gestione dei ricambi,
movimenti di magazzino e alert scorte.

NOTE: L'ordine delle route è intenzionale per evitare conflitti con FastAPI:
1. GET /low-stock (prima di /{part_id})
2. GET /code/{code} (prima di /{part_id})
3. GET / (lista paginata)
4. GET /{part_id} (dettaglio singolo)
5. POST / (creazione)
6. PUT /{part_id} (aggiornamento)
7. DELETE /{part_id} (eliminazione)
8. POST /{part_id}/movements (aggiungi movimento)
9. GET /{part_id}/movements (storico movimenti)
"""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.part import (
    LowStockAlert,
    LowStockAlertList,
    MovementType,
    PartCreate,
    PartList,
    PartRead,
    PartUpdate,
    PartUsageCreate,
    PartUsageRead,
    StockMovementCreate,
    StockMovementList,
    StockMovementRead,
)
from app.services.part_service import part_service

# Logger per questo modulo
logger = logging.getLogger(__name__)

# Router con prefix e tag
router = APIRouter(
    prefix="/parts",
    tags=["Ricambi e Magazzino"],
)


# ------------------------------------------------------------
# Endpoint: Alert Scorte Basse
# ------------------------------------------------------------

@router.get(
    "/low-stock",
    name="low_stock_alerts",
    summary="Alert scorte basse",
    description="Recupera la lista dei ricambi sotto il livello minimo di giacenza.",
    response_model=LowStockAlertList,
    status_code=status.HTTP_200_OK,
)
async def get_low_stock_alerts(
    db: AsyncSession = Depends(get_db),
) -> LowStockAlertList:
    """
    Recupera tutti i ricambi con giacenza sotto il livello minimo.
    """
    parts = await part_service.get_low_stock_alerts(db)
    
    return LowStockAlertList(
        items=[
            LowStockAlert(
                part_id=p.id,
                code=p.code,
                description=p.description,
                stock_quantity=p.stock_quantity,
                min_stock_level=p.min_stock_level,
            )
            for p in parts
        ],
        total=len(parts),
    )


# ------------------------------------------------------------
# Endpoint: Ricerca per Codice
# ------------------------------------------------------------

@router.get(
    "/code/{code}",
    name="part_by_code",
    summary="Ricerca ricambio per codice",
    description="Recupera un ricambio specifico tramite il suo codice identificativo.",
    response_model=PartRead,
    status_code=status.HTTP_200_OK,
)
async def get_part_by_code(
    code: str,
    db: AsyncSession = Depends(get_db),
) -> PartRead:
    """
    Recupera un ricambio per codice (case insensitive).
    """
    part = await part_service.get_by_code(db, code)
    return PartRead.model_validate(part)


# ------------------------------------------------------------
# Endpoint: Lista Ricambi (paginata)
# ------------------------------------------------------------

@router.get(
    "/",
    name="parts_list",
    summary="Lista ricambi",
    description="Recupera la lista paginata dei ricambi con eventuali filtri.",
    response_model=PartList,
    status_code=status.HTTP_200_OK,
)
async def get_parts(
    page: int = Query(1, ge=1, description="Numero pagina"),
    per_page: int = Query(10, ge=1, le=100, description="Elementi per pagina"),
    search: Optional[str] = Query(None, description="Termine di ricerca"),
    is_active: Optional[bool] = Query(None, description="Filtro per stato attivo"),
    below_minimum: bool = Query(False, description="Solo ricambi sotto il minimo"),
    category_id: Optional[uuid.UUID] = Query(None, description="Filtro per categoria"),
    db: AsyncSession = Depends(get_db),
) -> PartList:
    """
    Recupera la lista paginata dei ricambi.
    """
    parts, total = await part_service.get_all(
        db=db,
        page=page,
        per_page=per_page,
        search=search,
        is_active=is_active,
        below_minimum=below_minimum,
        category_id=category_id,
    )
    
    return PartList(
        items=[PartRead.model_validate(p) for p in parts],
        total=total,
        page=page,
        per_page=per_page,
    )


# ------------------------------------------------------------
# Endpoint: Dettaglio Ricambio
# ------------------------------------------------------------

@router.get(
    "/{part_id}",
    name="part_detail",
    summary="Dettaglio ricambio",
    description="Recupera i dettagli di un ricambio specifico.",
    response_model=PartRead,
    status_code=status.HTTP_200_OK,
)
async def get_part(
    part_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> PartRead:
    """
    Recupera i dettagli di un ricambio.
    """
    part = await part_service.get_by_id(db, part_id)
    return PartRead.model_validate(part)


# ------------------------------------------------------------
# Endpoint: Creazione Ricambio
# ------------------------------------------------------------

@router.post(
    "/",
    name="part_create",
    summary="Crea ricambio",
    description="Crea un nuovo ricambio nel catalogo.",
    response_model=PartRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_part(
    data: PartCreate,
    db: AsyncSession = Depends(get_db),
) -> PartRead:
    """
    Crea un nuovo ricambio.
    
    Nota: La giacenza iniziale è 0 e si gestisce solo tramite movimenti.
    """
    part = await part_service.create(db, data)
    await db.commit()
    return PartRead.model_validate(part)


# ------------------------------------------------------------
# Endpoint: Aggiornamento Ricambio
# ------------------------------------------------------------

@router.put(
    "/{part_id}",
    name="part_update",
    summary="Aggiorna ricambio",
    description="Aggiorna i dati di un ricambio esistente.",
    response_model=PartRead,
    status_code=status.HTTP_200_OK,
)
async def update_part(
    part_id: uuid.UUID,
    data: PartUpdate,
    db: AsyncSession = Depends(get_db),
) -> PartRead:
    """
    Aggiorna un ricambio.
    
    Nota: Non è possibile modificare la giacenza direttamente,
    usare gli endpoint dei movimenti.
    """
    part = await part_service.update(db, part_id, data)
    await db.commit()
    return PartRead.model_validate(part)


# ------------------------------------------------------------
# Endpoint: Eliminazione Ricambio
# ------------------------------------------------------------

@router.delete(
    "/{part_id}",
    name="part_delete",
    summary="Elimina ricambio",
    description="Elimina un ricambio dal catalogo.",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_part(
    part_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Elimina un ricambio.
    
    Se il ricambio è utilizzato in ordini di lavoro,
    restituisce un errore (usare la disattivazione).
    """
    await part_service.delete(db, part_id)
    await db.commit()


# ------------------------------------------------------------
# Endpoint: Aggiungi Movimento
# ------------------------------------------------------------

@router.post(
    "/{part_id}/movements",
    name="add_movement",
    summary="Aggiungi movimento",
    description="Registra un movimento di magazzino (carico, scarico, aggiustamento).",
    response_model=StockMovementRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_movement(
    part_id: uuid.UUID,
    data: StockMovementCreate,
    db: AsyncSession = Depends(get_db),
) -> StockMovementRead:
    """
    Aggiunge un movimento di magazzino.
    
    - IN: aumenta la giacenza
    - OUT: diminuisce la giacenza (verifica disponibilità)
    - ADJUSTMENT: imposta la giacenza al valore specificato
    """
    # Assicura che il part_id del path corrisponda a quello del body
    if data.part_id != part_id:
        data.part_id = part_id
    
    movement = await part_service.add_movement(db, data)
    await db.commit()
    
    return StockMovementRead(
        id=movement.id,
        part_id=movement.part_id,
        movement_type=MovementType(movement.movement_type),
        quantity=movement.quantity,
        reference=movement.reference,
        notes=movement.notes,
        created_at=movement.created_at,
    )


# ------------------------------------------------------------
# Endpoint: Storico Movimenti
# ------------------------------------------------------------

@router.get(
    "/{part_id}/movements",
    name="movements_list",
    summary="Storico movimenti",
    description="Recupera lo storico dei movimenti di magazzino per un ricambio.",
    response_model=StockMovementList,
    status_code=status.HTTP_200_OK,
)
async def get_movements(
    part_id: uuid.UUID,
    page: int = Query(1, ge=1, description="Numero pagina"),
    per_page: int = Query(10, ge=1, le=100, description="Elementi per pagina"),
    movement_type: Optional[MovementType] = Query(None, description="Filtro per tipo"),
    db: AsyncSession = Depends(get_db),
) -> StockMovementList:
    """
    Recupera lo storico movimenti per un ricambio.
    """
    movements, total = await part_service.get_movements(
        db=db,
        part_id=part_id,
        page=page,
        per_page=per_page,
        movement_type=movement_type,
    )
    
    return StockMovementList(
        items=[
            StockMovementRead(
                id=m.id,
                part_id=m.part_id,
                movement_type=MovementType(m.movement_type),
                quantity=m.quantity,
                reference=m.reference,
                notes=m.notes,
                created_at=m.created_at,
            )
            for m in movements
        ],
        total=total,
        page=page,
        per_page=per_page,
    )
