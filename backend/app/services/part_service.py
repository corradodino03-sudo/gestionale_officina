"""
Servizi per la gestione dei Ricambi e del Magazzino
Progetto: Garage Manager (Gestionale Officina)

Contiene le funzioni di business logic per:
- CRUD ricambi
- Movimenti di magazzino
- Utilizzo ricambi in ordini di lavoro
- Alert scorte basse
"""

import logging
import uuid
from decimal import Decimal
from typing import Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessValidationError, DuplicateError, NotFoundError
from app.models.part import Part, PartUsage, StockMovement
from app.models.work_order import WorkOrder
from app.schemas.part import (
    MovementType,
    PartCreate,
    PartUpdate,
    PartUsageCreate,
    StockMovementCreate,
)

logger = logging.getLogger(__name__)


class PartService:
    """
    Service per la gestione dei ricambi e del magazzino.
    
    Fornisce metodi asincroni per interagire con il database
    in modo centralizzato, senza dipendenze da FastAPI.
    """

    def __init__(self) -> None:
        """Inizializza il service."""
        pass

    # ------------------------------------------------------------
    # CRUD Ricambi
    # ------------------------------------------------------------

    async def get_all(
        self,
        db: AsyncSession,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        below_minimum: bool = False,
        category_id: Optional[uuid.UUID] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Tuple[list[Part], int]:
        """
        Recupera tutti i ricambi con filtri e paginazione.
        
        Args:
            db: Sessione database
            search: Termine di ricerca (code, description, brand)
            is_active: Filtro per stato attivo
            below_minimum: Se True, filtra solo ricambi sotto il livello minimo
            page: Numero pagina (1-based)
            per_page: Elementi per pagina
            
        Returns:
            Tuple (lista ricambi, totale)
        """
        query = select(Part)
        count_query = select(func.count(Part.id))
        
        # Filtro ricerca
        if search:
            search_term = f"%{search}%"
            filter_condition = (
                Part.code.ilike(search_term) |
                Part.description.ilike(search_term) |
                Part.brand.ilike(search_term)
            )
            query = query.filter(filter_condition)
            count_query = count_query.filter(filter_condition)
        
        # Filtro is_active
        if is_active is not None:
            query = query.filter(Part.is_active == is_active)
            count_query = count_query.filter(Part.is_active == is_active)
        
        # Filtro below_minimum
        if below_minimum:
            query = query.filter(Part.stock_quantity < Part.min_stock_level)
            count_query = count_query.filter(Part.stock_quantity < Part.min_stock_level)

        # Filtro category_id
        if category_id is not None:
            query = query.filter(Part.category_id == category_id)
            count_query = count_query.filter(Part.category_id == category_id)

        # Ordine
        query = query.order_by(Part.code.asc())
        
        # Paginazione
        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page)
        
        # Esecuzione query
        result = await db.execute(query)
        items = list(result.scalars().all())
        
        result_count = await db.execute(count_query)
        total = result_count.scalar() or 0
        
        return items, total

    async def get_by_id(self, db: AsyncSession, part_id: uuid.UUID) -> Part:
        """
        Recupera un ricambio per ID.
        
        Args:
            db: Sessione database
            part_id: UUID del ricambio
            
        Returns:
            Il ricambio trovato
            
        Raises:
            NotFoundError: Se il ricambio non esiste
        """
        query = select(Part).where(Part.id == part_id)
        result = await db.execute(query)
        part = result.scalar_one_or_none()
        
        if not part:
            logger.warning("Ricambio non trovato: %s", part_id)
            raise NotFoundError(f"Ricambio non trovato: {part_id}")
        
        return part

    async def get_by_code(self, db: AsyncSession, code: str) -> Part:
        """
        Recupera un ricambio per codice (case insensitive).
        
        Args:
            db: Sessione database
            code: Codice del ricambio
            
        Returns:
            Il ricambio trovato
            
        Raises:
            NotFoundError: Se il ricambio non esiste
        """
        query = select(Part).where(func.upper(Part.code) == code.upper())
        result = await db.execute(query)
        part = result.scalar_one_or_none()
        
        if not part:
            logger.warning("Ricambio non trovato per codice: %s", code)
            raise NotFoundError(f"Ricambio non trovato: {code}")
        
        return part

    async def create(self, db: AsyncSession, data: PartCreate) -> Part:
        """
        Crea un nuovo ricambio.
        
        Args:
            db: Sessione database
            data: Dati del ricambio da creare
            
        Returns:
            Il ricambio creato
            
        Raises:
            DuplicateError: Se il codice esiste già
        """
        # Verifica unicità codice
        existing = await db.execute(
            select(Part).where(func.upper(Part.code) == data.code.upper())
        )
        existing = existing.scalar_one_or_none()
        
        if existing:
            logger.warning("Codice ricambio duplicato: %s", data.code)
            raise DuplicateError(f"Codice ricambio già esistente: {data.code}")
        
        # Crea nuovo ricambio (stock_quantity iniziale = 0)
        part = Part(
            code=data.code,
            description=data.description,
            brand=data.brand,
            compatible_models=data.compatible_models,
            purchase_price=data.purchase_price or Decimal("0"),
            sale_price=data.sale_price or Decimal("0"),
            # FIX 5: Includi vat_rate
            vat_rate=data.vat_rate if data.vat_rate is not None else Decimal("22.00"),
            stock_quantity=0,  # Iniziale = 0
            min_stock_level=data.min_stock_level or 0,
            location=data.location,
            is_active=data.is_active if data.is_active is not None else True,
            category_id=data.category_id,
            unit_of_measure=data.unit_of_measure.value if data.unit_of_measure else "pz",
        )
        
        db.add(part)
        await db.flush()
        await db.refresh(part)
        
        logger.info("Creato nuovo ricambio: %s", part.code)
        return part

    async def update(
        self,
        db: AsyncSession,
        part_id: uuid.UUID,
        data: PartUpdate,
    ) -> Part:
        """
        Aggiorna un ricambio esistente.
        
        Args:
            db: Sessione database
            part_id: UUID del ricambio
            data: Dati da aggiornare
            
        Returns:
            Il ricambio aggiornato
            
        Raises:
            NotFoundError: Se il ricambio non esiste
            DuplicateError: Se il nuovo codice esiste già
        """
        part = await self.get_by_id(db, part_id)
        
        # Se cambia code, verifica unicità
        if data.code and data.code.upper() != part.code.upper():
            existing = await db.execute(
                select(Part).where(func.upper(Part.code) == data.code.upper())
            )
            existing = existing.scalar_one_or_none()
            
            if existing:
                logger.warning("Codice ricambio duplicato: %s", data.code)
                raise DuplicateError(f"Codice ricambio già esistente: {data.code}")
            
            part.code = data.code
        
        # Aggiorna gli altri campi (stock_quantity NON modificabile qui)
        if data.description is not None:
            part.description = data.description
        if data.brand is not None:
            part.brand = data.brand
        if data.compatible_models is not None:
            part.compatible_models = data.compatible_models
        if data.purchase_price is not None:
            part.purchase_price = data.purchase_price
        if data.sale_price is not None:
            part.sale_price = data.sale_price
        # FIX 5: Aggiunto aggiornamento vat_rate
        if data.vat_rate is not None:
            part.vat_rate = data.vat_rate
        if data.min_stock_level is not None:
            part.min_stock_level = data.min_stock_level
        if data.location is not None:
            part.location = data.location
        if data.is_active is not None:
            part.is_active = data.is_active
        if data.category_id is not None:
            part.category_id = data.category_id
        if data.unit_of_measure is not None:
            part.unit_of_measure = data.unit_of_measure.value
        
        await db.flush()
        await db.refresh(part)
        
        logger.info("Aggiornato ricambio: %s", part.code)
        return part

    async def delete(self, db: AsyncSession, part_id: uuid.UUID) -> None:
        """
        Elimina un ricambio.
        
        Args:
            db: Sessione database
            part_id: UUID del ricambio
            
        Raises:
            NotFoundError: Se il ricambio non esiste
            BusinessValidationError: Se il ricambio è utilizzato in ordini di lavoro
        """
        part = await self.get_by_id(db, part_id)
        
        # Verifica che non abbia PartUsage associati
        usage_count_query = select(func.count(PartUsage.id)).where(
            PartUsage.part_id == part_id
        )
        result = await db.execute(usage_count_query)
        usage_count = result.scalar() or 0
        
        if usage_count > 0:
            logger.warning("Tentativo eliminazione ricambio usato in ordini: %s", part.code)
            raise BusinessValidationError(
                "Ricambio utilizzato in ordini di lavoro. Disattivarlo invece di eliminarlo."
            )
        
        await db.delete(part)
        await db.flush()
        
        logger.info("Eliminato ricambio: %s", part.code)

    # ------------------------------------------------------------
    # Movimenti Magazzino
    # ------------------------------------------------------------

    async def add_movement(
        self,
        db: AsyncSession,
        data: StockMovementCreate,
    ) -> StockMovement:
        """
        Aggiunge un movimento di magazzino.
        
        Args:
            db: Sessione database
            data: Dati del movimento
            
        Returns:
            Il movimento creato
            
        Raises:
            NotFoundError: Se il ricambio non esiste
            BusinessValidationError: Se la giacenza non è sufficiente per un movimento OUT
        """
        part = await self.get_by_id(db, data.part_id)
        
        # Calcola la variazione in base al tipo
        if data.movement_type == MovementType.IN:
            # Carico: aggiunge al magazzino
            quantity_delta = abs(data.quantity)
            part.stock_quantity = part.stock_quantity + quantity_delta
            
        elif data.movement_type == MovementType.OUT:
            # Scarico: sottrae dal magazzino
            quantity_delta = -abs(data.quantity)
            new_stock = part.stock_quantity + quantity_delta
            
            # Verifica giacenza sufficiente
            if new_stock < 0:
                logger.warning(
                    "Giacenza insufficiente per ricambio %s: disponibili=%s, richiesti=%s",
                    part.code,
                    part.stock_quantity,
                    abs(data.quantity),
                )
                raise BusinessValidationError(
                    f"Giacenza insufficiente. Disponibili: {part.stock_quantity}, richiesti: {abs(data.quantity)}"
                )
            
            part.stock_quantity = new_stock
            
        else:  # ADJUSTMENT
            # Il payload quantity = NUOVO VALORE ASSOLUTO desiderato
            # La variazione è la differenza rispetto al valore attuale
            # FIX 7: Verifica che il nuovo valore non sia negativo
            if data.quantity < 0:
                logger.warning(
                    "Tentativo di impostare giacenza negativa per ricambio %s: %s",
                    part.code,
                    data.quantity,
                )
                raise BusinessValidationError(
                    "La giacenza non può essere negativa"
                )
            quantity_delta = data.quantity - part.stock_quantity
            part.stock_quantity = data.quantity
        
        # Crea il movimento
        movement = StockMovement(
            part_id=part.id,
            movement_type=data.movement_type.value,
            quantity=quantity_delta,
            reference=data.reference,
            notes=data.notes,
        )
        
        db.add(movement)
        await db.flush()
        await db.refresh(part)
        await db.refresh(movement)
        
        logger.info(
            "Creato movimento %s per ricambio %s: qty=%s, nuovo stock=%s",
            data.movement_type.value,
            part.code,
            quantity_delta,
            part.stock_quantity,
        )
        
        return movement

    async def get_movements(
        self,
        db: AsyncSession,
        part_id: uuid.UUID,
        movement_type: Optional[MovementType] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Tuple[list[StockMovement], int]:
        """
        Recupera lo storico movimenti per un ricambio.
        
        Args:
            db: Sessione database
            part_id: UUID del ricambio
            movement_type: Filtro opzionale per tipo movimento
            page: Numero pagina (1-based)
            per_page: Elementi per pagina
            
        Returns:
            Tuple (lista movimenti, totale)
        """
        # Verifica che il ricambio esista
        await self.get_by_id(db, part_id)
        
        query = select(StockMovement).where(StockMovement.part_id == part_id)
        count_query = select(func.count(StockMovement.id)).where(
            StockMovement.part_id == part_id
        )
        
        # Filtro tipo movimento
        if movement_type:
            query = query.filter(StockMovement.movement_type == movement_type.value)
            count_query = count_query.filter(
                StockMovement.movement_type == movement_type.value
            )
        
        # Ordine: più recenti prima
        query = query.order_by(StockMovement.created_at.desc())
        
        # Paginazione
        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page)
        
        # Esecuzione query
        result = await db.execute(query)
        items = list(result.scalars().all())
        
        result_count = await db.execute(count_query)
        total = result_count.scalar() or 0
        
        return items, total

    # ------------------------------------------------------------
    # Utilizzo Ricambi in Ordini
    # ------------------------------------------------------------

    async def add_part_to_work_order(
        self,
        db: AsyncSession,
        work_order_id: uuid.UUID,
        data: PartUsageCreate,
    ) -> PartUsage:
        """
        Aggiunge un ricambio a un ordine di lavoro.
        
        Args:
            db: Sessione database
            work_order_id: UUID dell'ordine di lavoro
            data: Dati dell'utilizzo ricambio
            
        Returns:
            Il PartUsage creato
            
        Raises:
            NotFoundError: Se l'ordine o il ricambio non esiste
            BusinessValidationError: Se lo stato dell'ordine non permette modifiche
                                      o se la giacenza è insufficiente
        """
        # Verifica ordine esiste
        query_wo = select(WorkOrder).where(WorkOrder.id == work_order_id)
        result_wo = await db.execute(query_wo)
        work_order = result_wo.scalar_one_or_none()
        
        if not work_order:
            logger.warning("Ordine di lavoro non trovato: %s", work_order_id)
            raise NotFoundError(f"Ordine di lavoro non trovato: {work_order_id}")
        
        # Verifica stato ordine: DRAFT o IN_PROGRESS
        if work_order.status not in ("draft", "in_progress"):
            logger.warning(
                "Ordine %s in stato non modificabile: %s",
                work_order_id,
                work_order.status,
            )
            raise BusinessValidationError(
                f"Non è possibile aggiungere ricambi a un ordine in stato: {work_order.status}"
            )
        
        # Verifica ricambio esiste ed è attivo
        part_query = select(Part).where(Part.id == data.part_id).with_for_update(of=(Part,))
        part_result = await db.execute(part_query)
        part = part_result.scalar_one_or_none()
        
        if not part:
            logger.warning("Ricambio non trovato: %s", data.part_id)
            raise NotFoundError(f"Ricambio non trovato: {data.part_id}")
        
        if not part.is_active:
            logger.warning("Ricambio non attivo: %s", part.code)
            raise BusinessValidationError(f"Ricambio non disponibile: {part.code}")
        
        # Verifica giacenza sufficiente
        if part.stock_quantity < data.quantity:
            logger.warning(
                "Giacenza insufficiente per ricambio %s: disponibili=%s, richiesti=%s",
                part.code,
                part.stock_quantity,
                data.quantity,
            )
            raise BusinessValidationError(
                f"Giacenza insufficiente. Disponibili: {part.stock_quantity}, richiesti: {data.quantity}"
            )
        
        # Determina il prezzo unitario
        unit_price = data.unit_price
        if not unit_price or unit_price == Decimal("0"):
            unit_price = part.sale_price
        
        # Crea il PartUsage
        part_usage = PartUsage(
            work_order_id=work_order_id,
            part_id=data.part_id,
            quantity=data.quantity,
            unit_price=unit_price,
            unit_of_measure=part.unit_of_measure,
        )
        
        db.add(part_usage)
        
        # Crea automaticamente il movimento di magazzino (OUT)
        movement = StockMovement(
            part_id=part.id,
            movement_type="out",
            quantity=-data.quantity,
            reference=f"Ordine di lavoro {work_order_id}",
            notes=f"Utilizzo in ordine di lavoro",
        )
        
        db.add(movement)
        
        # Aggiorna la giacenza
        part.stock_quantity = part.stock_quantity - data.quantity
        
        await db.flush()
        await db.refresh(part_usage)
        await db.refresh(part)
        
        logger.info(
            "Aggiunto ricambio %s (qty=%s) all'ordine %s",
            part.code,
            data.quantity,
            work_order_id,
        )
        
        return part_usage

    async def remove_part_from_work_order(
        self,
        db: AsyncSession,
        work_order_id: uuid.UUID,
        part_usage_id: uuid.UUID,
    ) -> None:
        """
        Rimuove un ricambio da un ordine di lavoro e ripristina il magazzino.
        
        Args:
            db: Sessione database
            work_order_id: UUID dell'ordine di lavoro
            part_usage_id: UUID del PartUsage da rimuovere
            
        Raises:
            NotFoundError: Se il PartUsage non esiste o non appartiene all'ordine
            BusinessValidationError: Se lo stato dell'ordine non permette modifiche
        """
        # Recupera il PartUsage
        query = select(PartUsage).where(PartUsage.id == part_usage_id)
        result = await db.execute(query)
        part_usage = result.scalar_one_or_none()
        
        if not part_usage:
            logger.warning("PartUsage non trovato: %s", part_usage_id)
            raise NotFoundError(f"Utilizzo ricambio non trovato: {part_usage_id}")
        
        # Verifica appartenenza all'ordine
        if part_usage.work_order_id != work_order_id:
            logger.warning(
                "PartUsage %s non appartiene all'ordine %s",
                part_usage_id,
                work_order_id,
            )
            raise NotFoundError(f"Utilizzo ricambio non trovato nell'ordine: {work_order_id}")
        
        # Verifica ordine esiste e stato permette modifiche
        query_wo = select(WorkOrder).where(WorkOrder.id == work_order_id)
        result_wo = await db.execute(query_wo)
        work_order = result_wo.scalar_one_or_none()
        
        if not work_order:
            raise NotFoundError(f"Ordine di lavoro non trovato: {work_order_id}")
        
        if work_order.status not in ("draft", "in_progress"):
            raise BusinessValidationError(
                f"Non è possibile rimuovere ricambi da un ordine in stato: {work_order.status}"
            )
        
        # Recupera il ricambio
        part = await self.get_by_id(db, part_usage.part_id)
        
        # Crea automaticamente il movimento di magazzino (IN) per ricaricare
        movement = StockMovement(
            part_id=part.id,
            movement_type="in",
            quantity=part_usage.quantity,
            reference=f"Annullamento utilizzo ordine {work_order_id}",
            notes=f"Rimozione ricambio da ordine di lavoro",
        )
        
        db.add(movement)
        
        # Aggiorna la giacenza
        part.stock_quantity = part.stock_quantity + part_usage.quantity
        
        # Elimina il PartUsage
        await db.delete(part_usage)
        await db.flush()
        await db.refresh(part)
        
        logger.info(
            "Rimosso ricambio %s (qty=%s) dall'ordine %s",
            part.code,
            part_usage.quantity,
            work_order_id,
        )

    async def get_parts_for_work_order(
        self,
        db: AsyncSession,
        work_order_id: uuid.UUID,
    ) -> list[PartUsage]:
        """
        Recupera tutti i ricambi utilizzati in un ordine di lavoro.
        
        Args:
            db: Sessione database
            work_order_id: UUID dell'ordine di lavoro
            
        Returns:
            Lista dei PartUsage con i dati del ricambio caricati
        """
        from sqlalchemy.orm import selectinload
        
        query = (
            select(PartUsage)
            .options(selectinload(PartUsage.part))
            .where(PartUsage.work_order_id == work_order_id)
            .order_by(PartUsage.created_at.asc())
        )
        
        result = await db.execute(query)
        items = list(result.scalars().all())
        
        return items

    async def get_low_stock_alerts(self, db: AsyncSession) -> list[Part]:
        """
        Recupera tutti i ricambi sotto il livello minimo di stock.
        
        Args:
            db: Sessione database
            
        Returns:
            Lista dei ricambi con stock sotto il minimo, ordinati per deficit decrescente
        """
        query = (
            select(Part)
            .where(Part.is_active == True)
            .where(Part.stock_quantity < Part.min_stock_level)
            .order_by((Part.min_stock_level - Part.stock_quantity).desc())
        )
        
        result = await db.execute(query)
        items = list(result.scalars().all())
        
        logger.info("Trovati %s ricambi sotto il livello minimo", len(items))
        
        return items


# Istanza singleton del service
part_service = PartService()
