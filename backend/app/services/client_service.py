"""
Service Layer per l'entità Client
Progetto: Garage Manager (Gestionale Officina)

Definisce la logica di business per la gestione dei clienti.
"""

import logging
import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateError, NotFoundError
from app.models import Client
from app.schemas.client import ClientCreate, ClientUpdate

# Logger per questo modulo
logger = logging.getLogger(__name__)


class ClientService:
    """
    Service per la gestione delle operazioni CRUD sui clienti.
    
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
        page: int = 1,
        per_page: int = 10,
        search: Optional[str] = None,
    ) -> tuple[list[Client], int]:
        """
        Recupera la lista paginata dei clienti.
        
        Args:
            db: Sessione database
            page: Numero pagina (default 1)
            per_page: Elementi per pagina (default 10)
            search: Termine di ricerca opzionale
            
        Returns:
            Tuple di (lista clienti, totale count)
        """
        # Build filter condition for search
        filter_condition = None
        if search:
            search_term = f"%{search}%"
            filter_condition = (
                Client.name.ilike(search_term)
                | Client.surname.ilike(search_term)
                | Client.tax_id.ilike(search_term)
                | Client.phone.ilike(search_term)
                | Client.email.ilike(search_term)
            )

        # Main query for data
        query = select(Client)
        if filter_condition is not None:
            query = query.where(filter_condition)

        # Calculate offset
        offset = (page - 1) * per_page

        # Execute query for data
        query = query.offset(offset).limit(per_page)
        result = await db.execute(query)
        clients = list(result.scalars().all())

        # Execute separate count query
        count_query = select(func.count()).select_from(Client)
        if filter_condition is not None:
            count_query = count_query.where(filter_condition)
        
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        logger.debug(f"Recuperati {len(clients)} clienti su {total} totali")

        return clients, total

    async def get_by_id(
        self,
        db: AsyncSession,
        client_id: uuid.UUID,
    ) -> Client:
        """
        Recupera un cliente tramite ID.
        
        Args:
            db: Sessione database
            client_id: UUID del cliente
            
        Returns:
            Oggetto Client
            
        Raises:
            NotFoundError: Se il cliente non esiste
        """
        result = await db.execute(
            select(Client).where(Client.id == client_id)
        )
        client = result.scalar_one_or_none()

        if client is None:
            logger.warning(f"Cliente non trovato: {client_id}")
            raise NotFoundError(f"Cliente con ID {client_id} non trovato")

        return client

    async def create(
        self,
        db: AsyncSession,
        client_data: ClientCreate,
    ) -> Client:
        """
        Crea un nuovo cliente.
        
        Args:
            db: Sessione database
            client_data: Dati del cliente da creare
            
        Returns:
            Oggetto Client appena creato
            
        Raises:
            DuplicateError: Se il tax_id è già in uso
        """
        # Converti Pydantic model in dict
        client_dict = client_data.model_dump()

        # Crea nuovo oggetto
        client = Client(**client_dict)

        try:
            db.add(client)
            await db.flush()
            await db.refresh(client)

            logger.info(f"Creato nuovo cliente: {client.id} - {client.name}")
            return client

        except IntegrityError as e:
            await db.rollback()
            logger.warning(f"Errore creazione cliente - duplicato: {e.orig}")
            raise DuplicateError("Tax ID già registrato")

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
        """
        # Recupera il cliente esistente
        client = await self.get_by_id(db, client_id)

        # Converti i dati in dict (esclude None)
        update_data = client_data.model_dump(exclude_unset=True)

        # Applica gli aggiornamenti
        for field, value in update_data.items():
            setattr(client, field, value)

        try:
            await db.flush()
            await db.refresh(client)

            logger.info(f"Aggiornato cliente: {client.id}")
            return client

        except IntegrityError as e:
            await db.rollback()
            logger.warning(f"Errore aggiornamento cliente - duplicato: {e.orig}")
            raise DuplicateError("Tax ID già registrato")

    async def delete(
        self,
        db: AsyncSession,
        client_id: uuid.UUID,
    ) -> None:
        """
        Elimina un cliente.
        
        Args:
            db: Sessione database
            client_id: UUID del cliente da eliminare
            
        Raises:
            NotFoundError: Se il cliente non esiste
        """
        # Recupera il cliente esistente
        client = await self.get_by_id(db, client_id)

        # Elimina
        await db.delete(client)
        await db.flush()

        logger.info(f"Eliminato cliente: {client_id}")

    async def search(
        self,
        db: AsyncSession,
        query: str,
    ) -> list[Client]:
        """
        Ricerca clienti per nome, cognome, tax_id, telefono o email.
        
        Usa ricerca case-insensitive con ilike.
        
        Args:
            db: Sessione database
            query: Termine di ricerca
            
        Returns:
            Lista di clienti trovati
        """
        search_term = f"%{query}%"

        result = await db.execute(
            select(Client).where(
                (Client.name.ilike(search_term))
                | (Client.surname.ilike(search_term))
                | (Client.tax_id.ilike(search_term))
                | (Client.phone.ilike(search_term))
                | (Client.email.ilike(search_term))
            )
        )

        clients = list(result.scalars().all())
        logger.debug(f"Ricerca '{query}': {len(clients)} risultati")

        return clients


# Istanza globale del service
client_service = ClientService()
