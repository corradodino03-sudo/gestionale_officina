"""
Main Entry Point - FastAPI Application
Progetto: Garage Manager (Gestionale Officina)

Configura l'applicazione FastAPI con middleware, router e lifecycle.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import close_db, init_db
from app.core.exceptions import (
    ConflictError,
    DuplicateError,
    NotFoundError,
    ValidationError,
)

# ------------------------------------------------------------
# Configurazione Logging
# ------------------------------------------------------------
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ------------------------------------------------------------
# Exception Handlers
# ------------------------------------------------------------
@app.exception_handler(NotFoundError)
async def not_found_exception_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    """
    Gestore per eccezioni NotFoundError.
    
    Converte l'eccezione in risposta HTTP 404.
    """
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)},
    )


@app.exception_handler(DuplicateError)
async def duplicate_exception_handler(request: Request, exc: DuplicateError) -> JSONResponse:
    """
    Gestore per eccezioni DuplicateError.
    
    Converte l'eccezione in risposta HTTP 409.
    """
    return JSONResponse(
        status_code=409,
        content={"detail": str(exc)},
    )


@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """
    Gestore per eccezioni ValidationError.
    
    Converte l'eccezione in risposta HTTP 422.
    """
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc)},
    )


@app.exception_handler(ConflictError)
async def conflict_exception_handler(request: Request, exc: ConflictError) -> JSONResponse:
    """
    Gestore per eccezioni ConflictError.
    
    Converte l'eccezione in risposta HTTP 409.
    """
    return JSONResponse(
        status_code=409,
        content={"detail": str(exc)},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Gestore generico per tutte le eccezioni non catturate.
    
    Converte l'eccezione in risposta HTTP 500 e logga l'errore.
    """
    logger.error(
        f"Unhandled exception: {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Errore interno del server"},
    )


# ------------------------------------------------------------
# Lifespan Handler
# ------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> None:
    """
    Gestisce il ciclo di vita dell'applicazione.

    - Startup: inizializza la connessione al database
    - Shutdown: chiude le connessioni database
    """
    # Startup
    logger.info(f"Avvio {settings.app_name} v{settings.app_version}")
    await init_db()
    logger.info("Applicazione avviata con successo")

    yield

    # Shutdown
    logger.info("Arresto applicazione in corso...")
    await close_db()
    logger.info("Applicazione arrestata")


# ------------------------------------------------------------
# FastAPI Application
# ------------------------------------------------------------
app = FastAPI(
    title=settings.app_name,
    description="Gestionale per officina meccanica - Backend API",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)


# ------------------------------------------------------------
# Middleware CORS
# ------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------
@app.get(
    "/health",
    name="Health Check",
    summary="Controlla lo stato dell'applicazione",
    tags=["System"],
)
async def health_check() -> dict[str, str]:
    """
    Endpoint per il controllo dello stato di salute.

    Returns:
        dict: Stato dell'applicazione
    """
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
    }


# ------------------------------------------------------------
# Router
# ------------------------------------------------------------
from app.api.v1 import api_v1_router

app.include_router(api_v1_router)
