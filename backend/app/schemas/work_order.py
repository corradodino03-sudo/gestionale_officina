"""
Schemas Pydantic per gli Ordini di Lavoro
Progetto: Garage Manager (Gestionale Officina)

Definisce gli schemi di validazione e serializzazione per l'API.
"""

import datetime
import uuid
from decimal import Decimal
from enum import Enum
from typing import Optional
from zoneinfo import ZoneInfo

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)


# -------------------------------------------------------------------
# Enum per gli stati dell'ordine di lavoro
# -------------------------------------------------------------------

class WorkOrderStatus(str, Enum):
    """Enum che definisce i possibili stati di un ordine di lavoro."""
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    WAITING_PARTS = "waiting_parts"
    COMPLETED = "completed"
    INVOICED = "invoiced"
    CANCELLED = "cancelled"


# -------------------------------------------------------------------
# Enum per i tipi di voce dell'ordine di lavoro
# -------------------------------------------------------------------

class ItemType(str, Enum):
    """Enum che definisce i tipi di voce di un ordine di lavoro."""
    LABOR = "labor"
    SERVICE = "service"


# -------------------------------------------------------------------
# Matrice delle transizioni di stato valide
# -------------------------------------------------------------------

# Nota: la validazione delle transizioni avviene nel service layer (work_order_service.py)
# Questa matrice è definita qui come unica source of truth e importata dal service.
VALID_TRANSITIONS: dict[WorkOrderStatus, list[WorkOrderStatus]] = {
    WorkOrderStatus.DRAFT: [WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.CANCELLED],
    WorkOrderStatus.IN_PROGRESS: [
        WorkOrderStatus.WAITING_PARTS,
        WorkOrderStatus.COMPLETED,
        WorkOrderStatus.CANCELLED,
    ],
    WorkOrderStatus.WAITING_PARTS: [WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.CANCELLED],
    WorkOrderStatus.COMPLETED: [WorkOrderStatus.INVOICED],
    WorkOrderStatus.INVOICED: [],  # Stato finale
    WorkOrderStatus.CANCELLED: [],  # Stato finale
}


# -------------------------------------------------------------------
# Funzioni di validazione standalone
# -------------------------------------------------------------------

def validate_km_coherence(km_in: Optional[int], km_out: Optional[int]) -> None:
    """
    Valida la coerenza dei chilometraggi.
    
    Args:
        km_in: Chilometraggio all'ingresso
        km_out: Chilometraggio alla consegna
        
    Raises:
        ValueError: Se km_out è inferiore a km_in
    """
    if km_in is not None and km_out is not None:
        if km_out < km_in:
            raise ValueError("km_out non può essere inferiore a km_in")


def validate_problem_description_field(v: Optional[str]) -> Optional[str]:
    """
    Valida e normalizza la descrizione del problema.
    
    Args:
        v: Descrizione del problema
        
    Returns:
        Descrizione normalizzata
        
    Raises:
        ValueError: Se la descrizione è troppo corta
    """
    if v is not None:
        v = v.strip()
        if len(v) < 5:
            raise ValueError("La descrizione del problema deve avere almeno 5 caratteri")
    return v


# -------------------------------------------------------------------
# Schemas per WorkOrderItem (voci di lavoro)
# -------------------------------------------------------------------

class WorkOrderItemBase(BaseModel):
    """
    Schema base per le voci di lavoro.
    
    Attributes:
        description: Descrizione del lavoro/intervento
        quantity: Quantità (ore per manodopera, pezzi per interventi)
        unit_price: Prezzo unitario (orario o per unità)
        item_type: Tipo di voce: labor (manodopera) o service (intervento)
    """
    description: str = Field(..., min_length=1, max_length=500, description="Descrizione del lavoro")
    quantity: Decimal = Field(default=Decimal("1"), ge=Decimal("0"), description="Quantità")
    unit_price: Decimal = Field(default=Decimal("0"), ge=Decimal("0"), description="Prezzo unitario")
    item_type: ItemType = Field(..., description="Tipo di voce: labor (manodopera) o service (intervento)")


class WorkOrderItemCreate(WorkOrderItemBase):
    """Schema per la creazione di una voce di lavoro."""
    pass


class WorkOrderItemUpdate(BaseModel):
    """
    Schema per l'aggiornamento di una voce di lavoro.
    
    Tutti i campi sono opzionali per permettere aggiornamenti parziali.
    """
    description: Optional[str] = Field(None, min_length=1, max_length=500)
    quantity: Optional[Decimal] = Field(None, ge=Decimal("0"))
    unit_price: Optional[Decimal] = Field(None, ge=Decimal("0"))
    item_type: Optional[ItemType] = None


class WorkOrderItemRead(WorkOrderItemBase):
    """
    Schema per la lettura di una voce di lavoro.
    
    Include campi computed come line_total.
    """
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    work_order_id: uuid.UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime

    @computed_field
    @property
    def line_total(self) -> Decimal:
        """Totale della riga (quantity * unit_price)."""
        return self.quantity * self.unit_price


# -------------------------------------------------------------------
# Schemas per WorkOrder (ordini di lavoro)
# -------------------------------------------------------------------

class WorkOrderBase(BaseModel):
    """
    Schema base per gli ordini di lavoro.
    
    Attributes:
        client_id: UUID del cliente proprietario del veicolo
        vehicle_id: UUID del veicolo oggetto dell'intervento
        problem_description: Descrizione del problema segnalato dal cliente
        diagnosis: Diagnosi del meccanico dopo ispezione
        km_in: Chilometraggio al momento dell'ingresso
        km_out: Chilometraggio alla consegna
        estimated_delivery: Data prevista consegna
        internal_notes: Note interne tra operatori
    """
    client_id: uuid.UUID
    vehicle_id: uuid.UUID
    problem_description: str = Field(..., min_length=5, max_length=5000, description="Descrizione del problema")
    diagnosis: Optional[str] = Field(None, max_length=5000)
    km_in: Optional[int] = Field(None, ge=0, description="Chilometraggio all'ingresso")
    km_out: Optional[int] = Field(None, ge=0, description="Chilometraggio alla consegna")
    estimated_delivery: Optional[datetime.date] = Field(None, description="Data prevista consegna")
    internal_notes: Optional[str] = Field(None, max_length=5000, description="Note interne")

    @field_validator("problem_description")
    @classmethod
    def validate_problem_description(cls, v: str) -> str:
        """Valida e normalizza la descrizione del problema."""
        return validate_problem_description_field(v)

    @model_validator(mode="after")
    def validate_km(self) -> "WorkOrderBase":
        """Valida la coerenza dei chilometraggi."""
        validate_km_coherence(self.km_in, self.km_out)
        return self


class WorkOrderCreate(WorkOrderBase):
    """
    Schema per la creazione di un ordine di lavoro.
    
    Può includere le voci di lavoro iniziali.
    """
    items: Optional[list[WorkOrderItemCreate]] = Field(
        default=None,
        description="Voci di lavoro iniziali (opzionale)"
    )

    @model_validator(mode="after")
    def validate_estimated_delivery_create(self) -> "WorkOrderCreate":
        """Valida che estimated_delivery non sia nel passato (solo in creazione)."""
        if self.estimated_delivery is not None:
            today = datetime.datetime.now(ZoneInfo("Europe/Rome")).date()
            if self.estimated_delivery < today:
                raise ValueError("La data prevista consegna non può essere nel passato")
        return self


class WorkOrderUpdate(BaseModel):
    """
    Schema per l'aggiornamento di un ordine di lavoro.
    
    Tutti i campi sono opzionali per permettere aggiornamenti parziali.
    Lo status NON può essere cambiato tramite questo endpoint (usare change_status).
    """
    problem_description: Optional[str] = Field(None, min_length=5, max_length=5000)
    diagnosis: Optional[str] = Field(None, max_length=5000)
    km_in: Optional[int] = Field(None, ge=0)
    km_out: Optional[int] = Field(None, ge=0)
    estimated_delivery: Optional[datetime.date] = Field(None)
    internal_notes: Optional[str] = Field(None, max_length=5000)

    @field_validator("problem_description")
    @classmethod
    def validate_problem_description(cls, v: Optional[str]) -> Optional[str]:
        """Valida e normalizza la descrizione del problema."""
        return validate_problem_description_field(v)

    @model_validator(mode="after")
    def validate_km(self) -> "WorkOrderUpdate":
        """Valida la coerenza dei chilometraggi."""
        validate_km_coherence(self.km_in, self.km_out)
        return self


class WorkOrderStatusUpdate(BaseModel):
    """
    Schema per il cambio di stato di un ordine di lavoro.
    
    Usato esclusivamente per le transizioni di stato.
    """
    status: WorkOrderStatus = Field(..., description="Nuovo stato dell'ordine")


class WorkOrderRead(WorkOrderBase):
    """
    Schema per la lettura di un ordine di lavoro.
    
    Include lo stato, le voci di lavoro, i timestamp e i totali calcolati.
    """
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: WorkOrderStatus
    completed_at: Optional[datetime.datetime]
    created_at: datetime.datetime
    updated_at: datetime.datetime
    items: list[WorkOrderItemRead] = Field(default_factory=list)

    @computed_field
    @property
    def total_labor(self) -> Decimal:
        """Totale manodopera (somma line_total degli item con tipo 'labor')."""
        total = Decimal("0")
        for item in self.items:
            if item.item_type == ItemType.LABOR:
                total += item.line_total
        return total

    @computed_field
    @property
    def total_services(self) -> Decimal:
        """Totale interventi (somma line_total degli item con tipo 'service')."""
        total = Decimal("0")
        for item in self.items:
            if item.item_type == ItemType.SERVICE:
                total += item.line_total
        return total

    @computed_field
    @property
    def total(self) -> Decimal:
        """Totale complessivo (manodopera + interventi)."""
        return self.total_labor + self.total_services


# -------------------------------------------------------------------
# Schema per lista paginata
# -------------------------------------------------------------------

class WorkOrderList(BaseModel):
    """
    Schema per la risposta paginata degli ordini di lavoro.
    
    Attributes:
        items: Lista degli ordini di lavoro
        total: Numero totale di record
        page: Pagina corrente
        per_page: Record per pagina
        total_pages: Numero totale di pagine (calcolato automaticamente)
    """
    items: list[WorkOrderRead]
    total: int
    page: int
    per_page: int
    total_pages: int = 0

    @model_validator(mode="after")
    def compute_total_pages(self) -> "WorkOrderList":
        """Calcola automaticamente il numero totale di pagine."""
        if self.per_page > 0:
            self.total_pages = (self.total + self.per_page - 1) // self.per_page
        return self
