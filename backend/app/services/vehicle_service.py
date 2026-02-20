"""
Service Layer per l'entità Vehicle
Progetto: Garage Manager (Gestionale Officina)

Definisce la logica di business per la gestione dei veicoli.
"""

import logging
import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BusinessValidationError, DuplicateError, NotFoundError
from app.models import Client, Vehicle, WorkOrder
from app.schemas.vehicle import VehicleCreate, VehicleUpdate

# Logger per questo modulo
logger = logging.getLogger(__name__)


class VehicleService:
    """
    Service per la gestione delle operazioni CRUD sui veicoli.
    
    Fornisce metodi asincroni per interagire con il database
    in modo centralizzato, senza dipendenze da FastAPI.
    """

    def __init__(self) -> None:
        """
        Inizializza il service.
        """
        pass

    async def get_all(
        self,
        db: AsyncSession,
        client_id: Optional[uuid.UUID] = None,
        page: int = 1,
        per_page: int = 10,
        search: Optional[str] = None,
    ) -> tuple[list[Vehicle], int]:
        """
        Recupera la lista paginata dei veicoli.
        
        Args:
            db: Sessione database
            client_id: UUID del cliente per filtrare i veicoli (opzionale)
            page: Numero pagina (default 1)
            per_page: Elementi per pagina (default 10)
            search: Termine di ricerca opzionale (cerca su plate, brand, model, vin)
            
        Returns:
            Tuple di (lista veicoli, totale count)
        """
        # Build filter conditions
        filter_conditions = []
        
        # FIX 4: Filtra solo veicoli attivi di default
        filter_conditions.append(Vehicle.is_active == True)
        
        # Filtro per cliente
        if client_id is not None:
            filter_conditions.append(Vehicle.client_id == client_id)
        
        # Filtro per ricerca
        if search:
            search_term = f"%{search}%"
            search_condition = (
                Vehicle.plate.ilike(search_term)
                | Vehicle.brand.ilike(search_term)
                | Vehicle.model.ilike(search_term)
                | Vehicle.vin.ilike(search_term)
            )
            filter_conditions.append(search_condition)

        # Main query for data
        query = select(Vehicle)
        if filter_conditions:
            query = query.where(*filter_conditions)

        # Ordine per plate ASC
        query = query.order_by(Vehicle.plate.asc())

        # Calculate offset
        offset = (page - 1) * per_page

        # Execute query for data
        query = query.offset(offset).limit(per_page)
        result = await db.execute(query)
        vehicles = list(result.scalars().all())

        # Execute separate count query
        count_query = select(func.count()).select_from(Vehicle)
        if filter_conditions:
            count_query = count_query.where(*filter_conditions)
        
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        logger.debug(f"Recuperati {len(vehicles)} veicoli su {total} totali")

        return vehicles, total

    async def get_by_id(
        self,
        db: AsyncSession,
        vehicle_id: uuid.UUID,
    ) -> Vehicle:
        """
        Recupera un veicolo tramite ID.
        
        Usa selectinload per caricare il cliente insieme al veicolo.
        FIX 4: Filtra solo veicoli attivi.
        
        Args:
            db: Sessione database
            vehicle_id: UUID del veicolo
            
        Returns:
            Oggetto Vehicle
            
        Raises:
            NotFoundError: Se il veicolo non esiste
        """
        result = await db.execute(
            select(Vehicle)
            .options(selectinload(Vehicle.client))
            .where(Vehicle.id == vehicle_id)
            .where(Vehicle.is_active == True)
        )
        vehicle = result.scalar_one_or_none()

        if vehicle is None:
            logger.warning(f"Veicolo non trovato: {vehicle_id}")
            raise NotFoundError(f"Veicolo con ID {vehicle_id} non trovato")

        return vehicle

    async def create(
        self,
        db: AsyncSession,
        vehicle_data: VehicleCreate,
    ) -> Vehicle:
        """
        Crea un nuovo veicolo.
        
        Verifica che il cliente esista prima di creare il veicolo.
        
        Args:
            db: Sessione database
            vehicle_data: Dati del veicolo da creare
            
        Returns:
            Oggetto Vehicle appena creato
            
        Raises:
            NotFoundError: Se il cliente non esiste
            DuplicateError: Se la targa o il VIN sono già in uso
        """
        # Verifica che il cliente esista
        client_result = await db.execute(
            select(Client).where(Client.id == vehicle_data.client_id)
        )
        client = client_result.scalar_one_or_none()
        
        if client is None:
            logger.warning(f"Cliente non trovato per creazione veicolo: {vehicle_data.client_id}")
            raise NotFoundError("Cliente non trovato")

        # Converti Pydantic model in dict
        vehicle_dict = vehicle_data.model_dump()

        # Crea nuovo oggetto
        vehicle = Vehicle(**vehicle_dict)

        try:
            db.add(vehicle)
            await db.flush()
            await db.refresh(vehicle)

            logger.info(f"Creato nuovo veicolo: {vehicle.id} - {vehicle.plate}")
            return vehicle

        except IntegrityError as e:
            await db.rollback()
            error_msg = str(e.orig).lower()
            
            if "plate" in error_msg:
                logger.warning(f"Errore creazione veicolo - targa duplicata: {e.orig}")
                raise DuplicateError("Targa già registrata")
            
            if "vin" in error_msg:
                logger.warning(f"Errore creazione veicolo - VIN duplicato: {e.orig}")
                raise DuplicateError("Numero telaio già registrato")
            
            # Rilancia come errore generico
            logger.error(f"Errore creazione veicolo - errore DB: {e.orig}")
            raise

    async def update(
        self,
        db: AsyncSession,
        vehicle_id: uuid.UUID,
        vehicle_data: VehicleUpdate,
    ) -> Vehicle:
        """
        Aggiorna un veicolo esistente.
        
        Args:
            db: Sessione database
            vehicle_id: UUID del veicolo da aggiornare
            vehicle_data: Dati parziali del veicolo
            
        Returns:
            Oggetto Vehicle aggiornato
            
        Raises:
            NotFoundError: Se il veicolo non esiste
            NotFoundError: Se il nuovo cliente non esiste
            DuplicateError: Se la targa o il VIN sono già in uso
        """
        # Recupera il veicolo esistente
        vehicle = await self.get_by_id(db, vehicle_id)

        # Verifica cambio cliente se client_id è presente nei dati
        update_data = vehicle_data.model_dump(exclude_unset=True)
        if "client_id" in update_data and update_data["client_id"] is not None:
            new_client_id = update_data["client_id"]
            if vehicle.client_id != new_client_id:
                # Verifica che il nuovo cliente esista
                client_result = await db.execute(
                    select(Client).where(Client.id == new_client_id)
                )
                client = client_result.scalar_one_or_none()
                
                if client is None:
                    logger.warning(f"Cliente non trovato per aggiornamento veicolo: {new_client_id}")
                    raise NotFoundError("Cliente non trovato")

        # Applica gli aggiornamenti
        for field, value in update_data.items():
            setattr(vehicle, field, value)

        try:
            await db.flush()
            await db.refresh(vehicle)

            logger.info(f"Aggiornato veicolo: {vehicle.id}")
            return vehicle

        except IntegrityError as e:
            await db.rollback()
            error_msg = str(e.orig).lower()
            
            if "plate" in error_msg:
                logger.warning(f"Errore aggiornamento veicolo - targa duplicata: {e.orig}")
                raise DuplicateError("Targa già registrata")
            
            if "vin" in error_msg:
                logger.warning(f"Errore aggiornamento veicolo - VIN duplicato: {e.orig}")
                raise DuplicateError("Numero telaio già registrato")
            
            # Rilancia come errore generico
            logger.error(f"Errore aggiornamento veicolo - errore DB: {e.orig}")
            raise

    async def delete(
        self,
        db: AsyncSession,
        vehicle_id: uuid.UUID,
    ) -> None:
        """
        Elimina un veicolo (soft delete).
        
        FIX 3: Verifica che non esistano OdL attivi prima di procedere.
        Se il veicolo ha OdL non cancellati, solleva un errore.
        
        Args:
            db: Sessione database
            vehicle_id: UUID del veicolo da eliminare
            
        Raises:
            NotFoundError: Se il veicolo non esiste
            BusinessValidationError: Se esistono OdL attivi associati
        """
        # Recupera il veicolo esistente
        vehicle = await self.get_by_id(db, vehicle_id)

        # FIX 3: Verifica che non esistano OdL con stato diverso da 'cancelled'
        active_orders_query = (
            select(func.count(WorkOrder.id))
            .where(WorkOrder.vehicle_id == vehicle_id)
            .where(WorkOrder.status != 'cancelled')
        )
        result = await db.execute(active_orders_query)
        active_orders_count = result.scalar() or 0
        
        if active_orders_count > 0:
            logger.warning(
                "Tentativo di eliminare veicolo %s con %s ordini di lavoro attivi",
                vehicle_id,
                active_orders_count
            )
            raise BusinessValidationError(
                f"Impossibile eliminare il veicolo: ha {active_orders_count} ordini di lavoro attivi. "
                "Completare o annullare tutti gli ordini di lavoro prima di eliminare il veicolo."
            )

        # FIX 4: Converte da hard delete a soft delete
        vehicle.is_active = False
        await db.flush()

        logger.info(f"Disattivato veicolo: {vehicle_id}")

    async def get_by_client(
        self,
        db: AsyncSession,
        client_id: uuid.UUID,
    ) -> list[Vehicle]:
        """
        Recupera tutti i veicoli di un cliente specifico.
        
        Args:
            db: Sessione database
            client_id: UUID del cliente
            
        Returns:
            Lista di veicoli del cliente
            
        Raises:
            NotFoundError: Se il cliente non esiste
        """
        # Verifica che il cliente esista
        client_result = await db.execute(
            select(Client).where(Client.id == client_id)
        )
        client = client_result.scalar_one_or_none()
        
        if client is None:
            logger.warning(f"Cliente non trovato: {client_id}")
            raise NotFoundError("Cliente non trovato")

        # Recupera tutti i veicoli del cliente
        result = await db.execute(
            select(Vehicle)
            .where(Vehicle.client_id == client_id)
            .where(Vehicle.is_active == True)
            .order_by(Vehicle.plate.asc())
        )
        vehicles = list(result.scalars().all())

        logger.debug(f"Recuperati {len(vehicles)} veicoli per cliente {client_id}")

        return vehicles


# Istanza globale del service
vehicle_service = VehicleService()
