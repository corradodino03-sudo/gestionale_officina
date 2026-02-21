"""
Modello SQLAlchemy per Dichiarazioni di Intenzione
Progetto: Garage Manager (Gestionale Officina)

Le dichiarazioni di intento (ex art. 1, c. 100, L. 244/2007) permettono
agli esportatori abituali di acquistare senza IVA fino ad un plafond dichiarato.
"""


from __future__ import annotations
import uuid
from datetime import date
from decimal import Decimal
from typing import Optional, TYPE_CHECKING, List

from sqlalchemy import Boolean, Date, ForeignKey, Index, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base
from app.models.mixins import TimestampMixin, UUIDMixin

# Import per type hinting relazioni (evita circular import)
if TYPE_CHECKING:
    from app.models.client import Client


class IntentDeclaration(Base, UUIDMixin, TimestampMixin):
    """
    Modello per le dichiarazioni di intento.
    
    Le dichiarazioni di intento permettono agli esportatori abituali di
    acquistare beni e servizi senza IVA, fino ad un ammontare massimo
    dichiarato (plafond).
    
    Attributes:
        id: UUID primary key
        client_id: FK al cliente (esportatore abituale)
        protocol_number: Numero protocollo Agenzia Entrate
        declaration_date: Data della dichiarazione
        amount_limit: Importo massimo dichiarato (plafond)
        used_amount: Importo già utilizzato
        expiry_date: Data di scadenza (di solito 31/12 dell'anno)
        is_active: Se la dichiarazione è attiva
        notes: Note aggiuntive
    
    Relationships:
        client: Cliente associato
    """

    __tablename__ = "intent_declarations"

    # ------------------------------------------------------------
    # Colonne Relazione
    # ------------------------------------------------------------
    client_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        doc="UUID del cliente esportatore abituale",
    )

    # ------------------------------------------------------------
    # Colonne Dati
    # ------------------------------------------------------------
    protocol_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Numero protocollo Agenzia Entrate",
    )

    declaration_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        doc="Data della dichiarazione",
    )

    amount_limit: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        doc="Importo massimo dichiarato (plafond)",
    )

    used_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0"),
        doc="Importo già utilizzato",
    )

    expiry_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        doc="Data di scadenza della dichiarazione",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Se la dichiarazione è attiva",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Note aggiuntive",
    )

    # ------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------
    client: Mapped["Client"] = relationship(
        "Client",
        back_populates="intent_declarations",
        lazy="selectin",
        doc="Cliente associato",
    )

    # ------------------------------------------------------------
    # Properties Calcolate
    # ------------------------------------------------------------
    @property
    def remaining_amount(self) -> Decimal:
        """
        Plafond residuo disponibile.
        
        Returns:
            Decimal: amount_limit - used_amount
        """
        return self.amount_limit - self.used_amount

    @property
    def is_valid(self) -> bool:
        """
        Verifica se la dichiarazione è valida.
        
        Una dichiarazione è valida se:
        - è attiva (is_active = True)
        - non è scaduta (expiry_date >= today)
        - ha plafond residuo (remaining_amount > 0)
        
        Returns:
            bool: True se la dichiarazione è valida
        """
        today = date.today()
        return (
            self.is_active
            and self.expiry_date >= today
            and self.remaining_amount > Decimal("0")
        )

    @property
    def usage_percentage(self) -> float:
        """
        Percentuale di utilizzo del plafond.
        
        Returns:
            float: Percentuale (0-100)
        """
        if self.amount_limit == Decimal("0"):
            return 0.0
        return float((self.used_amount / self.amount_limit) * Decimal("100"))

    # ------------------------------------------------------------
    # Indici
    # ------------------------------------------------------------
    __table_args__ = (
        Index("ix_intent_declarations_client_id", "client_id"),
        Index("ix_intent_declarations_expiry_date", "expiry_date"),
        Index("ix_intent_declarations_active", "client_id", "is_active"),
    )

    # ------------------------------------------------------------
    # Metodi
    # ------------------------------------------------------------
    def __repr__(self) -> str:
        return f"<IntentDeclaration(id={self.id}, client={self.client_id}, limit={self.amount_limit}, remaining={self.remaining_amount})>"
