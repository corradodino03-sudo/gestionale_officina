from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional, TYPE_CHECKING, List

from sqlalchemy import Boolean, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base
from app.models.mixins import SoftDeleteMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.work_order import WorkOrder, WorkOrderItem


class Technician(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """
    Modello per l'anagrafica dei tecnici/meccanici dell'officina.
    """
    __tablename__ = "technicians"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    surname: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    specialization: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    hourly_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

    # Relationships
    work_orders: Mapped[List["WorkOrder"]] = relationship(
        "WorkOrder",
        back_populates="assigned_technician",
        lazy="noload"
    )

    work_order_items: Mapped[List["WorkOrderItem"]] = relationship(
        "WorkOrderItem",
        back_populates="technician",
        lazy="noload"
    )

    def __repr__(self) -> str:
        return f"Technician(name={self.name!r}, surname={self.surname!r})"
