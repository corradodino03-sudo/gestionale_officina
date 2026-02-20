"""
Router FastAPI per Dichiarazioni di Intenzione
Progetto: Garage Manager (Gestionale Officina)

Definisce gli endpoint API per la gestione delle dichiarazioni di intento.
"""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.exceptions import NotFoundError, BusinessValidationError
from app.models import Client
from app.schemas.intent_declaration import (
    IntentDeclarationCreate,
    IntentDeclarationList,
    IntentDeclarationRead,
    IntentDeclarationUpdate,
)

# Logger per questo modulo
logger = logging.getLogger(__name__)

# Router con prefix e tag
router = APIRouter(
    prefix="/intent-declarations",
    tags=["Dichiarazioni Intenzione"],
)


# -------------------------------------------------------------------
# Dependency Injection
# -------------------------------------------------------------------

def get_db_session() -> AsyncSession:
    """
    Dependency per ottenere la sessione database.
    
    In FastAPI, questo sarà iniettato automaticamente.
    """
    return Depends(get_db)


# -------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------

async def get_client_or_404(db: AsyncSession, client_id: uuid.UUID) -> Client:
    """
    Recupera il cliente o solleva NotFoundError.
    
    Args:
        db: Sessione database
        client_id: UUID del cliente
        
    Returns:
        Client: Il cliente trovato
        
    Raises:
        NotFoundError: Se il cliente non esiste
    """
    from sqlalchemy import select
    
    stmt = select(Client).where(Client.id == client_id)
    result = await db.execute(stmt)
    client = result.scalar_one_or_none()
    
    if not client:
        raise NotFoundError(f"Cliente {client_id} non trovato")
    
    return client


# -------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------

@router.get(
    "/",
    name="intent_declarations_lista",
    summary="Lista dichiarazioni di intento",
    description="Recupera la lista paginata delle dichiarazioni di intento.",
    response_model=IntentDeclarationList,
    status_code=status.HTTP_200_OK,
)
async def get_intent_declarations(
    client_id: Optional[uuid.UUID] = Query(None, description="Filtra per cliente"),
    page: int = Query(1, ge=1, description="Numero pagina"),
    per_page: int = Query(10, ge=1, le=100, description="Elementi per pagina"),
    db: AsyncSession = Depends(get_db),
) -> IntentDeclarationList:
    """
    Recupera la lista paginata delle dichiarazioni di intento.
    
    Args:
        client_id: Filtro opzionale per cliente
        page: Numero pagina (default 1)
        per_page: Elementi per pagina (default 10, max 100)
        db: Sessione database
        
    Returns:
        IntentDeclarationList: Lista paginata con metadati
    """
    from sqlalchemy import select, func, or_
    from app.models.intent_declaration import IntentDeclaration
    
    # Build base query with eager loading
    stmt = select(IntentDeclaration).options(
        selectinload(IntentDeclaration.client),
    )
    
    # Apply client filter
    conditions = []
    if client_id:
        conditions.append(IntentDeclaration.client_id == client_id)
    
    if conditions:
        stmt = stmt.where(and_(*conditions))
    
    # Get total count
    count_stmt = select(func.count(IntentDeclaration.id))
    if conditions:
        count_stmt = count_stmt.where(and_(*conditions))
    
    count_result = await db.execute(count_stmt)
    total = count_result.scalar()
    
    # Apply pagination and ordering
    stmt = stmt.order_by(IntentDeclaration.declaration_date.desc())
    offset = (page - 1) * per_page
    stmt = stmt.offset(offset).limit(per_page)
    
    result = await db.execute(stmt)
    declarations = result.scalars().all()
    
    # Calculate total pages
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1
    
    return IntentDeclarationList(
        items=list(declarations),
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


@router.get(
    "/{declaration_id}",
    name="intent_declaration_dettaglio",
    summary="Dettaglio dichiarazione di intento",
    description="Recupera i dettagli di una dichiarazione di intento specifica.",
    response_model=IntentDeclarationRead,
    status_code=status.HTTP_200_OK,
)
async def get_intent_declaration(
    declaration_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> IntentDeclarationRead:
    """
    Recupera i dettagli di una dichiarazione di intento.
    
    Args:
        declaration_id: UUID della dichiarazione
        db: Sessione database
        
    Returns:
        IntentDeclarationRead: Dettagli della dichiarazione
        
    Raises:
        NotFoundError: Se la dichiarazione non esiste
    """
    from sqlalchemy import select
    
    stmt = (
        select(IntentDeclaration)
        .where(IntentDeclaration.id == declaration_id)
        .options(
            selectinload(IntentDeclaration.client),
        )
    )
    result = await db.execute(stmt)
    declaration = result.scalar_one_or_none()
    
    if not declaration:
        raise NotFoundError(f"Dichiarazione di intento {declaration_id} non trovata")
    
    return declaration


@router.post(
    "/",
    name="intent_declaration_crea",
    summary="Crea dichiarazione di intento",
    description="Crea una nuova dichiarazione di intento per un cliente.",
    response_model=IntentDeclarationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_intent_declaration(
    declaration_data: IntentDeclarationCreate,
    db: AsyncSession = Depends(get_db),
) -> IntentDeclarationRead:
    """
    Crea una nuova dichiarazione di intento.
    
    Args:
        declaration_data: Dati della dichiarazione
        db: Sessione database
        
    Returns:
        IntentDeclarationRead: Dettagli della dichiarazione creata
        
    Raises:
        NotFoundError: Se il cliente non esiste
        BusinessValidationError: Se i dati non sono validi
    """
    from sqlalchemy import select
    from app.models.intent_declaration import IntentDeclaration
    
    # Verify client exists
    client = await get_client_or_404(db, declaration_data.client_id)
    
    # Create the declaration
    declaration = IntentDeclaration(
        client_id=declaration_data.client_id,
        protocol_number=declaration_data.protocol_number,
        declaration_date=declaration_data.declaration_date,
        amount_limit=declaration_data.amount_limit,
        expiry_date=declaration_data.expiry_date,
        is_active=declaration_data.is_active,
        notes=declaration_data.notes,
    )
    
    db.add(declaration)
    await db.commit()
    await db.refresh(declaration)
    
    # Reload with client
    stmt = (
        select(IntentDeclaration)
        .where(IntentDeclaration.id == declaration.id)
        .options(
            selectinload(IntentDeclaration.client),
        )
    )
    result = await db.execute(stmt)
    declaration = result.scalar_one()
    
    return declaration


@router.put(
    "/{declaration_id}",
    name="intent_declaration_aggiorna",
    summary="Aggiorna dichiarazione di intento",
    description="Aggiorna i dati di una dichiarazione di intento esistente.",
    response_model=IntentDeclarationRead,
    status_code=status.HTTP_200_OK,
)
async def update_intent_declaration(
    declaration_id: uuid.UUID,
    declaration_data: IntentDeclarationUpdate,
    db: AsyncSession = Depends(get_db),
) -> IntentDeclarationRead:
    """
    Aggiorna una dichiarazione di intento esistente.
    
    Args:
        declaration_id: UUID della dichiarazione da aggiornare
        declaration_data: Dati parziali della dichiarazione
        db: Sessione database
        
    Returns:
        IntentDeclarationRead: Dettagli della dichiarazione aggiornata
        
    Raises:
        NotFoundError: Se la dichiarazione non esiste
        BusinessValidationError: Se used_amount supera amount_limit
    """
    from sqlalchemy import select
    from app.models.intent_declaration import IntentDeclaration
    
    # Get existing declaration
    stmt = (
        select(IntentDeclaration)
        .where(IntentDeclaration.id == declaration_id)
        .options(
            selectinload(IntentDeclaration.client),
        )
    )
    result = await db.execute(stmt)
    declaration = result.scalar_one_or_none()
    
    if not declaration:
        raise NotFoundError(f"Dichiarazione di intento {declaration_id} non trovata")
    
    # Update fields if provided
    if declaration_data.protocol_number is not None:
        declaration.protocol_number = declaration_data.protocol_number
    
    if declaration_data.declaration_date is not None:
        declaration.declaration_date = declaration_data.declaration_date
    
    if declaration_data.amount_limit is not None:
        declaration.amount_limit = declaration_data.amount_limit
    
    if declaration_data.used_amount is not None:
        # Validate that used_amount doesn't exceed amount_limit
        if declaration_data.used_amount > declaration.amount_limit:
            raise BusinessValidationError(
                f"L'importo utilizzato ({declaration_data.used_amount}) "
                f"non può superare il plafond ({declaration.amount_limit})"
            )
        declaration.used_amount = declaration_data.used_amount
    
    if declaration_data.expiry_date is not None:
        declaration.expiry_date = declaration_data.expiry_date
    
    if declaration_data.is_active is not None:
        declaration.is_active = declaration_data.is_active
    
    if declaration_data.notes is not None:
        declaration.notes = declaration_data.notes
    
    await db.commit()
    await db.refresh(declaration)
    
    return declaration


@router.delete(
    "/{declaration_id}",
    name="intent_declaration_elimina",
    summary="Elimina dichiarazione di intento",
    description="Elimina una dichiarazione di intento (eliminazione fisica).",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_intent_declaration(
    declaration_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Elimina una dichiarazione di intento.
    
    Args:
        declaration_id: UUID della dichiarazione da eliminare
        db: Sessione database
        
    Raises:
        NotFoundError: Se la dichiarazione non esiste
    """
    from sqlalchemy import select, delete
    from app.models.intent_declaration import IntentDeclaration
    
    # Get existing declaration
    stmt = select(IntentDeclaration).where(IntentDeclaration.id == declaration_id)
    result = await db.execute(stmt)
    declaration = result.scalar_one_or_none()
    
    if not declaration:
        raise NotFoundError(f"Dichiarazione di intento {declaration_id} non trovata")
    
    # Delete
    await db.delete(declaration)
    await db.commit()


@router.get(
    "/client/{client_id}",
    name="intent_declarations_by_client",
    summary="Dichiarazioni di intento per cliente",
    description="Recupera tutte le dichiarazioni di intento per un cliente specifico.",
    response_model=IntentDeclarationList,
    status_code=status.HTTP_200_OK,
)
async def get_intent_declarations_by_client(
    client_id: uuid.UUID,
    active_only: bool = Query(True, description="Solo dichiarazioni attive"),
    db: AsyncSession = Depends(get_db),
) -> IntentDeclarationList:
    """
    Recupera tutte le dichiarazioni di intento per un cliente.
    
    Args:
        client_id: UUID del cliente
        active_only: Se True, restituisci solo dichiarazioni attive
        db: Sessione database
        
    Returns:
        IntentDeclarationList: Lista delle dichiarazioni
        
    Raises:
        NotFoundError: Se il cliente non esiste
    """
    from sqlalchemy import select, func
    from app.models.intent_declaration import IntentDeclaration
    
    # Verify client exists
    await get_client_or_404(db, client_id)
    
    # Build query
    stmt = select(IntentDeclaration).options(
        selectinload(IntentDeclaration.client),
    ).where(IntentDeclaration.client_id == client_id)
    
    if active_only:
        from datetime import date
        today = date.today()
        stmt = stmt.where(
            and_(
                IntentDeclaration.is_active == True,
                IntentDeclaration.expiry_date >= today,
            )
        )
    
    stmt = stmt.order_by(IntentDeclaration.declaration_date.desc())
    
    result = await db.execute(stmt)
    declarations = result.scalars().all()
    
    total = len(declarations)
    
    return IntentDeclarationList(
        items=list(declarations),
        total=total,
        page=1,
        per_page=total,
        total_pages=1,
    )
