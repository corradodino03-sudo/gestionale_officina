"""
Service Layer per l'entità Client
Progetto: Garage Manager (Gestionale Officina)

Definisce la logica di business per la gestione dei clienti.
Ottimizzato per installazione on-premise con focus su:
- Soft delete (cancellazione logica)
- Validazione proattiva dei dati
- Integrità del database
- Logging dettagliato
- Dependency Injection ready
"""

import logging
import uuid
from typing import Optional

from sqlalchemy import func, select, or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateError, NotFoundError, ConflictError
from app.models import Client
from app.schemas.client import ClientCreate, ClientUpdate

# Logger per questo modulo
logger = logging.getLogger(__name__)


class ClientService:
    """
    Service per la gestione delle operazioni CRUD sui clienti.
    
    Fornisce metodi asincroni per interagire con il database
    in modo centralizzato, senza dipendenze da FastAPI.
    
    Implementa:
    - Soft Delete: cancellazione logica tramite flag is_active
    - Validazione Proattiva: controllo duplicati tax_id prima del create
    - Filtro Automatico: di default esclude i clienti eliminati
    
    Usage with Dependency Injection:
        from app.services.client_service import ClientService
        
        @app.get("/clients")
        def get_clients(service: ClientService):
            return service.get_all(db)
    """

    async def get_all(
        self,
        db: AsyncSession,
        page: int = 1,
        per_page: int = 10,
        search: Optional[str] = None,
        include_inactive: bool = False,
    ) -> tuple[list[Client], int]:
        """
        Recupera la lista paginata dei clienti.
        
        Di default restituisce solo i clienti attivi (is_active=True).
        Impostare include_inactive=True per includere anche i clienti eliminati.
        
        Args:
            db: Sessione database
            page: Numero pagina (default 1)
            per_page: Elementi per pagina (default 10)
            search: Termine di ricerca opzionale
            include_inactive: Se True, include anche i clienti soft-deleted
            
        Returns:
            Tuple di (lista clienti, totale count)
        """
        # Build filter conditions
        conditions = []
        
        # Filtro automatico: di default esclude i soft-deleted
        if not include_inactive:
            conditions.append(Client.is_active == True)
        
        # Search filter
        if search:
            search_term = f"%{search}%"
            search_condition = or_(
                Client.name.ilike(search_term),
                Client.surname.ilike(search_term),
                Client.tax_id.ilike(search_term),
                Client.phone.ilike(search_term),
                Client.email.ilike(search_term),
            )
            conditions.append(search_condition)

        # Main query for data
        query = select(Client).order_by(Client.name.asc(), Client.surname.asc())
        if conditions:
            query = query.where(*conditions)

        # Calculate offset
        offset = (page - 1) * per_page

        # Execute query for data
        query = query.offset(offset).limit(per_page)
        result = await db.execute(query)
        clients = list(result.scalars().all())

        # Execute separate count query
        count_query = select(func.count()).select_from(Client)
        if conditions:
            count_query = count_query.where(*conditions)
        
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        logger.info(
            "Recuperati %s clienti su %s totali (pagina %s, include_inactive=%s)",
            len(clients), total, page, include_inactive
        )

        return clients, total

    async def get_by_id(
        self,
        db: AsyncSession,
        client_id: uuid.UUID,
        include_inactive: bool = False,
    ) -> Client:
        """
        Recupera un cliente tramite ID.
        
        Di default restituisce solo clienti attivi (is_active=True).
        
        Args:
            db: Sessione database
            client_id: UUID del cliente
            include_inactive: Se True, include anche clienti soft-deleted
            
        Returns:
            Oggetto Client
            
        Raises:
            NotFoundError: Se il cliente non esiste o è stato eliminato
        """
        # Build query with optional is_active filter
        query = select(Client).where(Client.id == client_id)
        
        if not include_inactive:
            query = query.where(Client.is_active == True)
        
        result = await db.execute(query)
        client = result.scalar_one_or_none()

        if client is None:
            logger.warning("Cliente non trovato o eliminato: %s", client_id)
            raise NotFoundError(f"Cliente con ID {client_id} non trovato")

        logger.debug("Recuperato cliente: %s - %s %s", client.id, client.name, client.surname)
        return client

    async def create(
        self,
        db: AsyncSession,
        client_data: ClientCreate,
    ) -> Client:
        """
        Crea un nuovo cliente.
        
        Implementa validazione proattiva: verifica che il tax_id
        non sia già in uso prima di creare il record.
        
        Args:
            db: Sessione database
            client_data: Dati del cliente da creare
            
        Returns:
            Oggetto Client appena creato
            
        Raises:
            DuplicateError: Se il tax_id è già in uso
            ConflictError: Se il database genera un errore imprevisto
        """
        # Estrai il tax_id per la validazione proattiva
        tax_id = client_data.tax_id
        
        # Validazione Proattiva: verifica duplicato tax_id PRIMA di creare
        if tax_id:
            existing = await self._check_tax_id_exists(db, tax_id)
            if existing:
                logger.warning(
                    "Tentativo di creare cliente con tax_id duplicato: %s (esistente: %s)",
                    tax_id, existing.id
                )
                raise DuplicateError(
                    f"Tax ID '{tax_id}' già registrato per un altro cliente"
                )
        
        # ------------------------------------------------------------
        # Validazione coerenza campi fiscali
        # ------------------------------------------------------------
        # Log informativo per regime speciali
        if client_data.is_foreign:
            logger.info(
                "Creato cliente estero: %s - %s (country_code: %s)",
                client_data.name, client_data.surname or "", client_data.country_code or "N/A"
            )
        
        if client_data.vat_exemption_code and client_data.vat_exemption_code.startswith("N6"):
            logger.info(
                "Creato cliente con reverse charge: %s - %s (codice: %s)",
                client_data.name, client_data.surname or "", client_data.vat_exemption_code
            )
        
        if client_data.split_payment:
            logger.info(
                "Creato cliente con split payment: %s - %s",
                client_data.name, client_data.surname or ""
            )

        # Converti Pydantic model in dict
        client_dict = client_data.model_dump()

        # Crea nuovo oggetto (is_active default=True impostato dal mixin)
        client = Client(**client_dict)

        try:
            db.add(client)
            await db.flush()
            await db.refresh(client)

            logger.info(
                "Creato nuovo cliente: %s - %s %s (tax_id: %s)",
                client.id, client.name, client.surname or "", client.tax_id or "N/A"
            )
            return client

        except IntegrityError as e:
            logger.error("Errore IntegrityError creazione cliente: %s - %s", e.__class__.__name__, e.orig)
            await db.rollback()
            # Mappatura errori del database sulle nostre eccezioni
            if "tax_id" in str(e.orig).lower():
                raise DuplicateError("Tax ID già registrato per un altro cliente")
            raise ConflictError("Errore durante la creazione del cliente")
            
        except SQLAlchemyError as e:
            logger.error("Errore SQLAlchemy creazione cliente: %s - %s", e.__class__.__name__, e)
            await db.rollback()
            raise ConflictError("Errore del database durante la creazione del cliente")

    async def update(
        self,
        db: AsyncSession,
        client_id: uuid.UUID,
        client_data: ClientUpdate,
    ) -> Client:
        """
        Aggiorna un cliente esistente.
        
        Args:
            db: Sessione database
            client_id: UUID del cliente da aggiornare
            client_data: Dati parziali del cliente
            
        Returns:
            Oggetto Client aggiornato
            
        Raises:
            NotFoundError: Se il cliente non esiste
            DuplicateError: Se il tax_id è già in uso
            ConflictError: Se il database genera un errore imprevisto
        """
        # Recupera il cliente esistente (solo attivo)
        client = await self.get_by_id(db, client_id)

        # Estrai il nuovo tax_id per la validazione proattiva
        update_data = client_data.model_dump(exclude_unset=True)
        new_tax_id = update_data.get("tax_id")
        
        # Validazione Proattiva: verifica che il nuovo tax_id non sia già in uso
        if new_tax_id and new_tax_id != client.tax_id:
            existing = await self._check_tax_id_exists(db, new_tax_id)
            if existing:
                logger.warning(
                    "Tentativo di aggiornare cliente %s con tax_id duplicato: %s",
                    client_id, new_tax_id
                )
                raise DuplicateError(
                    f"Tax ID '{new_tax_id}' già registrato per un altro cliente"
                )
        
        # ------------------------------------------------------------
        # Log per regime speciali (quando vengono impostati/modificati)
        # ------------------------------------------------------------
        is_foreign = update_data.get("is_foreign")
        if is_foreign is True:
            logger.info(
                "Cliente %s configurato come estero (country_code: %s)",
                client_id, update_data.get("country_code", client.country_code) or "N/A"
            )
        
        vat_exemption_code = update_data.get("vat_exemption_code")
        if vat_exemption_code and vat_exemption_code.startswith("N6"):
            logger.info(
                "Cliente %s configurato con reverse charge (codice: %s)",
                client_id, vat_exemption_code
            )
        
        split_payment = update_data.get("split_payment")
        if split_payment is True:
            logger.info(
                "Cliente %s configurato con split payment",
                client_id
            )

        # Applica gli aggiornamenti
        for field, value in update_data.items():
            setattr(client, field, value)

        try:
            await db.flush()
            await db.refresh(client)

            logger.info(
                "Aggiornato cliente: %s - %s %s",
                client.id, client.name, client.surname or ""
            )
            return client

        except IntegrityError as e:
            logger.error("Errore IntegrityError aggiornamento cliente: %s - %s", e.__class__.__name__, e.orig)
            await db.rollback()
            if "tax_id" in str(e.orig).lower():
                raise DuplicateError("Tax ID già registrato per un altro cliente")
            raise ConflictError("Errore durante l'aggiornamento del cliente")
            
        except SQLAlchemyError as e:
            logger.error("Errore SQLAlchemy aggiornamento cliente: %s - %s", e.__class__.__name__, e)
            await db.rollback()
            raise ConflictError("Errore del database durante l'aggiornamento del cliente")

    async def delete(
        self,
        db: AsyncSession,
        client_id: uuid.UUID,
        hard_delete: bool = False,
    ) -> None:
        """
        Elimina un cliente.
        
        Implementa soft delete: di default imposta is_active=False.
        Impostare hard_delete=True per eliminazione fisica (da usare con cautela).
        
        Args:
            db: Sessione database
            client_id: UUID del cliente da eliminare
            hard_delete: Se True, elimina fisicamente il record (default: False)
            
        Raises:
            NotFoundError: Se il cliente non esiste
            ConflictError: Se il database genera un errore imprevisto
        """
        # Recupera il cliente esistente (solo attivo)
        client = await self.get_by_id(db, client_id)

        try:
            if hard_delete:
                # Eliminazione fisica (hard delete)
                await db.delete(client)
                await db.flush()
                logger.warning("Hard delete cliente: %s - %s %s", 
                    client.id, client.name, client.surname or ""
                )
            else:
                # Soft delete: imposta is_active = False
                client.is_active = False
                await db.flush()
                logger.info("Soft delete cliente: %s - %s %s", 
                    client.id, client.name, client.surname or ""
                )

        except SQLAlchemyError as e:
            logger.error("Errore SQLAlchemy eliminazione cliente: %s - %s", e.__class__.__name__, e)
            await db.rollback()
            raise ConflictError("Errore del database durante l'eliminazione del cliente")

    async def reactivate(
        self,
        db: AsyncSession,
        client_id: uuid.UUID,
    ) -> Client:
        """
        Riattiva un cliente precedentemente eliminato (soft delete).
        
        Args:
            db: Sessione database
            client_id: UUID del cliente da riattivare
            
        Returns:
            Oggetto Client riattivato
            
        Raises:
            NotFoundError: Se il cliente non esiste
            ConflictError: Se il database genera un errore imprevisto
        """
        # Recupera il cliente (anche quelli soft-deleted)
        query = select(Client).where(
            Client.id == client_id,
            Client.is_active == False
        )
        result = await db.execute(query)
        client = result.scalar_one_or_none()

        if client is None:
            logger.warning("Cliente non trovato per riattivazione: %s", client_id)
            raise NotFoundError(f"Cliente con ID {client_id} non trovato")

        # Riattiva il cliente
        client.is_active = True

        try:
            await db.flush()
            await db.refresh(client)
            logger.info("Riattivato cliente: %s - %s %s", 
                client.id, client.name, client.surname or ""
            )
            return client
            
        except SQLAlchemyError as e:
            logger.error("Errore SQLAlchemy riattivazione cliente: %s - %s", e.__class__.__name__, e)
            await db.rollback()
            raise ConflictError("Errore del database durante la riattivazione del cliente")

    # ----------------------------------------------------------------
    # Metodi privati di supporto
    # ----------------------------------------------------------------
    
    async def _check_tax_id_exists(
        self,
        db: AsyncSession,
        tax_id: str,
    ) -> Optional[Client]:
        """
        Verifica se un tax_id è già in uso.
        
        Args:
            db: Sessione database
            tax_id: Codice Fiscale o Partita IVA da verificare
            
        Returns:
            Oggetto Client se trovato, None altrimenti
        """
        # Cerca tra i clienti attivi
        result = await db.execute(
            select(Client).where(
                Client.tax_id == tax_id,
                Client.is_active == True
            )
        )
        return result.scalar_one_or_none()
