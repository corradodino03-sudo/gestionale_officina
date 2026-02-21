"""
Modello SQLAlchemy per l'entità Client
Progetto: Garage Manager (Gestionale Officina)

Rappresenta l'anagrafica dei clienti (persone fisiche e giuridiche).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base
from app.models.mixins import TimestampMixin, UUIDMixin, SoftDeleteMixin

# Import per type hinting relazioni (evita circular import)
if TYPE_CHECKING:
    from app.models.vehicle import Vehicle
    from app.models.work_order import WorkOrder
    from app.models.invoice import Invoice, Payment
    from app.models.intent_declaration import IntentDeclaration


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
    # Colonne Aliquota IVA Predefinita (FEAT 1)
    # ------------------------------------------------------------
    default_vat_rate: Mapped[float] = mapped_column(
        Float,
        default=22.00,
        nullable=False,
        doc="Aliquota IVA predefinita del cliente (default 22%)",
    )

    # ------------------------------------------------------------
    # Colonne Condizioni Pagamento Predefinite (FEAT 2)
    # ------------------------------------------------------------
    payment_terms_days: Mapped[int] = mapped_column(
        Integer,
        default=30,
        nullable=False,
        doc="Giorni per la scadenza fattura dalla data emissione (default 30)",
    )

    payment_method_default: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        doc="Metodo di pagamento predefinito: cash, pos, bank_transfer, check, other",
    )

    # ------------------------------------------------------------
    # Colonne Sconto Predefinito Cliente (FEAT 3)
    # ------------------------------------------------------------
    default_discount_percent: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        doc="Sconto predefinito percentuale (0-100). Es: 10.00 = 10% di sconto",
    )

    # ------------------------------------------------------------
    # Colonne Indirizzo Sede Legale (FEAT 5)
    # ------------------------------------------------------------
    # I campi address, city, zip_code, province rappresentano la SEDE LEGALE
    # I campi billing_* rappresentano la SEDE DI FATTURAZIONE (opzionali)

    # ------------------------------------------------------------
    # Colonne Indirizzo Sede di Fatturazione (FEAT 5)
    # ------------------------------------------------------------
    billing_address: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Indirizzo sede di fatturazione (se diverso dalla sede legale)",
    )

    billing_city: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Città sede di fatturazione",
    )

    billing_zip_code: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        doc="CAP sede di fatturazione",
    )

    billing_province: Mapped[str | None] = mapped_column(
        String(2),
        nullable=True,
        doc="Sigla provincia sede di fatturazione (2 caratteri)",
    )

    # ------------------------------------------------------------
    # Colonne Fido Commerciale (FEAT 7)
    # ------------------------------------------------------------
    credit_limit: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        doc="Fido massimo accordato al cliente. None = nessun limite",
    )

    credit_limit_action: Mapped[str] = mapped_column(
        String(10),
        default="warn",
        nullable=False,
        doc="Azione se superato fido: 'block' blocca fattura, 'warn' avvisa",
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

    intent_declarations: Mapped[List["IntentDeclaration"]] = relationship(
        "IntentDeclaration",
        back_populates="client",
        lazy="noload",
        doc="Dichiarazioni di intento del cliente",
    )

    # ------------------------------------------------------------
    # Properties Calcolate (FEAT 5)
    # ------------------------------------------------------------
    @property
    def effective_billing_address(self) -> dict:
        """
        Restituisce i dati di fatturazione effettivi.
        
        Se la sede di fatturazione è specificata, la usa;
        altrimenti restituisce i dati della sede legale.
        
        Returns:
            dict con chiavi: address, city, zip_code, province
        """
        if self.billing_address:
            return {
                "address": self.billing_address,
                "city": self.billing_city,
                "zip_code": self.billing_zip_code,
                "province": self.billing_province,
            }
        return {
            "address": self.address,
            "city": self.city,
            "zip_code": self.zip_code,
            "province": self.province,
        }

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
