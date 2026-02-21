"""
Modelli SQLAlchemy per gli Ordini di Lavoro
Progetto: Garage Manager (Gestionale Officina)

 Contiene:
- WorkOrder: Ordine di lavoro principale
- WorkOrderItem: Voci di lavoro (manodopera/interventi) associate all'ordine
"""


from __future__ import annotations
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, Uuid
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base
from app.models.mixins import TimestampMixin, UUIDMixin

# Import per type hinting relazioni (evita circular import)
if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.vehicle import Vehicle
    from app.models.part import PartUsage
    from app.models.invoice import Invoice
    from app.models.technician import Technician


# Gli stati sono definiti in app.schemas.work_order.WorkOrderStatus
# I tipi di voce sono definiti in app.schemas.work_order.ItemType


class WorkOrder(Base, UUIDMixin, TimestampMixin):
    """
    Modello per gli ordini di lavoro (work orders).
    
    Rappresenta un ordine di lavoro presso l'officina, associato al cliente e al veicolo.
    Include una macchina a stati per gestire il ciclo di vita dell'ordine.
    
    Attributes:
        id: UUID primary key, generato automaticamente
        client_id: UUID del cliente proprietario del veicolo
        vehicle_id: UUID del veicolo oggetto dell'intervento
        status: Stato corrente dell'ordine (draft, in_progress, waiting_parts, completed, invoiced, cancelled)
        problem_description: Descrizione del problema segnalato dal cliente
        diagnosis: Diagnosi del meccanico dopo ispezione
        km_in: Chilometraggio al momento dell'ingresso
        km_out: Chilometraggio alla consegna
        estimated_delivery: Data prevista consegna
        completed_at: Data/ora completamento ordine
        internal_notes: Note interne tra operatori
        created_at: Data/ora creazione record
        updated_at: Data/ora ultimo aggiornamento
        
    Relationships:
        client: Cliente proprietario
        vehicle: Veicolo oggetto dell'intervento
        items: Voci di lavoro (manodopera/interventi)
    
    States (State Machine):
        draft → in_progress → waiting_parts → completed → invoiced
                    ↓           ↓               ↓
                  cancelled   cancelled        -
    """

    __tablename__ = "work_orders"

    # ------------------------------------------------------------
    # Colonne Relazioni
    # ------------------------------------------------------------
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="UUID del cliente proprietario del veicolo",
    )

    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("vehicles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        doc="UUID del veicolo oggetto dell'intervento",
    )

    assigned_technician_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("technicians.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="UUID del tecnico assegnato",
    )

    # ------------------------------------------------------------
    # Colonne Stato e Dati
    # ------------------------------------------------------------
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
        doc="Stato corrente dell'ordine di lavoro",
    )

    problem_description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Descrizione del problema segnalato dal cliente",
    )

    diagnosis: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Diagnosi del meccanico dopo ispezione",
    )

    km_in: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Chilometraggio al momento dell'ingresso",
    )

    km_out: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Chilometraggio alla consegna",
    )

    estimated_delivery: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        doc="Data prevista consegna",
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Data/ora completamento ordine",
    )

    internal_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Note interne tra operatori",
    )

    # ------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------
    client: Mapped["Client"] = relationship(
        "Client",
        back_populates="work_orders",
        lazy="joined",
        doc="Cliente proprietario del veicolo",
    )

    assigned_technician: Mapped[Optional["Technician"]] = relationship(
        "Technician",
        back_populates="work_orders",
        lazy="joined",
        doc="Tecnico assegnato all'ordine",
    )

    vehicle: Mapped["Vehicle"] = relationship(
        "Vehicle",
        back_populates="work_orders",
        lazy="joined",
        doc="Veicolo oggetto dell'intervento",
    )

    items: Mapped[List["WorkOrderItem"]] = relationship(
        "WorkOrderItem",
        back_populates="work_order",
        cascade="all, delete-orphan",
        lazy="noload",
        doc="Voci di lavoro (manodopera/interventi) associate all'ordine",
    )

    part_usages: Mapped[List["PartUsage"]] = relationship(
        "PartUsage",
        back_populates="work_order",
        cascade="all, delete-orphan",
        lazy="noload",
        doc="Utilizzi ricambi associati all'ordine",
    )

    invoice: Mapped[Optional["Invoice"]] = relationship(
        "Invoice",
        back_populates="work_order",
        uselist=False,  # relazione 1:1
        lazy="selectin",
        doc="Fattura associata all'ordine",
    )

    # ------------------------------------------------------------
    # Indici e Vincoli
    # ------------------------------------------------------------
    __table_args__ = (
        # Indice su status (filtro più frequente)
        Index("ix_work_orders_status", "status"),
        # Indice composto per dashboard (status + data creazione)
        Index("ix_work_orders_status_created", "status", "created_at"),
        # Vincolo di check sullo stato
        CheckConstraint(
            "status IN ('draft', 'in_progress', 'waiting_parts', 'completed', 'invoiced', 'cancelled')",
            name="ck_work_orders_status",
        ),
        # Vincolo di check sui chilometri: km_out >= km_in (gestione NULL)
        CheckConstraint(
            "(km_out IS NULL OR km_in IS NULL OR km_out >= km_in)",
            name="ck_work_orders_km",
        ),
    )

    # ------------------------------------------------------------
    # Metodi
    # ------------------------------------------------------------
    def __repr__(self) -> str:
        """
        Rappresentazione stringa dell'oggetto WorkOrder.
        
        Returns:
            Stringa che identifica l'ordine di lavoro
        """
        return f"<WorkOrder(id={self.id}, status={self.status}, client_id={self.client_id})>"


class WorkOrderItem(Base, UUIDMixin, TimestampMixin):
    """
    Modello per le voci di lavoro (work order items).
    
    Rappresenta una singola voce di lavoro all'interno di un ordine,
    come manodopera (labor) o un intervento generico (service).
    
    Attributes:
        id: UUID primary key, generato automaticamente
        work_order_id: UUID dell'ordine di lavoro padre
        description: Descrizione del lavoro/intervento
        quantity: Quantità (ore per manodopera, pezzi per interventi)
        unit_price: Prezzo unitario (orario o per unità)
        item_type: Tipo di voce (labor = manodopera, service = intervento generico)
        created_at: Data/ora creazione record
        updated_at: Data/ora ultimo aggiornamento
        
    Relationships:
        work_order: Ordine di lavoro padre
    
    Properties:
        line_total: Totale riga (quantity * unit_price)
    """

    __tablename__ = "work_order_items"

    # ------------------------------------------------------------
    # Colonna Relazione
    # ------------------------------------------------------------
    work_order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("work_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="UUID dell'ordine di lavoro padre",
    )

    technician_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("technicians.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="UUID del tecnico assegnato alla voce",
    )

    # ------------------------------------------------------------
    # Colonne Dati
    # ------------------------------------------------------------
    description: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="Descrizione del lavoro/intervento",
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("1"),
        doc="Quantità (ore per manodopera, pezzi per interventi)",
    )

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0"),
        doc="Prezzo unitario (orario o per unità)",
    )

    item_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Tipo di voce: labor (manodopera) o service (intervento)",
    )

    # ------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------
    work_order: Mapped["WorkOrder"] = relationship(
        "WorkOrder",
        back_populates="items",
        doc="Ordine di lavoro padre",
    )

    technician: Mapped[Optional["Technician"]] = relationship(
        "Technician",
        back_populates="work_order_items",
        lazy="joined",
        doc="Tecnico assegnato alla voce",
    )

    # ------------------------------------------------------------
    # Indici e Vincoli
    # ------------------------------------------------------------
    __table_args__ = (
        # Vincolo di check sul tipo di voce
        CheckConstraint(
            "item_type IN ('labor', 'service')",
            name="ck_work_order_items_item_type",
        ),
    )

    # ------------------------------------------------------------
    # Hybrid Properties Calcolate
    # ------------------------------------------------------------
    @hybrid_property
    def line_total(self) -> Decimal:
        """
        Totale della riga (quantity * unit_price).
        
        Returns:
            Decimal: Quantità * Prezzo unitario
        """
        return self.quantity * self.unit_price

    @line_total.expression
    def line_total(cls) -> Numeric:
        """
        Espressione SQL per il totale della riga.
        Permette operazioni di query/aggregazione a livello di database.
        
        Returns:
            Numeric: Espressione quantity * unit_price
        """
        from sqlalchemy import cast

        return cast(cls.quantity * cls.unit_price, Numeric(10, 2))

    # ------------------------------------------------------------
    # Metodi
    # ------------------------------------------------------------
    def __repr__(self) -> str:
        """
        Rappresentazione stringa dell'oggetto WorkOrderItem.
        
        Returns:
            Stringa che identifica la voce di lavoro
        """
        return f"<WorkOrderItem(id={self.id}, type={self.item_type}, description={self.description[:30]}...)>"
