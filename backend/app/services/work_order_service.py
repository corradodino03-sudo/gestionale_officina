"""
Service Layer per gli Ordini di Lavoro
Progetto: Garage Manager (Gestionale Officina)

Definisce la logica di business per la gestione degli ordini di lavoro,
incluse le transizioni di stato e la gestione delle voci di lavoro.
"""

import datetime
import logging
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BusinessValidationError, NotFoundError
from app.models import Client, Vehicle, WorkOrder, WorkOrderItem
from app.models.part import Part, PartUsage, StockMovement
from app.schemas.work_order import (
    VALID_TRANSITIONS,
    WorkOrderCreate,
    WorkOrderItemCreate,
    WorkOrderItemUpdate,
    WorkOrderStatus,
    WorkOrderUpdate,
)

# Logger per questo modulo
logger = logging.getLogger(__name__)


class WorkOrderService:
    """
    Service per la gestione delle operazioni CRUD sugli ordini di lavoro.
    
    Fornisce metodi asincroni per interagire con il database
    in modo centralizzato, senza dipendenze da FastAPI.
    Include la logica di business per le transizioni di stato.
    """

    def __init__(self) -> None:
        """
        Inizializza il service.
        """
        pass

    def _check_editable_status(self, work_order: WorkOrder) -> None:
        """
        Verifica che l'ordine di lavoro sia in uno stato che permette modifiche.
        
        Solo gli ordini in stato DRAFT o IN_PROGRESS possono essere modificati.
        
        Args:
            work_order: L'ordine di lavoro da verificare
            
        Raises:
            ValidationError: Se l'ordine non è in stato modificabile
        """
        current_status = WorkOrderStatus(work_order.status)
        if current_status not in [WorkOrderStatus.DRAFT, WorkOrderStatus.IN_PROGRESS]:
            raise BusinessValidationError(
                f"Non è possibile modificare un ordine in stato '{work_order.status}'"
            )

    async def get_all(
        self,
        db: AsyncSession,
        status_filter: Optional[WorkOrderStatus] = None,
        client_id: Optional[uuid.UUID] = None,
        vehicle_id: Optional[uuid.UUID] = None,
        page: int = 1,
        per_page: int = 10,
        search: Optional[str] = None,
    ) -> tuple[list[WorkOrder], int]:
        """
        Recupera la lista paginata degli ordini di lavoro.
        
        Args:
            db: Sessione database
            status_filter: Filtro opzionale per stato
            client_id: Filtro opzionale per cliente
            vehicle_id: Filtro opzionale per veicolo
            page: Numero pagina (default 1)
            per_page: Elementi per pagina (default 10)
            search: Termine di ricerca opzionale (su problem_description e diagnosis)
            
        Returns:
            Tuple di (lista ordini, totale count)
        """
        # Build filter conditions
        conditions = []
        
        if status_filter:
            conditions.append(WorkOrder.status == status_filter)
        
        if client_id:
            conditions.append(WorkOrder.client_id == client_id)
        
        if vehicle_id:
            conditions.append(WorkOrder.vehicle_id == vehicle_id)
        
        if search:
            search_term = f"%{search}%"
            conditions.append(
                WorkOrder.problem_description.ilike(search_term)
                | WorkOrder.diagnosis.ilike(search_term)
            )

        # Main query for data
        query = select(WorkOrder)
        if conditions:
            query = query.where(and_(*conditions))

        # Order by created_at DESC (più recenti prima)
        query = query.order_by(WorkOrder.created_at.desc())

        # Calculate offset
        offset = (page - 1) * per_page

        # Execute query for data with eager loading
        query = query.options(
            selectinload(WorkOrder.client),
            selectinload(WorkOrder.vehicle),
            selectinload(WorkOrder.items),
            selectinload(WorkOrder.part_usages),
            selectinload(WorkOrder.invoice),
        ).offset(offset).limit(per_page)
        
        result = await db.execute(query)
        work_orders = list(result.scalars().all())

        # Execute separate count query
        count_query = select(func.count()).select_from(WorkOrder)
        if conditions:
            count_query = count_query.where(and_(*conditions))
        
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        logger.debug("Recuperati %d ordini di lavoro su %d totali", len(work_orders), total)

        return work_orders, total

    async def get_by_id(
        self,
        db: AsyncSession,
        work_order_id: uuid.UUID,
    ) -> WorkOrder:
        """
        Recupera un ordine di lavoro tramite ID.
        
        Args:
            db: Sessione database
            work_order_id: UUID dell'ordine di lavoro
            
        Returns:
            WorkOrder: L'ordine di lavoro trovato
            
        Raises:
            NotFoundError: Se l'ordine di lavoro non esiste
        """
        logger.debug("get_by_id: Retrieving work order %s", work_order_id)
        query = (
            select(WorkOrder)
            .where(WorkOrder.id == work_order_id)
            .options(
                selectinload(WorkOrder.client),
                selectinload(WorkOrder.vehicle),
                selectinload(WorkOrder.items),
                selectinload(WorkOrder.part_usages),
                selectinload(WorkOrder.invoice),
            )
        )
        
        result = await db.execute(query)
        work_order = result.scalar_one_or_none()

        if not work_order:
            logger.warning("Ordine di lavoro non trovato: %s", work_order_id)
            raise NotFoundError(f"Ordine di lavoro con ID {work_order_id} non trovato")

        # Debug: Log relationship statuses
        logger.debug(
            "get_by_id: client=%s, vehicle=%s, items=%d, "
            "part_usages=%d, invoice=%s",
            "loaded" if work_order.client else "None",
            "loaded" if work_order.vehicle else "None",
            len(work_order.items) if work_order.items else 0,
            len(getattr(work_order, 'part_usages', []) or []),
            "loaded" if work_order.invoice else "None"
        )
        
        logger.debug("Recuperato ordine di lavoro: %s", work_order_id)
        return work_order

    async def create(
        self,
        db: AsyncSession,
        data: WorkOrderCreate,
    ) -> WorkOrder:
        """
        Crea un nuovo ordine di lavoro.
        
        Args:
            db: Sessione database
            data: Dati per la creazione dell'ordine
            
        Returns:
            WorkOrder: L'ordine di lavoro creato
            
        Raises:
            NotFoundError: Se il cliente o il veicolo non esistono
            ValidationError: Se il veicolo non appartiene al cliente
        """
        # Verifica che il cliente esista
        client_result = await db.execute(
            select(Client).where(Client.id == data.client_id)
        )
        client = client_result.scalar_one_or_none()
        
        if not client:
            logger.warning("Cliente non trovato: %s", data.client_id)
            raise NotFoundError(f"Cliente con ID {data.client_id} non trovato")

        # Verifica che il veicolo esista
        vehicle_result = await db.execute(
            select(Vehicle).where(Vehicle.id == data.vehicle_id)
        )
        vehicle = vehicle_result.scalar_one_or_none()
        
        if not vehicle:
            logger.warning("Veicolo non trovato: %s", data.vehicle_id)
            raise NotFoundError(f"Veicolo con ID {data.vehicle_id} non trovato")

        # Verifica che il veicolo appartenga al cliente
        if vehicle.client_id != data.client_id:
            logger.warning(
                "Veicolo %s non appartiene al cliente %s",
                data.vehicle_id,
                data.client_id
            )
            raise BusinessValidationError("Il veicolo non appartiene al cliente selezionato")

        # Crea l'ordine di lavoro
        work_order = WorkOrder(
            client_id=data.client_id,
            vehicle_id=data.vehicle_id,
            problem_description=data.problem_description,
            diagnosis=data.diagnosis,
            km_in=data.km_in,
            km_out=data.km_out,
            estimated_delivery=data.estimated_delivery,
            internal_notes=data.internal_notes,
            status=WorkOrderStatus.DRAFT.value,  # Stato iniziale
        )

        db.add(work_order)
        await db.flush()  # Assicura che work_order.id sia disponibile
        
        # Crea le voci di lavoro se presenti
        if data.items:
            for item_data in data.items:
                item = WorkOrderItem(
                    work_order_id=work_order.id,
                    description=item_data.description,
                    quantity=item_data.quantity,
                    unit_price=item_data.unit_price,
                    item_type=item_data.item_type,
                )
                db.add(item)

        await db.flush()
        
        # Ricarica l'ordine con le relazioni caricate usando selectinload
        # (refresh non funziona bene con lazy="noload" per collections)
        query = (
            select(WorkOrder)
            .where(WorkOrder.id == work_order.id)
            .options(
                selectinload(WorkOrder.client),
                selectinload(WorkOrder.vehicle),
                selectinload(WorkOrder.items),
                selectinload(WorkOrder.part_usages),
                selectinload(WorkOrder.invoice),
            )
        )
        result = await db.execute(query)
        work_order = result.scalar_one()

        logger.info("Creato ordine di lavoro: %s", work_order.id)
        return work_order

    async def update(
        self,
        db: AsyncSession,
        work_order_id: uuid.UUID,
        data: WorkOrderUpdate,
    ) -> WorkOrder:
        """
        Aggiorna un ordine di lavoro esistente.
        
        NOTA: Questo metodo NON permette di cambiare lo status.
        Per cambiare lo status usare change_status().
        
        Args:
            db: Sessione database
            work_order_id: UUID dell'ordine da aggiornare
            data: Dati per l'aggiornamento
            
        Returns:
            WorkOrder: L'ordine di lavoro aggiornato
            
        Raises:
            NotFoundError: Se l'ordine non esiste
            ValidationError: Se l'ordine non è in stato modificabile
        """
        # Recupera l'ordine
        work_order = await self.get_by_id(db, work_order_id)

        # Verifica che lo stato permetta modifiche
        self._check_editable_status(work_order)

        # Aggiorna solo i campi forniti (escludi status)
        update_data = data.model_dump(exclude_unset=True)

        # Se cambia vehicle_id, verifica appartenenza al client PRIMA di applicare i campi
        if "vehicle_id" in update_data:
            new_vehicle_id = update_data["vehicle_id"]
            vehicle_result = await db.execute(
                select(Vehicle).where(Vehicle.id == new_vehicle_id)
            )
            vehicle = vehicle_result.scalar_one_or_none()
            
            if not vehicle:
                raise NotFoundError(f"Veicolo con ID {new_vehicle_id} non trovato")
            if vehicle.client_id != work_order.client_id:
                raise BusinessValidationError("Il veicolo non appartiene al cliente selezionato")

        # Solo dopo applicare tutti i campi
        for field, value in update_data.items():
            setattr(work_order, field, value)

        await db.flush()
        await db.refresh(work_order, ["client", "vehicle", "items"])

        logger.info("Aggiornato ordine di lavoro: %s", work_order_id)
        return work_order

    async def delete(
        self,
        db: AsyncSession,
        work_order_id: uuid.UUID,
    ) -> None:
        """
        Elimina un ordine di lavoro.
        
        Solo gli ordini in stato 'draft' o 'cancelled' possono essere eliminati.
        Se l'ordine ha PartUsage associati, il magazzino viene ripristinato.
        
        Args:
            db: Sessione database
            work_order_id: UUID dell'ordine da eliminare
            
        Raises:
            NotFoundError: Se l'ordine non esiste
            ValidationError: Se l'ordine non è in stato draft o cancelled
        """
        # Recupera l'ordine con i part_usages
        work_order = await self.get_by_id(db, work_order_id)

        # Verifica che sia in stato draft o cancelled
        current_status = WorkOrderStatus(work_order.status)
        if current_status not in [WorkOrderStatus.DRAFT, WorkOrderStatus.CANCELLED]:
            logger.warning(
                "Impossibile eliminare ordine %s: stato=%s",
                work_order_id,
                work_order.status
            )
            raise BusinessValidationError(
                "Solo ordini in bozza o annullati possono essere eliminati"
            )

        # FIX 1: Se l'ordine ha PartUsage, ripristina il magazzino
        if work_order.part_usages:
            for part_usage in work_order.part_usages:
                # Carica il part se non già caricato
                if not part_usage.part:
                    part_result = await db.execute(
                        select(Part).where(Part.id == part_usage.part_id)
                    )
                    part = part_result.scalar_one_or_none()
                else:
                    part = part_usage.part
                
                if part:
                    # Incrementa la giacenza
                    part.stock_quantity = part.stock_quantity + part_usage.quantity
                    
                    # Crea movimento di magazzino di tipo IN
                    movement = StockMovement(
                        part_id=part.id,
                        movement_type="in",
                        quantity=part_usage.quantity,
                        reference=f"Ripristino da annullamento OdL {work_order_id}",
                        notes=f"Ripristino magazzino per annullamento ordine di lavoro",
                    )
                    db.add(movement)
                    
                    logger.info(
                        "Ripristinato magazzino per ricambio %s: qty=%s",
                        part.code,
                        part_usage.quantity
                    )

        await db.delete(work_order)
        await db.flush()

        logger.info("Eliminato ordine di lavoro: %s", work_order_id)

    async def change_status(
        self,
        db: AsyncSession,
        work_order_id: uuid.UUID,
        new_status: WorkOrderStatus,
    ) -> WorkOrder:
        """
        Cambia lo stato di un ordine di lavoro.
        
        Valida la transizione usando la matrice VALID_TRANSITIONS.
        
        Args:
            db: Sessione database
            work_order_id: UUID dell'ordine
            new_status: Nuovo stato desiderato
            
        Returns:
            WorkOrder: L'ordine con lo stato aggiornato
            
        Raises:
            NotFoundError: Se l'ordine non esiste
            ValidationError: Se la transizione non è valida
        """
        # Recupera l'ordine
        work_order = await self.get_by_id(db, work_order_id)

        # Converte lo stato corrente in enum
        try:
            current_status = WorkOrderStatus(work_order.status)
        except ValueError:
            logger.error("Stato invalido nel database: %s", work_order.status)
            raise BusinessValidationError(f"Stato invalido: {work_order.status}")

        # Verifica che la transizione sia valida
        allowed_transitions = VALID_TRANSITIONS.get(current_status, [])
        
        if new_status not in allowed_transitions:
            logger.warning(
                "Transizione non consentita: %s -> %s",
                current_status,
                new_status
            )
            raise BusinessValidationError(
                f"Transizione da '{current_status.value}' a '{new_status.value}' non consentita"
            )

        # Applica il nuovo stato
        old_status = work_order.status
        work_order.status = new_status.value

        # Logica specifica per alcuni stati
        if new_status == WorkOrderStatus.COMPLETED:
            # Imposta completed_at se completato
            work_order.completed_at = datetime.datetime.now(datetime.timezone.utc)
            
            # FIX 6: Aggiorna il chilometraggio del veicolo se km_out è presente
            if work_order.km_out and work_order.vehicle:
                vehicle_result = await db.execute(
                    select(Vehicle).where(Vehicle.id == work_order.vehicle_id)
                )
                vehicle = vehicle_result.scalar_one_or_none()
                if vehicle and (vehicle.current_km is None or work_order.km_out > vehicle.current_km):
                    vehicle.current_km = work_order.km_out
                    logger.info(
                        "Aggiornato chilometraggio veicolo %s: %s km",
                        vehicle.plate,
                        work_order.km_out
                    )
            logger.info("Ordine %s completato", work_order_id)
        
        elif new_status == WorkOrderStatus.CANCELLED:
            # FIX 1: Se l'ordine ha PartUsage, ripristina il magazzino
            if work_order.part_usages:
                for part_usage in work_order.part_usages:
                    # Carica il part se non già caricato
                    if not getattr(part_usage, 'part', None):
                        part_result = await db.execute(
                            select(Part).where(Part.id == part_usage.part_id)
                        )
                        part = part_result.scalar_one_or_none()
                    else:
                        part = part_usage.part
                    
                    if part:
                        # Incrementa la giacenza
                        part.stock_quantity = part.stock_quantity + part_usage.quantity
                        
                        # Crea movimento di magazzino di tipo IN
                        movement = StockMovement(
                            part_id=part.id,
                            movement_type="in",
                            quantity=part_usage.quantity,
                            reference=f"Ripristino da cancellazione OdL {work_order_id}",
                            notes=f"Ripristino magazzino per cancellazione ordine di lavoro",
                        )
                        db.add(movement)
                        
                        logger.info(
                            "Ripristinato magazzino per ricambio %s: qty=%s",
                            part.code,
                            part_usage.quantity
                        )
            logger.info("Ordine %s cancellato, magazzino ripristinato", work_order_id)
        
        elif new_status == WorkOrderStatus.IN_PROGRESS:
            # Se si riapre un ordine completato, resetta completed_at
            if work_order.completed_at is not None:
                work_order.completed_at = None
                logger.info("Ordine %s riaperto, reset completed_at", work_order_id)

        await db.flush()
        await db.refresh(work_order, ["client", "vehicle", "items"])

        logger.info(
            "Cambiato stato ordine %s: %s -> %s",
            work_order_id,
            old_status,
            new_status.value
        )
        return work_order

    # -------------------------------------------------------------------
    # Metodi per WorkOrderItem (voci di lavoro)
    # -------------------------------------------------------------------

    async def add_item(
        self,
        db: AsyncSession,
        work_order_id: uuid.UUID,
        item_data: WorkOrderItemCreate,
    ) -> WorkOrderItem:
        """
        Aggiunge una voce di lavoro a un ordine.
        
        Args:
            db: Sessione database
            work_order_id: UUID dell'ordine
            item_data: Dati della voce da aggiungere
            
        Returns:
            WorkOrderItem: La voce creata
            
        Raises:
            NotFoundError: Se l'ordine non esiste
            ValidationError: Se l'ordine non è in stato draft o in_progress
        """
        # Recupera l'ordine
        work_order = await self.get_by_id(db, work_order_id)

        # Verifica che lo stato permetta l'aggiunta di voci
        self._check_editable_status(work_order)

        # Crea la voce
        item = WorkOrderItem(
            work_order_id=work_order_id,
            description=item_data.description,
            quantity=item_data.quantity,
            unit_price=item_data.unit_price,
            item_type=item_data.item_type,
        )

        db.add(item)
        await db.flush()
        await db.refresh(item)

        logger.info("Aggiunta voce %s all'ordine %s", item.id, work_order_id)
        return item

    async def update_item(
        self,
        db: AsyncSession,
        work_order_id: uuid.UUID,
        item_id: uuid.UUID,
        item_data: WorkOrderItemUpdate,
    ) -> WorkOrderItem:
        """
        Aggiorna una voce di lavoro esistente.

        Args:
            db: Sessione database
            work_order_id: UUID dell'ordine di lavoro (per verifica appartenenza)
            item_id: UUID della voce da aggiornare
            item_data: Dati per l'aggiornamento

        Returns:
            WorkOrderItem: La voce aggiornata

        Raises:
            NotFoundError: Se la voce non esiste o non appartiene all'ordine
            ValidationError: Se l'ordine padre non permette modifiche
        """
        # Recupera la voce
        result = await db.execute(
            select(WorkOrderItem).where(WorkOrderItem.id == item_id)
        )
        item = result.scalar_one_or_none()

        if not item:
            raise NotFoundError(f"Voce di lavoro con ID {item_id} non trovata")

        # Verifica che l'item appartenga all'ordine specificato
        if item.work_order_id != work_order_id:
            raise NotFoundError(
                f"Voce di lavoro {item_id} non trovata nell'ordine {work_order_id}"
            )

        # Recupera l'ordine padre
        work_order = await self.get_by_id(db, item.work_order_id)

        # Verifica che lo stato permetta la modifica
        self._check_editable_status(work_order)

        # Aggiorna solo i campi forniti
        update_data = item_data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(item, field, value)

        await db.flush()
        await db.refresh(item)

        logger.info("Aggiornata voce di lavoro: %s", item_id)
        return item

    async def remove_item(
        self,
        db: AsyncSession,
        work_order_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> None:
        """
        Rimuove una voce di lavoro.

        Args:
            db: Sessione database
            work_order_id: UUID dell'ordine di lavoro (per verifica appartenenza)
            item_id: UUID della voce da rimuovere

        Raises:
            NotFoundError: Se la voce non esiste o non appartiene all'ordine
            ValidationError: Se l'ordine padre non permette la rimozione
        """
        # Recupera la voce
        result = await db.execute(
            select(WorkOrderItem).where(WorkOrderItem.id == item_id)
        )
        item = result.scalar_one_or_none()

        if not item:
            raise NotFoundError(f"Voce di lavoro con ID {item_id} non trovata")

        # Verifica che l'item appartenga all'ordine specificato
        if item.work_order_id != work_order_id:
            raise NotFoundError(
                f"Voce di lavoro {item_id} non trovata nell'ordine {work_order_id}"
            )

        # Recupera l'ordine padre
        work_order = await self.get_by_id(db, item.work_order_id)

        # Verifica che lo stato permetta la rimozione
        self._check_editable_status(work_order)

        await db.delete(item)
        await db.flush()

        logger.info("Rimossa voce di lavoro: %s", item_id)
