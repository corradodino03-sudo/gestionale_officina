"""
API v1 Routes
Progetto: Garage Manager (Gestionale Officina)

Router versione 1 dell'API.
"""

from fastapi import APIRouter

from app.api.v1 import clients, vehicles, work_orders

# Router aggregato per v1
api_v1_router = APIRouter(prefix="/api/v1")

# Includi i router dei moduli
api_v1_router.include_router(clients.router)
api_v1_router.include_router(vehicles.router)
api_v1_router.include_router(work_orders.router)

# Esportazione
__all__ = ["api_v1_router"]
