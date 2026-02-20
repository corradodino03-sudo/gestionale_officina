import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

class CashRegisterSummary(BaseModel):
    close_date: date = Field(..., description="Data di chiusura")
    total_cash: Decimal = Field(..., description="Totale incassato in contanti")
    total_pos: Decimal = Field(..., description="Totale incassato con POS")
    total_bank_transfer: Decimal = Field(..., description="Totale bonifici")
    total_check: Decimal = Field(..., description="Totale assegni")
    total_other: Decimal = Field(..., description="Totale altri metodi")
    total_amount: Decimal = Field(..., description="Somma di tutti i metodi")
    payments_count: int = Field(..., description="Numero di pagamenti inclusi")

class CashRegisterCloseCreate(BaseModel):
    close_date: date = Field(..., description="Data di chiusura")
    closed_by: Optional[str] = Field(None, description="Operatore")
    notes: Optional[str] = Field(None, description="Note")

class CashRegisterCloseRead(CashRegisterSummary):
    id: uuid.UUID
    closed_by: Optional[str]
    notes: Optional[str]
    is_reconciled: bool
    created_at: date
    updated_at: date

    model_config = ConfigDict(from_attributes=True)
