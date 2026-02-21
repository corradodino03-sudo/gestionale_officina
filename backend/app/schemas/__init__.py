"""
Schemas Pydantic per il progetto Garage Manager

Questo modulo contiene tutti gli schemi Pydantic utilizzati per la validazione
e serializzazione delle risposte API.
"""

# Import degli schemi per renderli disponibili tramite import diretto
# es: from app.schemas import VehicleRead, ClientRead, etc.

from app.schemas.client import ClientCreate, ClientRead, ClientUpdate
from app.schemas.user import UserCreate, UserLogin, UserUpdate, UserResponse
from app.schemas.token import TokenResponse, TokenRefresh, TokenPayload
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
from app.schemas.part import (
    MovementType,
    UnitOfMeasure,
    PartCategoryCreate,
    PartCategoryRead,
    PartCategoryUpdate,
    LowStockAlert,
    LowStockAlertList,
    PartCreate,
    PartList,
    PartRead,
    PartUpdate,
    PartUsageCreate,
    PartUsageList,
    PartUsageRead,
    StockMovementCreate,
    StockMovementList,
    StockMovementRead,
)
from app.schemas.invoice import (
    PaymentMethod,
    InvoiceStatus,
    InvoiceLineType,
    InvoiceLineBase,
    InvoiceLineCreate,
    InvoiceLineRead,
    PaymentBase,
    PaymentCreate,
    PaymentRead,
    InvoiceBase,
    InvoiceUpdate,
    InvoiceRead as InvoiceReadSchema,
    InvoiceList,
    RevenueReport,
    CreateInvoiceFromWorkOrder,
    CreditNoteRead,
    CreditNoteLineRead,
    PartialCreditNoteRequest,
    DepositStatus,
    DepositCreate,
    DepositRead,
    InvoiceCreationResponse,
)
from app.schemas.intent_declaration import (
    IntentDeclarationCreate,
    IntentDeclarationRead,
    IntentDeclarationUpdate,
    IntentDeclarationList,
)
from app.schemas.technician import (
    TechnicianCreate,
    TechnicianRead,
    TechnicianUpdate,
)
from app.schemas.cash_register import (
    CashRegisterSummary,
    CashRegisterCloseRead,
    CashRegisterCloseCreate,
)

# NOTA: VehicleRead.model_rebuild() deve essere chiamato dopo l'import di ClientRead
# per risolvere il forward reference del campo client: Optional["ClientRead"]
VehicleRead.model_rebuild()

# Rebuild per forward references circolari tra WorkOrder e Part
WorkOrderRead.model_rebuild()
PartUsageRead.model_rebuild()

# Rebuild per Technician in WorkOrder
WorkOrderRead.model_rebuild()
WorkOrderItemRead.model_rebuild()

# Rebuild per Invoice
InvoiceReadSchema.model_rebuild()

__all__ = [
    # Client schemas
    "ClientCreate",
    "ClientRead",
    "ClientUpdate",
    # User schemas
    "UserCreate",
    "UserLogin",
    "UserUpdate",
    "UserResponse",
    # Token schemas
    "TokenResponse",
    "TokenRefresh",
    "TokenPayload",
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
    # Part schemas
    "MovementType",
    "UnitOfMeasure",
    "PartCategoryCreate",
    "PartCategoryRead",
    "PartCategoryUpdate",
    "LowStockAlert",
    "LowStockAlertList",
    "PartCreate",
    "PartList",
    "PartRead",
    "PartUpdate",
    "PartUsageCreate",
    "PartUsageList",
    "PartUsageRead",
    "StockMovementCreate",
    "StockMovementList",
    "StockMovementRead",
    # Invoice schemas
    "PaymentMethod",
    "InvoiceStatus",
    "InvoiceLineType",
    "InvoiceLineBase",
    "InvoiceLineCreate",
    "InvoiceLineRead",
    "PaymentBase",
    "PaymentCreate",
    "PaymentRead",
    "InvoiceBase",
    "InvoiceUpdate",
    "InvoiceRead",
    "InvoiceList",
    "RevenueReport",
    "CreateInvoiceFromWorkOrder",
    "CreditNoteRead",
    "CreditNoteLineRead",
    "PartialCreditNoteRequest",
    "DepositStatus",
    "DepositCreate",
    "DepositRead",
    "InvoiceCreationResponse",
    # IntentDeclaration schemas
    "IntentDeclarationCreate",
    "IntentDeclarationRead",
    "IntentDeclarationUpdate",
    "IntentDeclarationList",
    # Technician schemas
    "TechnicianCreate",
    "TechnicianRead",
    "TechnicianUpdate",
    # Cash Register schemas
    "CashRegisterSummary",
    "CashRegisterCloseRead",
    "CashRegisterCloseCreate",
]
