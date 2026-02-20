"""
Modello SQLAlchemy per l'entità Client
Progetto: Garage Manager (Gestionale Officina)

Rappresenta l'anagrafica dei clienti (persone fisiche e giuridiche).
"""

from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base
from app.models.mixins import TimestampMixin, UUIDMixin, SoftDeleteMixin

# Import per type hinting relazioni (evita circular import)
if TYPE_CHECKING:
    from app.models.vehicle import Vehicle
    from app.models.work_order import WorkOrder
    from app.models.invoice import Invoice, Payment


class Client(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
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
    # Colonne Dati Esteri
    # ------------------------------------------------------------
    country_code: Mapped[str | None] = mapped_column(
        String(2),
        nullable=True,
        default="IT",
        doc="Codice ISO 3166-1 alpha-2 del paese",
    )

    is_foreign: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="True se cliente estero, attiva logiche esenzione IVA",
    )

    # ------------------------------------------------------------
    # Colonne Fatturazione Elettronica (SDI)
    # ------------------------------------------------------------
    sdi_code: Mapped[str | None] = mapped_column(
        String(7),
        nullable=True,
        doc="Codice Destinatario SDI (7 caratteri). '0000000' per PEC, 'XXXXXXX' per esteri",
    )

    pec: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="PEC per fatturazione elettronica",
    )

    # ------------------------------------------------------------
    # Colonne Regime Fiscale
    # ------------------------------------------------------------
    vat_regime: Mapped[str | None] = mapped_column(
        String(5),
        nullable=True,
        default="RF01",
        doc="Regime fiscale: RF01=Ordinario, RF02=Minimi, RF04=Agricoltura, RF19=Forfettario",
    )

    # ------------------------------------------------------------
    # Colonne Regime IVA / Esenzione
    # ------------------------------------------------------------
    vat_exemption: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="True se il cliente è esente IVA",
    )

    vat_exemption_code: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        doc="Codice natura esenzione: N1, N2, N2.1, N2.2, N3, N3.1, N3.5, N4, N5, N6, N6.1, N6.9, N7",
    )

    vat_exemption_reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Descrizione testuale del motivo esenzione",
    )

    # ------------------------------------------------------------
    # Colonne Regime Pagamento Speciale
    # ------------------------------------------------------------
    split_payment: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="True per enti pubblici soggetti a split payment",
    )

    # ------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------
    vehicles: Mapped[List["Vehicle"]] = relationship(
        "Vehicle",
        back_populates="client",
        lazy="noload",
        doc="Veicoli associati al cliente",
    )

    work_orders: Mapped[List["WorkOrder"]] = relationship(
        "WorkOrder",
        back_populates="client",
        lazy="noload",
        doc="Ordini di lavoro associati al cliente",
    )

    invoices: Mapped[List["Invoice"]] = relationship(
        "Invoice",
        back_populates="client",
        lazy="noload",
        doc="Fatture associate al cliente",
    )

    payments: Mapped[List["Payment"]] = relationship(
        "Payment",
        back_populates="client",
        lazy="noload",
        doc="Pagamenti effettuati dal cliente",
    )

    # ------------------------------------------------------------
    # Indici
    # ------------------------------------------------------------
    __table_args__ = (
        Index("ix_clients_name_surname", "name", "surname"),
        Index("ix_clients_tax_id", "tax_id"),
        Index("ix_clients_sdi_code", "sdi_code"),
        Index("ix_clients_foreign_vat_exemption", "is_foreign", "vat_exemption"),
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
