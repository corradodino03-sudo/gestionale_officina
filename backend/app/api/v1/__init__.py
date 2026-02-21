"""
API v1 Routes
Progetto: Garage Manager (Gestionale Officina)

Router versione 1 dell'API.
"""

from fastapi import APIRouter

from app.api.v1 import (
    clients, vehicles, work_orders, parts, part_categories, technicians, invoices, intent_declarations, cash_register, deposits, auth
)

# Router aggregato per v1
api_v1_router = APIRouter(prefix="/api/v1")

# Includi i router dei moduli
api_v1_router.include_router(auth.router)
api_v1_router.include_router(clients.router)
api_v1_router.include_router(vehicles.router)
api_v1_router.include_router(work_orders.router)
api_v1_router.include_router(parts.router)
api_v1_router.include_router(part_categories.router)
api_v1_router.include_router(technicians.router)
api_v1_router.include_router(invoices.router)
api_v1_router.include_router(invoices.credit_notes_router)
api_v1_router.include_router(intent_declarations.router)
api_v1_router.include_router(cash_register.router)
api_v1_router.include_router(deposits.router)

# Esportazione
__all__ = ["api_v1_router"]
