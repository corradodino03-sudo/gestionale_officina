import datetime
import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TechnicianBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Nome del tecnico")
    surname: str = Field(..., min_length=1, max_length=100, description="Cognome del tecnico")
    phone: Optional[str] = Field(None, max_length=50, description="Telefono")
    email: Optional[str] = Field(None, max_length=255, description="Email")
    specialization: Optional[str] = Field(None, max_length=100, description="Specializzazione (es. Elettrauto)")
    is_active: bool = Field(default=True, description="Indica se il tecnico è attivo")
    hourly_rate: Optional[Decimal] = Field(None, ge=0, description="Tariffa oraria interna (costo)")


class TechnicianCreate(TechnicianBase):
    pass


class TechnicianUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    surname: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=255)
    specialization: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None
    hourly_rate: Optional[Decimal] = Field(None, ge=0)


class TechnicianRead(TechnicianBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime
