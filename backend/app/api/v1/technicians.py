import logging
import uuid
from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.technician import TechnicianCreate, TechnicianRead, TechnicianUpdate
from app.services.technician_service import technician_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/technicians",
    tags=["Tecnici"],
)


@router.get("/", response_model=List[TechnicianRead])
async def get_all_technicians(db: AsyncSession = Depends(get_db)):
    """Recupera la lista dei tecnici attivi."""
    technicians = await technician_service.get_all(db)
    return technicians


@router.get("/{id}", response_model=TechnicianRead)
async def get_technician(id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Recupera il dettaglio di un tecnico."""
    technician = await technician_service.get_by_id(db, id)
    return technician


@router.post("/", response_model=TechnicianRead, status_code=status.HTTP_201_CREATED)
async def create_technician(data: TechnicianCreate, db: AsyncSession = Depends(get_db)):
    """Crea un nuovo tecnico."""
    technician = await technician_service.create(db, data)
    await db.commit()
    return technician


@router.put("/{id}", response_model=TechnicianRead)
async def update_technician(id: uuid.UUID, data: TechnicianUpdate, db: AsyncSession = Depends(get_db)):
    """Aggiorna i dati di un tecnico."""
    technician = await technician_service.update(db, id, data)
    await db.commit()
    return technician


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_technician(id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Soft delete di un tecnico. Blocca se ha OdL aperti assegnati."""
    await technician_service.delete(db, id)
    await db.commit()
