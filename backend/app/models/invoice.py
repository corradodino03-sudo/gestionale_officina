"""
Modelli SQLAlchemy per la Fatturazione
Progetto: Garage Manager (Gestionale Officina)

Contiene:
- Invoice: Fattura principale
- InvoiceLine: Righe della fattura (manodopera, servizi, ricambi)
- Payment: Pagamenti registrati sulla fattura
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING, List

from sqlalchemy import (
    CheckConstraint,
    Date,
    Float,
    Index,
    Numeric,
    String,
    Text,
    Uuid,
    Boolean,
    ForeignKey,
    Integer,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base
from app.models.mixins import TimestampMixin, UUIDMixin

# Import per type hinting relazioni (evita circular import)
if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.work_order import WorkOrder


class Invoice(Base, UUIDMixin, TimestampMixin):
    """
    Modello per le fatture.
    
    Una fattura è generata da un ordine di lavoro COMPLETATO e contiene
    tutte le informazioni necessarie per la fatturazione al cliente.
    
    Attributes:
        id: UUID primary key, generato automaticamente
        work_order_id: UUID dell'ordine di lavoro (1:1)
        client_id: UUID del cliente (denormalizzato per velocità query)
        invoice_number: Numero progressivo annuale (formato: YYYY/NNNN)
        invoice_date: Data emissione fattura
        due_date: Data scadenza pagamento
        subtotal: Totale imponibile (senza IVA)
        vat_rate: Aliquota IVA applicata (default 22%)
        vat_amount: Importo IVA calcolato
        total: Totale fattura (subtotal + vat_amount)
        vat_exemption: Flag esenzione IVA
        vat_exemption_code: Codice esenzione IVA
        split_payment: Flag split payment (PA)
        notes: Note interne
        customer_notes: Note per il cliente (stampate in fattura)
        stamp_duty_applied: Flag marca da bollo
        stamp_duty_amount: Importo marca da bollo
        payment_iban: IBAN per bonifico
        payment_reference: Riferimento pagamento
        created_at: Data/ora creazione record
        updated_at: Data/ora ultimo aggiornamento
        
    Relationships:
        work_order: Ordine di lavoro associato
        client: Cliente associato
        lines: Righe della fattura
        payments: Pagamenti registrati
    """

    __tablename__ = "invoices"

    # ------------------------------------------------------------
    # Colonne Relazioni
    # ------------------------------------------------------------
    work_order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("work_orders.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        doc="UUID dell'ordine di lavoro (relazione 1:1)",
    )

    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("clients.id", ondelete="RESTRICT"),
        nullable=False,
        doc="UUID del cliente proprietario del veicolo (denormalizzato per velocità query)",
    )

    # FEAT 3: Fattura a terzi
    bill_to_client_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("clients.id", ondelete="SET NULL"),
        nullable=True,
        doc="UUID del cliente a cui è intestata la fattura (se diverso dal proprietario)",
    )
    bill_to_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bill_to_tax_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bill_to_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    claim_number: Mapped[str | None] = mapped_column(String(100), nullable=True)


    # ------------------------------------------------------------
    # Colonne Identificazione
    # ------------------------------------------------------------
    invoice_number: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        unique=True,
        doc="Numero fattura progressivo annuale (formato: YYYY/NNNN)",
    )

    invoice_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        doc="Data emissione fattura",
    )

    due_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        doc="Data scadenza pagamento",
    )

    # ------------------------------------------------------------
    # Colonne Importi
    # ------------------------------------------------------------
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        doc="Totale imponibile (manodopera + ricambi + servizi)",
    )

    vat_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("22.00"),
        doc="Aliquota IVA applicata (default 22%)",
    )

    vat_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        doc="Importo IVA calcolato",
    )

    total: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        doc="Totale fattura (subtotal + vat_amount + stamp_duty_amount)",
    )

    # ------------------------------------------------------------
    # Colonne Marca da Bollo (FEAT 3)
    # ------------------------------------------------------------
    stamp_duty_applied: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Flag marca da bollo applicata",
    )

    stamp_duty_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        doc="Importo marca da bollo",
    )

    # ------------------------------------------------------------
    # Colonne Pagamento (FEAT 2)
    # ------------------------------------------------------------
    payment_iban: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="IBAN per pagamenti con bonifico",
    )

    payment_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Riferimento pagamento (es. numero fattura da riportare in causale)",
    )

    # ------------------------------------------------------------
    # Colonne Regime Fiscale
    # ------------------------------------------------------------
    vat_exemption: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Flag esenzione IVA",
    )

    vat_exemption_code: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        doc="Codice natura esenzione IVA",
    )

    split_payment: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Flag split payment (PA - IVA versata direttamente dall'ente)",
    )

    # ------------------------------------------------------------
    # Colonne Note
    # ------------------------------------------------------------
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Note interne (non stampate in fattura)",
    )

    customer_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Note per il cliente (stampate in fattura)",
    )

    # ------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------
    work_order: Mapped["WorkOrder"] = relationship(
        "WorkOrder",
        back_populates="invoice",
        lazy="selectin",
        doc="Ordine di lavoro associato",
    )

    client: Mapped["Client"] = relationship(
        "Client",
        back_populates="invoices",
        lazy="selectin",
        foreign_keys="[Invoice.client_id]",
        doc="Cliente associato",
    )

    lines: Mapped[List["InvoiceLine"]] = relationship(
        "InvoiceLine",
        back_populates="invoice",
        cascade="all, delete-orphan",
        lazy="selectin",
        doc="Righe della fattura",
    )

    # Allocazioni ricevute (pagamenti applicati a questa fattura)
    payment_allocations: Mapped[List["PaymentAllocation"]] = relationship(
        "PaymentAllocation",
        back_populates="invoice",
        cascade="all, delete-orphan",
        lazy="selectin",
        doc="Allocazioni di pagamenti su questa fattura",
    )

    # Note di credito
    credit_notes: Mapped[List["CreditNote"]] = relationship(
        "CreditNote",
        back_populates="invoice",
        cascade="all, delete-orphan",
        lazy="selectin",
        doc="Note di credito che stornano questa fattura",
    )

    # ------------------------------------------------------------
    # Properties Calcolate
    # ------------------------------------------------------------
    @property
    def paid_amount(self) -> Decimal:
        """Somma degli importi allocati a questa fattura."""
        return sum((a.amount for a in self.payment_allocations), Decimal("0"))

    @property
    def remaining_amount(self) -> Decimal:
        """Importo residuo da incassare."""
        return self.total - self.paid_amount

    @property
    def status(self) -> str:
        """
        Stato calcolato in base ai pagamenti:
        - 'credited': stornata da nota di credito
        - 'paid': totalmente pagata
        - 'overdue': scaduta e non pagata
        - 'partial': parzialmente pagata
        - 'unpaid': non pagata
        """
        # Controlla note di credito
        if getattr(self, "credit_notes", None) and len(self.credit_notes) > 0:
            return "credited"

        if self.paid_amount >= self.total:
            return "paid"
        elif date.today() > self.due_date and self.remaining_amount > 0:
            return "overdue"
        elif self.paid_amount > 0:
            return "partial"
        else:
            return "unpaid"

    @property
    def is_overdue(self) -> bool:
        """True se la fattura è scaduta e non completamente pagata."""
        return date.today() > self.due_date and self.remaining_amount > 0

    # ------------------------------------------------------------
    # Indici e Vincoli
    # ------------------------------------------------------------
    __table_args__ = (
        # Indice su client_id per query per cliente
        Index("ix_invoices_client_id", "client_id"),
        # Indice su invoice_date per ricerca per periodo
        Index("ix_invoices_invoice_date", "invoice_date"),
        # Indice su due_date per scadenze
        Index("ix_invoices_due_date", "due_date"),
        # Indice composto per ricerca veloce
        Index("ix_invoices_date_number", "invoice_date", "invoice_number"),
        # Vincoli di check sugli importi
        CheckConstraint("subtotal >= 0", name="ck_invoices_subtotal_positive"),
        CheckConstraint("vat_rate >= 0", name="ck_invoices_vat_rate_positive"),
        CheckConstraint("vat_amount >= 0", name="ck_invoices_vat_amount_positive"),
        CheckConstraint("total >= 0", name="ck_invoices_total_positive"),
    )

    # ------------------------------------------------------------
    # Metodi
    # ------------------------------------------------------------
    def __repr__(self) -> str:
        """
        Rappresentazione stringa dell'oggetto Invoice.
        
        Returns:
            Stringa che identifica la fattura
        """
        return f"<Invoice(id={self.id}, number={self.invoice_number}, total={self.total})>"


class InvoiceLine(Base, UUIDMixin, TimestampMixin):
    """
    Modello per le righe della fattura.
    
    Rappresenta una singola riga nella fattura, che può essere:
    - labor: manodopera
    - service: servizio/intervento
    - part: ricambio
    
    Attributes:
        id: UUID primary key, generato automaticamente
        invoice_id: UUID della fattura padre
        line_type: Tipo riga (labor, service, part)
        description: Descrizione della riga
        quantity: Quantità
        unit_price: Prezzo unitario
        vat_rate: Aliquota IVA specifica della riga
        line_number: Numero progressivo riga nella fattura
        created_at: Data/ora creazione record
        updated_at: Data/ora ultimo aggiornamento
        
    Relationships:
        invoice: Fattura padre
    """

    __tablename__ = "invoice_lines"

    # ------------------------------------------------------------
    # Colonna Relazione
    # ------------------------------------------------------------
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="UUID della fattura padre",
    )

    # ------------------------------------------------------------
    # Colonne Dati
    # ------------------------------------------------------------
    line_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Tipo riga: labor (manodopera), service (servizio), part (ricambio)",
    )

    description: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="Descrizione della riga",
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("1"),
        doc="Quantità",
    )

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        doc="Prezzo unitario",
    )

    # ------------------------------------------------------------
    # Colonne Sconto (FEAT 3)
    # ------------------------------------------------------------
    discount_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        doc="Percentuale di sconto applicata alla riga (0-100)",
    )

    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0"),
        doc="Importo sconto calcolato",
    )

    vat_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        doc="Aliquota IVA specifica della riga",
    )

    line_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Numero progressivo riga nella fattura",
    )

    # ------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------
    invoice: Mapped["Invoice"] = relationship(
        "Invoice",
        back_populates="lines",
        doc="Fattura padre",
    )

    # ------------------------------------------------------------
    # Properties Calcolate
    # ------------------------------------------------------------
    @property
    def subtotal(self) -> Decimal:
        """
        Imponibile riga (senza IVA), TENENDO CONTO DELLO SCONTO.
        
        Formula: (quantity * unit_price) - discount_amount
        """
        gross = self.quantity * self.unit_price
        return (gross - self.discount_amount).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    @property
    def vat_amount(self) -> Decimal:
        """
        Importo IVA riga.
        
        L'IVA si applica sull'imponibile (già scontato).
        """
        result = (self.subtotal * self.vat_rate) / Decimal("100")
        return result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def total(self) -> Decimal:
        """Totale riga (con IVA)."""
        return (self.subtotal + self.vat_amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # ------------------------------------------------------------
    # Indici e Vincoli
    # ------------------------------------------------------------
    __table_args__ = (
        # Indice composto per ordinamento
        Index("ix_invoice_lines_invoice_number", "invoice_id", "line_number"),
        # Vincolo di check sul tipo di riga
        CheckConstraint(
            "line_type IN ('labor', 'service', 'part')",
            name="ck_invoice_lines_line_type",
        ),
        # Vincoli di check sugli importi
        CheckConstraint("quantity > 0", name="ck_invoice_lines_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_invoice_lines_unit_price_positive"),
        # Vincolo sconto (FEAT 3)
        CheckConstraint(
            "discount_percent >= 0 AND discount_percent <= 100",
            name="ck_invoice_lines_discount_percent",
        ),
    )

    # ------------------------------------------------------------
    # Metodi
    # ------------------------------------------------------------
    def __repr__(self) -> str:
        """
        Rappresentazione stringa dell'oggetto InvoiceLine.
        
        Returns:
            Stringa che identifica la riga fattura
        """
        return f"<InvoiceLine(id={self.id}, type={self.line_type}, description={self.description[:30]}...)>"


class PaymentAllocation(Base, UUIDMixin, TimestampMixin):
    """
    Allocazione di una quota di pagamento su una fattura specifica.
    
    Esempio:
        Pagamento P1 di €1500 può essere allocato così:
        - €900 → Fattura A (PaymentAllocation)
        - €600 → Fattura B (PaymentAllocation)
    
    Attributes:
        id: UUID primary key, generato automaticamente
        payment_id: UUID del pagamento sorgente
        invoice_id: UUID della fattura destinazione
        amount: Importo allocato a questa fattura
        created_at: Data/ora creazione record
        updated_at: Data/ora ultimo aggiornamento
        
    Relationships:
        payment: Pagamento sorgente
        invoice: Fattura destinazione
    """

    __tablename__ = "payment_allocations"

    # ------------------------------------------------------------
    # Colonne Relazione
    # ------------------------------------------------------------
    payment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("payments.id", ondelete="CASCADE"),
        nullable=False,
        doc="UUID del pagamento sorgente",
    )

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("invoices.id", ondelete="RESTRICT"),
        nullable=False,
        doc="UUID della fattura destinazione",
    )

    # ------------------------------------------------------------
    # Colonne Dati
    # ------------------------------------------------------------
    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        doc="Importo allocato a questa fattura",
    )

    # ------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------
    payment: Mapped["Payment"] = relationship(
        "Payment",
        back_populates="allocations",
        doc="Pagamento sorgente",
    )

    invoice: Mapped["Invoice"] = relationship(
        "Invoice",
        back_populates="payment_allocations",
        doc="Fattura destinazione",
    )

    # ------------------------------------------------------------
    # Indici e Vincoli
    # ------------------------------------------------------------
    __table_args__ = (
        # Impedisce allocazioni duplicate stesso payment+invoice
        Index("idx_payment_invoice_unique", "payment_id", "invoice_id", unique=True),
        # Indice per query veloci
        Index("idx_allocation_invoice", "invoice_id"),
        # Vincolo: amount > 0
        CheckConstraint("amount > 0", name="check_allocation_amount_positive"),
    )

    # ------------------------------------------------------------
    # Metodi
    # ------------------------------------------------------------
    def __repr__(self) -> str:
        """
        Rappresentazione stringa dell'oggetto PaymentAllocation.
        
        Returns:
            Stringa che identifica l'allocazione
        """
        return f"<PaymentAllocation(payment={self.payment_id}, invoice={self.invoice_id}, amount={self.amount})>"


class Payment(Base, UUIDMixin, TimestampMixin):
    """
    Modello per i pagamenti generici del cliente.
    
    Un pagamento è ora generico e non più legato a una fattura specifica.
    Viene allocato su una o più fatture tramite PaymentAllocation.
    
    Attributes:
        id: UUID primary key, generato automaticamente
        client_id: UUID del cliente che ha effettuato il pagamento
        amount: Importo totale del pagamento
        payment_date: Data del pagamento
        payment_method: Metodo di pagamento (cash, pos, bank_transfer, check, other)
        reference: Riferimento (numero assegno, CRO bonifico, etc.)
        notes: Note aggiuntive
        created_at: Data/ora creazione record
        updated_at: Data/ora ultimo aggiornamento
        
    Relationships:
        client: Cliente che ha effettuato il pagamento
        allocations: Lista delle allocazioni su fatture
    """

    __tablename__ = "payments"

    # ------------------------------------------------------------
    # Colonna Relazione - Cliente
    # ------------------------------------------------------------
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("clients.id", ondelete="RESTRICT"),
        nullable=False,
        doc="UUID del cliente che ha effettuato il pagamento",
    )

    # ------------------------------------------------------------
    # Colonne Dati
    # ------------------------------------------------------------
    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        doc="Importo totale del pagamento",
    )

    payment_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        doc="Data del pagamento",
    )

    payment_method: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Metodo di pagamento",
    )

    reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Riferimento (numero assegno, CRO bonifico, etc.)",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Note aggiuntive sul pagamento",
    )

    # ------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------
    client: Mapped["Client"] = relationship(
        "Client",
        back_populates="payments",
        lazy="selectin",
        doc="Cliente che ha effettuato il pagamento",
    )

    allocations: Mapped[List["PaymentAllocation"]] = relationship(
        "PaymentAllocation",
        back_populates="payment",
        cascade="all, delete-orphan",
        lazy="selectin",
        doc="Allocazioni su fatture",
    )

    # ------------------------------------------------------------
    # Properties Calcolate
    # ------------------------------------------------------------
    @property
    def allocated_amount(self) -> Decimal:
        """Somma degli importi allocati alle fatture."""
        return sum((a.amount for a in self.allocations), Decimal("0"))

    @property
    def unallocated_amount(self) -> Decimal:
        """Importo del pagamento non ancora allocato."""
        return self.amount - self.allocated_amount

    @property
    def is_fully_allocated(self) -> bool:
        """True se tutto il pagamento è stato allocato."""
        return self.unallocated_amount == Decimal("0")

    # ------------------------------------------------------------
    # Indici e Vincoli
    # ------------------------------------------------------------
    __table_args__ = (
        # Indice su client_id
        Index("ix_payments_client_id", "client_id"),
        # Indice su payment_date per ricerca per periodo
        Index("ix_payments_payment_date", "payment_date"),
        # Vincolo di check: amount > 0
        CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
        # Vincolo di check sul metodo di pagamento
        CheckConstraint(
            "payment_method IN ('cash', 'pos', 'bank_transfer', 'check', 'other')",
            name="ck_payments_payment_method",
        ),
    )

    # ------------------------------------------------------------
    # Metodi
    # ------------------------------------------------------------
    def __repr__(self) -> str:
        """
        Rappresentazione stringa dell'oggetto Payment.
        
        Returns:
            Stringa che identifica il pagamento
        """
        return f"<Payment(id={self.id}, amount={self.amount}, method={self.payment_method})>"


class CreditNote(Base, UUIDMixin, TimestampMixin):
    """
    Modello per le note di credito.
    Rappresenta uno storno parziale o totale di una fattura.
    """
    __tablename__ = "credit_notes"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=False
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False
    )

    credit_note_number: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    credit_note_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    reason: Mapped[str] = mapped_column(String(255), nullable=False)

    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    
    stamp_duty_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )

    # Relazioni
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="credit_notes")
    client: Mapped["Client"] = relationship("Client")
    lines: Mapped[List["CreditNoteLine"]] = relationship("CreditNoteLine", back_populates="credit_note", cascade="all, delete-orphan")


class CreditNoteLine(Base, UUIDMixin, TimestampMixin):
    """Righe di una nota di credito."""
    __tablename__ = "credit_note_lines"

    credit_note_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("credit_notes.id", ondelete="CASCADE"), nullable=False
    )

    line_type: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relazioni
    credit_note: Mapped["CreditNote"] = relationship("CreditNote", back_populates="lines")


class Deposit(Base, UUIDMixin, TimestampMixin):
    """
    Modello per le caparre/acconti versati dal cliente.
    """
    __tablename__ = "deposits"

    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False
    )
    work_order_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("work_orders.id", ondelete="SET NULL"), nullable=True
    )
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=True
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(20), nullable=False)
    deposit_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", doc="pending, applied, refunded"
    )

    # Relazioni
    client: Mapped["Client"] = relationship("Client")
    work_order: Mapped["WorkOrder"] = relationship("WorkOrder")
    invoice: Mapped["Invoice"] = relationship("Invoice")
