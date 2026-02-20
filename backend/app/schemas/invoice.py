"""
Schemas Pydantic per la Fatturazione
Progetto: Garage Manager (Gestionale Officina)

Contiene:
- Enums: PaymentMethod, InvoiceStatus, InvoiceLineType
- Schemas per InvoiceLine
- Schemas per Payment
- Schemas per Invoice
"""

import uuid
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from app.core.exceptions import BusinessValidationError


# -------------------------------------------------------------------
# Enum
# -------------------------------------------------------------------

class PaymentMethod(str, Enum):
    """Metodi di pagamento supportati."""
    CASH = "cash"
    POS = "pos"
    BANK_TRANSFER = "bank_transfer"
    CHECK = "check"
    OTHER = "other"


class InvoiceStatus(str, Enum):
    """Enum per rappresentare lo stato calcolato della fattura."""
    PAID = "paid"
    PARTIAL = "partial"
    UNPAID = "unpaid"
    OVERDUE = "overdue"


class InvoiceLineType(str, Enum):
    """Tipi di riga della fattura."""
    LABOR = "labor"
    SERVICE = "service"
    PART = "part"


# -------------------------------------------------------------------
# Schemas per InvoiceLine
# -------------------------------------------------------------------

class InvoiceLineBase(BaseModel):
    """Schema base per le righe della fattura."""
    
    line_type: InvoiceLineType = Field(
        ...,
        description="Tipo riga: labor (manodopera), service (servizio), part (ricambio)"
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Descrizione della riga"
    )
    quantity: Decimal = Field(
        ...,
        ge=0,
        description="Quantità",
        serialization_alias="quantity"
    )
    unit_price: Decimal = Field(
        ...,
        ge=0,
        description="Prezzo unitario",
        serialization_alias="unitPrice"
    )
    vat_rate: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Aliquota IVA specifica della riga",
        serialization_alias="vatRate"
    )
    line_number: int = Field(
        ...,
        ge=1,
        description="Numero progressivo riga nella fattura",
        serialization_alias="lineNumber"
    )
    
    model_config = ConfigDict(from_attributes=True)


class InvoiceLineCreate(InvoiceLineBase):
    """Schema per la creazione di una riga fattura."""
    pass


class InvoiceLineRead(InvoiceLineBase):
    """Schema per la lettura di una riga fattura."""
    
    id: uuid.UUID = Field(..., description="UUID della riga fattura")
    invoice_id: uuid.UUID = Field(..., description="UUID della fattura")
    created_at: date = Field(..., description="Data/ora creazione")
    updated_at: date = Field(..., description="Data/ora ultimo aggiornamento")
    
    @computed_field
    @property
    def subtotal(self) -> Decimal:
        """Imponibile riga (senza IVA)."""
        return self.quantity * self.unit_price
    
    @computed_field
    @property
    def vat_amount(self) -> Decimal:
        """Importo IVA riga."""
        return (self.subtotal * self.vat_rate) / Decimal("100")
    
    @computed_field
    @property
    def total(self) -> Decimal:
        """Totale riga (con IVA)."""
        return self.subtotal + self.vat_amount
    
    model_config = ConfigDict(from_attributes=True)


# -------------------------------------------------------------------
# Schemas per PaymentAllocation
# -------------------------------------------------------------------

class PaymentAllocationBase(BaseModel):
    """Schema base per allocazione pagamento."""
    
    invoice_id: uuid.UUID = Field(
        ...,
        description="ID fattura destinazione",
        serialization_alias="invoiceId"
    )
    amount: Decimal = Field(
        ...,
        gt=0,
        description="Importo allocato a questa fattura"
    )
    
    model_config = ConfigDict(from_attributes=True)


class PaymentAllocationCreate(PaymentAllocationBase):
    """Schema per creare una nuova allocazione."""
    pass


class PaymentAllocationRead(PaymentAllocationBase):
    """Schema per leggere un'allocazione esistente."""
    
    id: uuid.UUID = Field(..., description="UUID dell'allocazione")
    payment_id: uuid.UUID = Field(
        ...,
        description="UUID del pagamento",
        serialization_alias="paymentId"
    )
    created_at: date = Field(..., description="Data/ora creazione")
    
    # Denormalizzazione opzionale per comodità API
    invoice_number: Optional[str] = Field(
        None,
        description="Numero fattura",
        serialization_alias="invoiceNumber"
    )
    
    model_config = ConfigDict(from_attributes=True)


# -------------------------------------------------------------------
# Schemas per Payment
# -------------------------------------------------------------------

class PaymentBase(BaseModel):
    """Schema base per pagamento (generico, non legato a fattura specifica)."""
    
    client_id: uuid.UUID = Field(
        ...,
        description="ID cliente che ha effettuato il pagamento",
        serialization_alias="clientId"
    )
    amount: Decimal = Field(
        ...,
        gt=0,
        description="Importo totale pagamento"
    )
    payment_date: date = Field(
        ...,
        description="Data pagamento",
        serialization_alias="paymentDate"
    )
    payment_method: PaymentMethod = Field(
        ...,
        description="Metodo di pagamento",
        serialization_alias="paymentMethod"
    )
    reference: Optional[str] = Field(
        None,
        max_length=255,
        description="Riferimento (numero assegno, CRO bonifico, etc.)"
    )
    notes: Optional[str] = Field(
        None,
        description="Note aggiuntive sul pagamento"
    )
    
    model_config = ConfigDict(from_attributes=True)
    
    @field_validator("payment_date")
    @classmethod
    def validate_payment_date(cls, v: date) -> date:
        """Valida che la data pagamento non sia futura."""
        from datetime import date as today
        if v > today.today():
            raise ValueError("La data del pagamento non può essere futura")
        return v


class PaymentCreate(PaymentBase):
    """
    Schema per creare un nuovo pagamento con allocazioni.
    
    Supporta due modalità:
    1. Allocazione automatica (strategy):
       - "fifo": alloca su fatture più vecchie
       - "overdue_first": alloca su scadute prima
    
    2. Allocazione manuale (allocations):
       - Lista esplicita di {invoice_id, amount}
    """
    
    allocation_strategy: Optional[str] = Field(
        default="fifo",
        description="Strategia allocazione: 'fifo', 'overdue_first', 'manual'",
        serialization_alias="allocationStrategy"
    )
    
    # Se strategy="manual", questa lista è obbligatoria
    allocations: Optional[list[PaymentAllocationCreate]] = Field(
        default=None,
        description="Allocazioni manuali (usato solo se strategy='manual')"
    )
    
    @model_validator(mode="after")
    def validate_allocation_strategy(self) -> "PaymentCreate":
        """Valida coerenza tra strategy e allocations."""
        if self.allocation_strategy == "manual":
            if not self.allocations:
                raise BusinessValidationError(
                    "Se allocation_strategy='manual', devi specificare allocations"
                )
            
            # Verifica che la somma allocations <= amount
            total_allocated = sum(a.amount for a in self.allocations)
            if total_allocated > self.amount:
                raise BusinessValidationError(
                    f"Somma allocazioni ({total_allocated}) supera importo pagamento ({self.amount})"
                )
        
        return self


class PaymentRead(PaymentBase):
    """Schema per leggere un pagamento esistente."""
    
    id: uuid.UUID = Field(..., description="UUID del pagamento")
    created_at: date = Field(..., description="Data/ora creazione")
    
    # Allocazioni
    allocations: list[PaymentAllocationRead] = Field(
        default_factory=list,
        description="Allocazioni su fatture"
    )
    
    # -------------------------------------------------------------------
    # Computed Fields
    # -------------------------------------------------------------------
    @computed_field
    @property
    def allocated_amount(self) -> Decimal:
        """Importo totale allocato."""
        return sum(a.amount for a in self.allocations)
    
    @computed_field
    @property
    def unallocated_amount(self) -> Decimal:
        """Importo non ancora allocato."""
        return self.amount - self.allocated_amount
    
    @computed_field
    @property
    def is_fully_allocated(self) -> bool:
        """True se tutto il pagamento è allocato."""
        return self.unallocated_amount == Decimal("0")
    
    model_config = ConfigDict(from_attributes=True)


# -------------------------------------------------------------------
# Schemas per Invoice
# -------------------------------------------------------------------

class InvoiceBase(BaseModel):
    """Schema base per le fatture."""
    
    work_order_id: uuid.UUID = Field(
        ...,
        description="UUID dell'ordine di lavoro",
        serialization_alias="workOrderId"
    )
    invoice_date: date = Field(
        ...,
        description="Data emissione fattura",
        serialization_alias="invoiceDate"
    )
    due_date: date = Field(
        ...,
        description="Data scadenza pagamento",
        serialization_alias="dueDate"
    )
    vat_rate: Decimal = Field(
        default=Decimal("22.00"),
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Aliquota IVA applicata (default 22%)",
        serialization_alias="vatRate"
    )
    notes: Optional[str] = Field(
        None,
        description="Note interne (non stampate in fattura)"
    )
    customer_notes: Optional[str] = Field(
        None,
        description="Note per il cliente (stampate in fattura)",
        serialization_alias="customerNotes"
    )
    
    model_config = ConfigDict(from_attributes=True)
    
    @model_validator(mode="after")
    def validate_dates(self) -> "InvoiceBase":
        """Valida che due_date >= invoice_date."""
        if self.due_date < self.invoice_date:
            raise BusinessValidationError(
                "La data di scadenza non può essere precedente alla data fattura"
            )
        return self


class InvoiceCreate(InvoiceBase):
    """Schema per la creazione di una fattura."""
    
    # NON include:
    # - client_id (preso dal work_order)
    # - invoice_number (generato automaticamente dal service)
    # - subtotal/vat_amount/total (calcolati dal service)
    # - vat_exemption/split_payment (copiati dal cliente)
    
    @field_validator("vat_rate")
    @classmethod
    def validate_vat_rate(cls, v: Decimal) -> Decimal:
        """Valida l'aliquota IVA."""
        if v < 0 or v > 100:
            raise ValueError("L'aliquota IVA deve essere compresa tra 0 e 100")
        return v


class InvoiceUpdate(BaseModel):
    """Schema per l'aggiornamento di una fattura."""
    
    # Campi modificabili dopo la creazione
    notes: Optional[str] = Field(
        None,
        description="Note interne (non stampate in fattura)"
    )
    customer_notes: Optional[str] = Field(
        None,
        description="Note per il cliente (stampate in fattura)",
        serialization_alias="customerNotes"
    )
    due_date: Optional[date] = Field(
        None,
        description="Data scadenza pagamento",
        serialization_alias="dueDate"
    )
    
    model_config = ConfigDict(from_attributes=True)
    
    @model_validator(mode="after")
    def validate_update(self) -> "InvoiceUpdate":
        """Valida che almeno un campo sia stato modificato."""
        if not any([self.notes is not None, self.customer_notes is not None, self.due_date is not None]):
            raise BusinessValidationError("È necessario modificare almeno un campo")
        return self


class InvoiceRead(InvoiceBase):
    """Schema per la lettura di una fattura."""
    
    id: uuid.UUID = Field(..., description="UUID della fattura")
    client_id: uuid.UUID = Field(..., description="UUID del cliente")
    invoice_number: str = Field(
        ...,
        description="Numero fattura progressivo annuale",
        serialization_alias="invoiceNumber"
    )
    # Importi calcolati/denormalizzati
    subtotal: Decimal = Field(..., description="Totale imponibile")
    vat_amount: Decimal = Field(
        ...,
        description="Importo IVA calcolato",
        serialization_alias="vatAmount"
    )
    total: Decimal = Field(..., description="Totale fattura")
    # Regime fiscale
    vat_exemption: bool = Field(
        ...,
        description="Flag esenzione IVA",
        serialization_alias="vatExemption"
    )
    vat_exemption_code: Optional[str] = Field(
        None,
        description="Codice esenzione IVA",
        serialization_alias="vatExemptionCode"
    )
    split_payment: bool = Field(
        ...,
        description="Flag split payment (PA)",
        serialization_alias="splitPayment"
    )
    # Timestamps
    created_at: date = Field(..., description="Data/ora creazione")
    updated_at: date = Field(..., description="Data/ora ultimo aggiornamento")
    
    # Relazioni
    lines: list[InvoiceLineRead] = Field(
        default_factory=list,
        description="Righe della fattura"
    )
    payment_allocations: list[PaymentAllocationRead] = Field(
        default_factory=list,
        description="Allocazioni di pagamenti su questa fattura"
    )
    
    # -------------------------------------------------------------------
    # Computed Fields
    # -------------------------------------------------------------------
    @computed_field
    @property
    def paid_amount(self) -> Decimal:
        """Somma allocazioni ricevute da pagamenti."""
        return sum(a.amount for a in self.payment_allocations)
    
    @computed_field
    @property
    def remaining_amount(self) -> Decimal:
        """Importo residuo da incassare."""
        return self.total - self.paid_amount
    
    @computed_field
    @property
    def status(self) -> InvoiceStatus:
        """
        Stato calcolato in base ai pagamenti:
        - 'paid': totalmente pagata
        - 'partial': parzialmente pagata
        - 'unpaid': non pagata
        - 'overdue': scaduta e non pagata
        """
        from datetime import date as today
        
        if self.paid_amount >= self.total:
            return InvoiceStatus.PAID
        elif self.paid_amount > 0:
            return InvoiceStatus.PARTIAL
        elif today.today() > self.due_date:
            return InvoiceStatus.OVERDUE
        else:
            return InvoiceStatus.UNPAID
    
    @computed_field
    @property
    def is_overdue(self) -> bool:
        """True se la fattura è scaduta e non completamente pagata."""
        from datetime import date as today
        return today.today() > self.due_date and self.remaining_amount > 0
    
    model_config = ConfigDict(from_attributes=True)


class InvoiceList(BaseModel):
    """Schema per la lista paginata delle fatture."""
    
    items: list[InvoiceRead] = Field(
        default_factory=list,
        description="Lista delle fatture"
    )
    total: int = Field(
        ...,
        description="Numero totale di fatture",
        serialization_alias="totalItems"
    )
    page: int = Field(
        ...,
        description="Pagina corrente",
        serialization_alias="currentPage"
    )
    per_page: int = Field(
        ...,
        description="Elementi per pagina",
        serialization_alias="itemsPerPage"
    )
    total_pages: int = Field(
        ...,
        description="Numero totale di pagine",
        serialization_alias="totalPages"
    )
    
    model_config = ConfigDict(from_attributes=True)


# -------------------------------------------------------------------
# Schemas per Report
# -------------------------------------------------------------------

class RevenueReport(BaseModel):
    """Schema per il report degli incassi."""
    
    total_invoiced: Decimal = Field(
        ...,
        description="Somma totale delle fatture nel periodo",
        serialization_alias="totalInvoiced"
    )
    total_paid: Decimal = Field(
        ...,
        description="Somma totale dei pagamenti nel periodo",
        serialization_alias="totalPaid"
    )
    total_unpaid: Decimal = Field(
        ...,
        description="Totale residuo da incassare",
        serialization_alias="totalUnpaid"
    )
    invoices_count: int = Field(
        ...,
        description="Numero di fatture nel periodo",
        serialization_alias="invoicesCount"
    )
    payments_count: int = Field(
        ...,
        description="Numero di pagamenti nel periodo",
        serialization_alias="paymentsCount"
    )
    
    model_config = ConfigDict(from_attributes=True)


# -------------------------------------------------------------------
# Schemas per creazione fattura da ordine di lavoro
# -------------------------------------------------------------------

class CreateInvoiceFromWorkOrder(BaseModel):
    """Schema per la richiesta di creazione fattura da ordine di lavoro."""
    
    invoice_date: Optional[date] = Field(
        None,
        description="Data emissione fattura (default: oggi)",
        serialization_alias="invoiceDate"
    )
    due_date: Optional[date] = Field(
        None,
        description="Data scadenza pagamento (default: invoice_date + 30 giorni)",
        serialization_alias="dueDate"
    )
    customer_notes: Optional[str] = Field(
        None,
        description="Note per il cliente (stampate in fattura)",
        serialization_alias="customerNotes"
    )
    vat_rate: Decimal = Field(
        default=Decimal("22.00"),
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Aliquota IVA applicata (default 22% standard Italia)",
        serialization_alias="vatRate"
    )
    
    model_config = ConfigDict(from_attributes=True)
