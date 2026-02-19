"""
Modello SQLAlchemy per l'entità Client
Progetto: Garage Manager (Gestionale Officina)

Rappresenta l'anagrafica dei clienti (persone fisiche e giuridiche).
"""

import uuid
from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base
from app.models.mixins import TimestampMixin

# Import per type hinting relazioni (evita circular import)
if TYPE_CHECKING:
    from app.models.vehicle import Vehicle
    from app.models.work_order import WorkOrder


class Client(Base, TimestampMixin):
    """
    Modello per l'anagrafica clienti.
    
    Gestisce sia persone fisiche che giuridiche (aziende).
    Un cliente può avere più veicoli e più ordini di lavoro associati.
    
    Attributes:
        id: UUID primary key, generato automaticamente
        name: Nome o ragione sociale (obbligatorio)
        surname: Cognome (opzionale, per persone fisiche)
        is_company: Indica se è una persona giuridica
        tax_id: Codice Fiscale (16 char) o Partita IVA (11 cifre)
        address: Indirizzo completo
        city: Città
        zip_code: CAP
        province: Sigla provincia (2 caratteri)
        phone: Numero di telefono
        email: Indirizzo email
        notes: Note aggiuntive
        created_at: Data/ora creazione record
        updated_at: Data/ora ultimo aggiornamento
        
    Relationships:
        vehicles: Veicoli associati al cliente
        work_orders: Ordini di lavoro associati al cliente
    """

    __tablename__ = "clients"

    # ------------------------------------------------------------
    # Colonne Primary Key
    # ------------------------------------------------------------
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        doc="UUID primary key",
    )

    # ------------------------------------------------------------
    # Colonne Dati Anagrafici
    # ------------------------------------------------------------
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Nome o ragione sociale",
    )

    surname: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Cognome (per persone fisiche)",
    )

    is_company: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="Indica se è una persona giuridica",
    )

    tax_id: Mapped[str | None] = mapped_column(
        String(16),
        unique=True,
        nullable=True,
        doc="Codice Fiscale (16 char) o Partita IVA (11 cifre)",
    )

    # ------------------------------------------------------------
    # Colonne Indirizzo
    # ------------------------------------------------------------
    address: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Indirizzo completo",
    )

    city: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Città",
    )

    zip_code: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        doc="CAP",
    )

    province: Mapped[str | None] = mapped_column(
        String(2),
        nullable=True,
        doc="Sigla provincia (2 caratteri)",
    )

    # ------------------------------------------------------------
    # Colonne Contatto
    # ------------------------------------------------------------
    phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        doc="Numero di telefono",
    )

    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Indirizzo email",
    )

    # ------------------------------------------------------------
    # Colonne Extra
    # ------------------------------------------------------------
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Note aggiuntive sul cliente",
    )

    # ------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------
    vehicles: Mapped[List["Vehicle"]] = relationship(
        "Vehicle",
        back_populates="client",
        lazy="selectin",
        doc="Veicoli associati al cliente",
    )

    work_orders: Mapped[List["WorkOrder"]] = relationship(
        "WorkOrder",
        back_populates="client",
        lazy="selectin",
        doc="Ordini di lavoro associati al cliente",
    )

    # ------------------------------------------------------------
    # Indici
    # ------------------------------------------------------------
    __table_args__ = (
        Index("ix_clients_name_surname", "name", "surname"),
        Index("ix_clients_tax_id", "tax_id"),
    )

    # ------------------------------------------------------------
    # Metodi
    # ------------------------------------------------------------
    def __repr__(self) -> str:
        """
        Rappresentazione stringa dell'oggetto Client.
        
        Returns:
            Stringa che identifica il cliente
        """
        if self.is_company:
            return f"<Client(id={self.id}, company={self.name})>"
        return f"<Client(id={self.id}, name={self.name} {self.surname})>"
