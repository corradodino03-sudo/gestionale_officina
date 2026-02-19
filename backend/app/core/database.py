"""
Configurazione Database - SQLAlchemy 2.0 Async
Progetto: Garage Manager (Gestionale Officina)

Definisce engine, session factory e dependency injection per FastAPI.
"""

import logging
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# Logger per questo modulo
logger = logging.getLogger(__name__)

# ------------------------------------------------------------
# Engine Async SQLAlchemy 2.0
# ------------------------------------------------------------
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.debug,  # Log query in modalità debug
    pool_pre_ping=True,   # Verifica connessione prima di usarla
    pool_size=settings.db_pool_size,      # Dimensione pool connessioni
    max_overflow=settings.db_max_overflow,  # Connessioni extra oltre pool_size
)


# ------------------------------------------------------------
# Session Factory
# ------------------------------------------------------------
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency injection per FastAPI.

    Crea una sessione database per ogni richiesta e la chiude
    automaticamente al termine.

    Yields:
        AsyncSession: Sessione database async

    Example:
        @app.get("/users")
        async def get_users(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Inizializza la connessione al database.

    Esegue un test di connessione per verificare
    che il database sia raggiungibile.
    """
    try:
        async with engine.begin() as conn:
            # Test connessione
            await conn.execute(text("SELECT 1"))
        logger.info("Connessione al database stabilita con successo")
    except Exception as e:
        logger.error("Errore connessione database: %s", e)
        raise


async def close_db() -> None:
    """
    Chiude le connessioni al database.

    Da chiamare durante lo shutdown dell'applicazione.
    """
    await engine.dispose()
    logger.info("Connessioni database chiuse")
