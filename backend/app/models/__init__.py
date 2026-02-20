"""
Modelli Database SQLAlchemy
Progetto: Garage Manager (Gestionale Officina)

Import centralizzato di tutti i modelli per Alembic e usage generico.

Modelli previsti (da implementare):
- Client: Anagrafica clienti
- Vehicle: Veicoli associati ai clienti
- WorkOrder: Ordini di lavoro
- WorkOrderItem: Voci di lavoro per ordine
- Part: Catalogo ricambi
- PartUsage: Utilizzo ricambi in ordini
- StockMovement: Movimenti magazzino
- Invoice: Fatture
- InvoiceLine: Righe fattura
"""

# SQLAlchemy 2.0 Base declarativa
# Importato qui per essere disponibile per tutti i modelli
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class per tutti i modelli SQLAlchemy."""
    pass


# Import modelli implementati
from app.models.client import Client
from app.models.vehicle import Vehicle
from app.models.work_order import WorkOrder, WorkOrderItem
from app.models.part import Part, PartUsage, StockMovement, PartCategory
from app.models.invoice import Invoice, InvoiceLine, Payment, PaymentAllocation, CreditNote, CreditNoteLine, Deposit
from app.models.intent_declaration import IntentDeclaration
from app.models.technician import Technician
from app.models.cash_register import CashRegisterClose

# Placeholder per import modelli futuri
# from app.models.vehicle import Vehicle
# from app.models.work_order import WorkOrder, WorkOrderItem
# from app.models.part import Part, PartUsage, StockMovement
# from app.models.invoice import Invoice, InvoiceLine

# Esportazione di tutti i modelli per Alembic
__all__ = [
    "Base",
    "Client",
    "Vehicle",
    "WorkOrder",
    "WorkOrderItem",
    "Part",
    "PartCategory",
    "PartUsage",
    "StockMovement",
    "Invoice",
    "InvoiceLine",
    "Payment",
    "PaymentAllocation",
    "IntentDeclaration",
    "CreditNote",
    "CreditNoteLine",
    "Technician",
    "CashRegisterClose",
    "Deposit",
]
