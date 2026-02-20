"""
Service Layer per l'entità Technician
Progetto: Garage Manager (Gestionale Officina)

Definisce la logica di business per la gestione dei tecnici.
"""

import logging
import uuid
from typing import List

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessValidationError, NotFoundError
from app.models.technician import Technician
from app.models.work_order import WorkOrder
from app.schemas.technician import TechnicianCreate, TechnicianUpdate

logger = logging.getLogger(__name__)


class TechnicianService:
    """
    Service per la gestione delle operazioni CRUD sui tecnici.
    """

    def __init__(self) -> None:
        pass

    async def get_all(self, db: AsyncSession) -> List[Technician]:
        """Recupera la lista dei tecnici attivi."""
        query = select(Technician).where(Technician.is_active == True).order_by(Technician.name)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_by_id(self, db: AsyncSession, id: uuid.UUID) -> Technician:
        """Recupera il dettaglio di un tecnico."""
        query = select(Technician).where(Technician.id == id, Technician.is_active == True)
        result = await db.execute(query)
        technician = result.scalar_one_or_none()
        
        if not technician:
            raise NotFoundError(f"Tecnico {id} non trovato")
            
        return technician

    async def create(self, db: AsyncSession, data: TechnicianCreate) -> Technician:
        """Crea un nuovo tecnico."""
        technician = Technician(**data.model_dump())
        db.add(technician)
        await db.flush()
        await db.refresh(technician)
        return technician

    async def update(self, db: AsyncSession, id: uuid.UUID, data: TechnicianUpdate) -> Technician:
        """Aggiorna i dati di un tecnico."""
        technician = await self.get_by_id(db, id)
            
        update_data = data.model_dump(exclude_unset=True)
        for k, v in update_data.items():
            setattr(technician, k, v)
            
        await db.flush()
        await db.refresh(technician)
        return technician

    async def delete(self, db: AsyncSession, id: uuid.UUID) -> None:
        """Soft delete di un tecnico. Blocca se ha OdL aperti assegnati."""
        technician = await self.get_by_id(db, id)
            
        # Verifica OdL aperti
        wo_query = select(func.count(WorkOrder.id)).where(
            WorkOrder.assigned_technician_id == id,
            WorkOrder.status.not_in(["completed", "invoiced", "cancelled"])
        )
        wo_count = await db.execute(wo_query)
        
        if (wo_count.scalar() or 0) > 0:
            raise BusinessValidationError("Impossibile eliminare tecnico: ci sono ordini in corso assegnati a lui")
            
        technician.is_active = False
        await db.flush()


technician_service = TechnicianService()
