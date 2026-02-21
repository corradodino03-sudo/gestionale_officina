"""
Schemas Pydantic per l'entità User
Progetto: Garage Manager (Gestionale Officina)

Schemas per validazione e serializzazione dati utente.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.user import UserRole


class UserCreate(BaseModel):
    """
    Schema per la creazione di un nuovo utente.
    
    Attributes:
        email: Email dell'utente (deve essere univoca)
        password: Password in chiaro (min 8, max 100 caratteri)
        full_name: Nome completo dell'utente
        role: Ruolo dell'utente (default: mechanic)
    """

    email: EmailStr = Field(..., description="Email univoca dell'utente")
    password: str = Field(
        min_length=8,
        max_length=100,
        description="Password in chiaro (min 8, max 100 caratteri)",
    )
    full_name: str = Field(
        min_length=1,
        max_length=100,
        description="Nome completo dell'utente",
    )
    role: UserRole = Field(
        default=UserRole.MECHANIC,
        description="Ruolo dell'utente",
    )

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Valida la robustezza della password."""
        if len(v) < 8:
            raise ValueError("La password deve contenere almeno 8 caratteri")
        return v


class UserLogin(BaseModel):
    """
    Schema per il login utente.
    
    Attributes:
        email: Email dell'utente
        password: Password in chiaro
    """

    email: EmailStr = Field(..., description="Email dell'utente")
    password: str = Field(..., description="Password in chiaro")


class UserUpdate(BaseModel):
    """
    Schema per l'aggiornamento di un utente.
    
    Tutti i campi sono opzionali per permettere aggiornamenti parziali.
    """

    full_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Nome completo dell'utente",
    )
    role: Optional[UserRole] = Field(
        None,
        description="Ruolo dell'utente",
    )
    is_active: Optional[bool] = Field(
        None,
        description="Indica se l'utente è attivo",
    )


class UserResponse(BaseModel):
    """
    Schema per la risposta contenente dati utente.
    
    Utilizzato per le risposte API che espongono dati utente.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="UUID dell'utente")
    email: str = Field(..., description="Email dell'utente")
    full_name: str = Field(..., description="Nome completo dell'utente")
    role: UserRole = Field(..., description="Ruolo dell'utente")
    is_active: bool = Field(..., description="Indica se l'utente è attivo")
    created_at: datetime = Field(..., description="Data/ora di creazione")


# Export degli schemas
__all__ = [
    "UserCreate",
    "UserLogin",
    "UserUpdate",
    "UserResponse",
]
