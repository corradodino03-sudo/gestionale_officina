import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base
from app.models.mixins import TimestampMixin, UUIDMixin

class CashRegisterClose(Base, UUIDMixin, TimestampMixin):
    """
    Modello per la chiusura cassa giornaliera.
    """
    __tablename__ = "cash_register_closes"

    close_date: Mapped[date] = mapped_column(
        Date, unique=True, nullable=False, doc="Data di chiusura"
    )
    closed_by: Mapped[str | None] = mapped_column(
        String(100), nullable=True, doc="Operatore che ha chiuso la cassa"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    total_cash: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    total_pos: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    total_bank_transfer: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    total_check: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    total_other: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    payments_count: Mapped[int] = mapped_column(nullable=False, default=0)
    
    is_reconciled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
