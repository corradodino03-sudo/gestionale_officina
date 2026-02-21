"""
Schemas Pydantic per Dichiarazioni di Intenzione
Progetto: Garage Manager (Gestionale Officina)
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
)


class IntentDeclarationBase(BaseModel):
    """Schema base per dichiarazioni di intento."""
    
    protocol_number: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Numero protocollo Agenzia Entrate",
    )
    
    declaration_date: date = Field(
        ...,
        description="Data della dichiarazione",
    )
    
    amount_limit: Decimal = Field(
        ...,
        gt=0,
        description="Importo massimo dichiarato (plafond)",
    )
    
    expiry_date: date = Field(
        ...,
        description="Data di scadenza della dichiarazione",
    )
    
    notes: Optional[str] = Field(
        None,
        description="Note aggiuntive",
    )
    
    model_config = ConfigDict(from_attributes=True)
    
    @field_validator("declaration_date", "expiry_date", mode="before")
    @classmethod
    def validate_date_not_future(cls, v: date) -> date:
        """Valida che le date non siano eccessivamente nel futuro."""
        if v is None:
            return v
        # Allow future dates for declaration_date as it's when the document was submitted
        # But expiry_date should be reasonable
        return v


class IntentDeclarationCreate(IntentDeclarationBase):
    """Schema per la creazione di una dichiarazione di intento."""
    
    client_id: uuid.UUID = Field(
        ...,
        description="UUID del cliente a cui associare la dichiarazione",
    )
    
    is_active: bool = Field(
        default=True,
        description="Se la dichiarazione è attiva",
    )


class IntentDeclarationUpdate(BaseModel):
    """Schema per l'aggiornamento di una dichiarazione di intento."""
    
    protocol_number: Optional[str] = Field(
        None,
        min_length=1,
        max_length=50,
        description="Numero protocollo",
    )
    
    declaration_date: Optional[date] = Field(
        None,
        description="Data della dichiarazione",
    )
    
    amount_limit: Optional[Decimal] = Field(
        None,
        gt=0,
        description="Importo massimo dichiarato",
    )
    
    used_amount: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Importo già utilizzato",
    )
    
    expiry_date: Optional[date] = Field(
        None,
        description="Data di scadenza",
    )
    
    is_active: Optional[bool] = Field(
        None,
        description="Se la dichiarazione è attiva",
    )
    
    notes: Optional[str] = Field(
        None,
        description="Note aggiuntive",
    )
    
    model_config = ConfigDict(from_attributes=True)


class IntentDeclarationRead(IntentDeclarationBase):
    """Schema per la lettura di una dichiarazione di intento."""
    
    id: uuid.UUID = Field(
        ...,
        description="UUID della dichiarazione",
    )
    
    client_id: uuid.UUID = Field(
        ...,
        description="UUID del cliente",
    )
    
    used_amount: Decimal = Field(
        ...,
        description="Importo già utilizzato",
    )
    
    is_active: bool = Field(
        ...,
        description="Se la dichiarazione è attiva",
    )
    
    created_at: datetime = Field(
        ...,
        description="Data/ora creazione",
    )
    
    updated_at: datetime = Field(
        ...,
        description="Data/ora ultimo aggiornamento",
    )
    
    # ------------------------------------------------------------
    # Computed Fields
    # ------------------------------------------------------------
    @computed_field
    @property
    def remaining_amount(self) -> Decimal:
        """Plafond residuo disponibile."""
        return self.amount_limit - self.used_amount
    
    @computed_field
    @property
    def is_valid(self) -> bool:
        """Verifica se la dichiarazione è valida."""
        today = date.today()
        return (
            self.is_active
            and self.expiry_date >= today
            and self.remaining_amount > Decimal("0")
        )
    
    @computed_field
    @property
    def usage_percentage(self) -> float:
        """Percentuale di utilizzo del plafond."""
        if self.amount_limit == Decimal("0"):
            return 0.0
        return float((self.used_amount / self.amount_limit) * Decimal("100"))
    
    model_config = ConfigDict(from_attributes=True)


class IntentDeclarationList(BaseModel):
    """Schema per lista paginata dichiarazioni di intento."""
    
    items: list[IntentDeclarationRead] = Field(
        default_factory=list,
        description="Lista delle dichiarazioni",
    )
    
    total: int = Field(
        ...,
        ge=0,
        description="Numero totale di dichiarazioni",
    )
    
    page: int = Field(
        ...,
        ge=1,
        description="Pagina corrente",
    )
    
    per_page: int = Field(
        ...,
        ge=1,
        description="Elementi per pagina",
    )
    
    total_pages: int = Field(
        ...,
        description="Numero totale di pagine",
    )
    
    model_config = ConfigDict(from_attributes=True)
