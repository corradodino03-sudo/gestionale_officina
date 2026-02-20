"""
Mixin SQLAlchemy per modelli
Progetto: Garage Manager (Gestionale Officina)

Mixin riutilizzabili per aggiungere funzionalità comuni ai modelli.
"""

import datetime
import uuid

from sqlalchemy import Boolean, DateTime, Uuid
from sqlalchemy import event
from sqlalchemy.orm import Mapped, mapped_column, Session
from sqlalchemy.sql import func


class SoftDeleteMixin:
    """
    Mixin per implementare la cancellazione logica (soft delete).
    
    Aggiunge il campo is_active che, se impostato a False,
    indica che il record è stato "eliminato" ma non rimosso fisicamente.
    
    Usage:
        class MyModel(Base, SoftDeleteMixin):
            __tablename__ = "my_table"
            ...
    """

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Flag per soft delete: False = eliminato, True = attivo",
    )


class TimestampMixin:
    """
    Mixin per gestione automatica timestamp creazione e aggiornamento.
    
    Aggiunge i campi:
    - created_at: data/ora di creazione record (impostato automaticamente)
    - updated_at: data/ora ultimo aggiornamento (aggiornato automaticamente)
    
    Usage:
        class MyModel(Base, TimestampMixin):
            __tablename__ = "my_table"
            ...
    """

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Data/ora di creazione del record",
    )

    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Data/ora ultimo aggiornamento del record",
    )


class UUIDMixin:
    """
    Mixin per ID UUID generato server-side.
    
    Aggiunge il campo id come UUID primary key con generazione automatica.
    
    Usage:
        class MyModel(Base, UUIDMixin):
            __tablename__ = "my_table"
            ...
    """

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        doc="UUID primary key",
    )


# ------------------------------------------------------------
# Event Listeners
# ------------------------------------------------------------
@event.listens_for(Session, "before_flush")
def update_timestamp(session: Session, flush_context, instances) -> None:
    """
    Event listener per aggiornare automaticamente il campo updated_at.
    
    Questo listener viene eseguito prima di ogni flush e aggiorna il campo
    updated_at di tutti gli oggetti modificati (dirty) e nuovi (new).
    
    Args:
        session: Sessione SQLAlchemy
        flush_context: Contesto del flush
        instances: Oggetti instances (non usato)
    """
    # Get current timestamp with UTC timezone
    now = datetime.datetime.now(datetime.timezone.utc)
    
    # Update timestamp for dirty (modified) objects
    for obj in session.dirty:
        # Check if object has updated_at attribute (TimestampMixin)
        if hasattr(obj, 'updated_at'):
            # Only update if the object was actually modified
            if session.is_modified(obj, include_collections=False):
                obj.updated_at = now
    
    # Update timestamp for new objects
    for obj in session.new:
        # Check if object has updated_at attribute (TimestampMixin)
        if hasattr(obj, 'updated_at'):
            obj.updated_at = now
