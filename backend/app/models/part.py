"""
Modelli SQLAlchemy per Ricambi e Magazzino
Progetto: Garage Manager (Gestionale Officina)

Contiene:
- Part: Anagrafica ricambi
- PartUsage: Utilizzo ricambi in ordini di lavoro
- StockMovement: Movimenti di magazzino
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, Numeric, String, Text, Uuid, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base
from app.models.mixins import TimestampMixin, UUIDMixin

# Import per type hinting relazioni (evita circular import)
if TYPE_CHECKING:
    from app.models.work_order import WorkOrder


class PartCategory(Base, UUIDMixin, TimestampMixin):
    """
    Modello per la classificazione in categorie dei ricambi.
    Supporta subcategorie annidate tramite self-referencing.
    """
    __tablename__ = "part_categories"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("part_categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    parent: Mapped[Optional["PartCategory"]] = relationship(
        "PartCategory", remote_side="PartCategory.id", back_populates="children"
    )
    children: Mapped[list["PartCategory"]] = relationship(
        "PartCategory", back_populates="parent", lazy="selectin"
    )
    parts: Mapped[list["Part"]] = relationship("Part", back_populates="category", lazy="noload")

    def __repr__(self) -> str:
        return f"PartCategory(name={self.name!r}, parent_id={self.parent_id})"


class Part(Base, UUIDMixin, TimestampMixin):
    """
    Modello per l'anagrafica ricambi.
    
    Rappresenta un ricambio/serva disponibile in magazzino.
    
    Attributes:
        id: UUID primary key, generato automaticamente
        code: Codice identificativo univoco del ricambio
        description: Descrizione del ricambio
        brand: Marca/fornitore (opzionale)
        compatible_models: Modelli di veicolo compatibili (testo libero)
        purchase_price: Prezzo di acquisto
        sale_price: Prezzo di vendita
        stock_quantity: Giacenza attuale
        min_stock_level: Livello minimo giacenza per alert
        location: Posizione fisica in magazzino
        is_active: Indica se il ricambio è attivo/disponibile
        created_at: Data/ora creazione record
        updated_at: Data/ora ultimo aggiornamento
        
    Relationships:
        usages: Utilizzi del ricambio in ordini di lavoro
        stock_movements: Storico movimenti di magazzino
    
    Properties:
        is_below_minimum: True se stock < min_stock_level
    """

    __tablename__ = "parts"

    # ------------------------------------------------------------
    # Colonne Relazione Categoria
    # ------------------------------------------------------------
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("part_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="UUID della categoria",
    )

    # ------------------------------------------------------------
    # Colonne
    # ------------------------------------------------------------
    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        doc="Codice identificativo univoco del ricambio",
    )

    description: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Descrizione del ricambio",
    )

    brand: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        doc="Marca/fornitore del ricambio",
    )

    compatible_models: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Modelli di veicolo compatibili (testo libero)",
    )

    purchase_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        default=Decimal("0"),
        doc="Prezzo di acquisto",
    )

    sale_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0"),
        doc="Prezzo di vendita",
    )

    # FIX 5: Aggiunto campo vat_rate per gestione IVA per ricambio
    vat_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("22.00"),
        doc="Aliquota IVA del ricambio (default 22%)",
    )

    stock_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Giacenza attuale",
    )

    min_stock_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Livello minimo giacenza per alert",
    )

    location: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="Posizione fisica in magazzino",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        doc="Indica se il ricambio è attivo/disponibile",
    )

    unit_of_measure: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="pz",
        doc="Unità di misura (pz, lt, kg, mt, ml, gr)",
    )

    # ------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------
    category: Mapped[Optional["PartCategory"]] = relationship(
        "PartCategory",
        back_populates="parts",
        lazy="joined",
        doc="Categoria del ricambio",
    )

    usages: Mapped[List["PartUsage"]] = relationship(
        "PartUsage",
        back_populates="part",
        lazy="noload",
        doc="Utilizzi del ricambio in ordini di lavoro",
    )

    stock_movements: Mapped[List["StockMovement"]] = relationship(
        "StockMovement",
        back_populates="part",
        lazy="noload",
        doc="Storico movimenti di magazzino",
    )

    # ------------------------------------------------------------
    # Indici e Vincoli
    # ------------------------------------------------------------
    __table_args__ = (
        # Indice composto per ricerca magazzino
        Index("ix_parts_active_stock", "is_active", "stock_quantity"),
    )

    # ------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------
    @property
    def is_below_minimum(self) -> bool:
        """True se la giacenza è sotto il livello minimo."""
        return self.stock_quantity < self.min_stock_level

    # ------------------------------------------------------------
    # Magic Methods
    # ------------------------------------------------------------
    def __repr__(self) -> str:
        return f"Part(code={self.code!r}, description={self.description!r})"


class PartUsage(Base, UUIDMixin, TimestampMixin):
    """
    Modello per l'utilizzo di ricambi negli ordini di lavoro.
    
    Rappresenta un ricambio utilizzato in un ordine di lavoro specifico.
    
    Attributes:
        id: UUID primary key, generato automaticamente
        work_order_id: UUID dell'ordine di lavoro
        part_id: UUID del ricambio utilizzato
        quantity: Quantità utilizzata
        unit_price: Prezzo unitario al momento dell'utilizzo
        created_at: Data/ora creazione record
        updated_at: Data/ora ultimo aggiornamento
        
    Relationships:
        work_order: Ordine di lavoro associato
        part: Ricambio utilizzato
    
    Properties:
        line_total: Totale riga (quantity * unit_price)
    """

    __tablename__ = "part_usages"

    # ------------------------------------------------------------
    # Colonne
    # ------------------------------------------------------------
    work_order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("work_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="UUID dell'ordine di lavoro",
    )

    part_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("parts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        doc="UUID del ricambio utilizzato",
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        doc="Quantità utilizzata",
    )

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        doc="Prezzo unitario al momento dell'utilizzo",
    )

    unit_of_measure: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="pz",
        doc="Unità di misura al momento dell'utilizzo",
    )

    # ------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------
    work_order: Mapped["WorkOrder"] = relationship(
        "WorkOrder",
        back_populates="part_usages",
        lazy="noload",
        doc="Ordine di lavoro associato",
    )

    part: Mapped["Part"] = relationship(
        "Part",
        back_populates="usages",
        lazy="noload",
        doc="Ricambio utilizzato",
    )

    # ------------------------------------------------------------
    # Indici e Vincoli
    # ------------------------------------------------------------
    __table_args__ = (
        # Vincolo di check sulla quantità
        CheckConstraint(
            "quantity > 0",
            name="ck_part_usages_quantity",
        ),
    )

    # ------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------
    @property
    def line_total(self) -> Decimal:
        """Totale riga: quantity * unit_price."""
        return self.quantity * self.unit_price

    # ------------------------------------------------------------
    # Magic Methods
    # ------------------------------------------------------------
    def __repr__(self) -> str:
        return f"PartUsage(work_order_id={self.work_order_id}, part_id={self.part_id}, quantity={self.quantity})"


class StockMovement(Base, UUIDMixin, TimestampMixin):
    """
    Modello per i movimenti di magazzino.
    
    Rappresenta un movimento di stock (carico, scarico, aggiustamento).
    
    Attributes:
        id: UUID primary key, generato automaticamente
        part_id: UUID del ricambio
        movement_type: Tipo di movimento (in, out, adjustment)
        quantity: Quantità del movimento (positiva o negativa)
        reference: Riferimento (es. numero ordine, nota)
        notes: Note aggiuntive
        created_at: Data/ora creazione record
        updated_at: Data/ora ultimo aggiornamento
        
    Relationships:
        part: Ricambio associato al movimento
    """

    __tablename__ = "stock_movements"

    # ------------------------------------------------------------
    # Colonne
    # ------------------------------------------------------------
    part_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("parts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        doc="UUID del ricambio",
    )

    movement_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        doc="Tipo di movimento: in, out, adjustment",
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Quantità del movimento (positiva o negativa)",
    )

    reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Riferimento (es. numero ordine, nota)",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Note aggiuntive",
    )

    # ------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------
    part: Mapped["Part"] = relationship(
        "Part",
        back_populates="stock_movements",
        lazy="noload",
        doc="Ricambio associato al movimento",
    )

    # ------------------------------------------------------------
    # Indici e Vincoli
    # ------------------------------------------------------------
    __table_args__ = (
        # Vincolo di check sul tipo di movimento
        CheckConstraint(
            "movement_type IN ('in', 'out', 'adjustment')",
            name="ck_stock_movements_type",
        ),
    )

    # ------------------------------------------------------------
    # Magic Methods
    # ------------------------------------------------------------
    def __repr__(self) -> str:
        return f"StockMovement(part_id={self.part_id}, type={self.movement_type}, quantity={self.quantity})"
