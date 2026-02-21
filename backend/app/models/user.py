"""
Modello SQLAlchemy per l'entità User
Progetto: Garage Manager (Gestionale Officina)

Modello per l'autenticazione e gestione utenti del sistema.
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import Boolean, DateTime, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models import Base

if TYPE_CHECKING:
    pass


class UserRole(str, Enum):
    """Ruoli utente nel sistema."""
    ADMIN = "admin"
    MANAGER = "manager"
    MECHANIC = "mechanic"
    RECEPTIONIST = "receptionist"


class User(Base):
    """
    Modello per gli utenti del sistema.
    
    Gestisce l'autenticazione e le autorizzazioni per l'accesso
    alle funzionalità del gestionale.
    
    Attributes:
        id: UUID primary key, generato automaticamente
        email: Email univoca dell'utente
        hashed_password: Password hashata
        full_name: Nome completo dell'utente
        role: Ruolo dell'utente (admin, manager, mechanic, receptionist)
        is_active: Indica se l'utente è attivo
        created_at: Data/ora creazione record
        updated_at: Data/ora ultimo aggiornamento
    """

    __tablename__ = "users"

    # Primary key UUID
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        doc="UUID primary key",
    )

    # Email univoca
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        doc="Email univoca dell'utente",
    )

    # Password hashata
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Password hashata",
    )

    # Nome completo
    full_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Nome completo dell'utente",
    )

    # Ruolo
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=UserRole.MECHANIC.value,
        doc="Ruolo dell'utente",
    )

    # Flag attivo
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Indica se l'utente è attivo",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Data/ora di creazione del record",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        doc="Data/ora ultimo aggiornamento del record",
    )

    # Indici
    __table_args__ = (
        Index("ix_users_email", "email"),
        Index("ix_users_role", "role"),
        # Check constraint per il ruolo (a livello applicativo in SQLAlchemy 2.0)
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"
