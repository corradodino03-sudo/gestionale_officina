"""
Schemas Pydantic per il progetto Garage Manager

Questo modulo contiene tutti gli schemi Pydantic utilizzati per la validazione
e serializzazione delle risposte API.
"""

# Import degli schemi per renderli disponibili tramite import diretto
# es: from app.schemas import VehicleRead, ClientRead, etc.

from app.schemas.client import ClientCreate, ClientRead, ClientUpdate
from app.schemas.vehicle import (
    FuelType,
    VehicleBase,
    VehicleCreate,
    VehicleList,
    VehicleRead,
    VehicleUpdate,
)
from app.schemas.work_order import (
    ItemType,
    WorkOrderCreate,
    WorkOrderItemCreate,
    WorkOrderItemRead,
    WorkOrderItemUpdate,
    WorkOrderList,
    WorkOrderRead,
    WorkOrderStatus,
    WorkOrderStatusUpdate,
    WorkOrderUpdate,
)

# NOTA: VehicleRead.model_rebuild() deve essere chiamato dopo l'import di ClientRead
# per risolvere il forward reference del campo client: Optional["ClientRead"]
VehicleRead.model_rebuild()

__all__ = [
    # Client schemas
    "ClientCreate",
    "ClientRead",
    "ClientUpdate",
    # Vehicle schemas
    "FuelType",
    "VehicleBase",
    "VehicleCreate",
    "VehicleList",
    "VehicleRead",
    "VehicleUpdate",
    # WorkOrder schemas
    "ItemType",
    "WorkOrderCreate",
    "WorkOrderItemCreate",
    "WorkOrderItemRead",
    "WorkOrderItemUpdate",
    "WorkOrderList",
    "WorkOrderRead",
    "WorkOrderStatus",
    "WorkOrderStatusUpdate",
    "WorkOrderUpdate",
]
