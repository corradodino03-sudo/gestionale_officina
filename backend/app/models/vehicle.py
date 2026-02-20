"""
Modello SQLAlchemy per l'entità Vehicle
Progetto: Garage Manager (Gestionale Officina)

Rappresenta i veicoli associati ai clienti.
"""

import uuid
from typing import TYPE_CHECKING, List

from sqlalchemy import ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base
from app.models.mixins import TimestampMixin, UUIDMixin, SoftDeleteMixin

# Import per type hinting relazioni (evita circular import)
if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.work_order import WorkOrder


class Vehicle(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """
    Modello per i veicoli associati ai clienti.
    
    Rappresenta l'anagrafica dei veicoli con tutti i dati tecnici.
    Un veicolo appartiene a un cliente e può avere più ordini di lavoro.
    
    Attributes:
        id: UUID primary key, generato automaticamente
        client_id: UUID del cliente proprietario (obbligatorio)
        plate: Targa del veicolo (obbligatoria, univoca)
        brand: Marca del veicolo (obbligatoria)
        model: Modello del veicolo (obbligatorio)
        year: Anno di immatricolazione (opzionale)
        current_km: Chilometraggio attuale (default 0)
        vin: Numero telaio/VIN (opzionale, univoco)
        fuel_type: Tipo di carburante (opzionale)
        notes: Note aggiuntive (opzionale)
        created_at: Data/ora creazione record
        updated_at: Data/ora ultimo aggiornamento
        
    Relationships:
        client: Cliente proprietario del veicolo
        work_orders: Ordini di lavoro associati al veicolo
    """

    __tablename__ = "vehicles"

    # ------------------------------------------------------------
    # Colonne Relazione Cliente
    # ------------------------------------------------------------
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        doc="UUID del cliente proprietario",
    )

    # ------------------------------------------------------------
    # Colonne Dati Veicolo
    # ------------------------------------------------------------
    plate: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        unique=True,
        doc="Targa del veicolo",
    )

    brand: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Marca del veicolo",
    )

    model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Modello del veicolo",
    )

    # ------------------------------------------------------------
    # Colonne Dati Tecnici Opzionali
    # ------------------------------------------------------------
    year: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Anno di immatricolazione",
    )

    current_km: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Chilometraggio attuale",
    )

    vin: Mapped[str | None] = mapped_column(
        String(17),
        unique=True,
        nullable=True,
        doc="Numero telaio (Vehicle Identification Number)",
    )

    fuel_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="Tipo di carburante",
    )

    # ------------------------------------------------------------
    # Colonne Extra
    # ------------------------------------------------------------
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Note aggiuntive sul veicolo",
    )

    # ------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------
    client: Mapped["Client"] = relationship(
        "Client",
        back_populates="vehicles",
        lazy="joined",
        doc="Cliente proprietario del veicolo",
    )

    work_orders: Mapped[List["WorkOrder"]] = relationship(
        "WorkOrder",
        back_populates="vehicle",
        cascade="all, delete-orphan",
        lazy="noload",
        doc="Ordini di lavoro associati al veicolo",
    )

    # ------------------------------------------------------------
    # Indici
    # ------------------------------------------------------------
    __table_args__ = (
        # Indice composto per ricerca veloce "veicoli di un cliente"
        Index("ix_vehicles_client_plate", "client_id", "plate"),
        # Indice sulla targa (già unique, ma esplicita per query)
        Index("ix_vehicles_plate", "plate"),
        # Indice sul VIN se presente
        Index("ix_vehicles_vin", "vin"),
    )

    # ------------------------------------------------------------
    # Metodi
    # ------------------------------------------------------------
    def __repr__(self) -> str:
        """
        Rappresentazione stringa dell'oggetto Vehicle.
        
        Returns:
            Stringa che identifica il veicolo (targa, marca, modello)
        """
        return f"<Vehicle(id={self.id}, plate={self.plate}, brand={self.brand}, model={self.model})>"

    @property
    def display_name(self) -> str:
        """
        Nome visualizzato del veicolo.
        
        Returns:
            Stringa formattata: "Marca Modello (Targa)"
        """
        return f"{self.brand} {self.model} ({self.plate})"
