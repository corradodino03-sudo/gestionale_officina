"""
Schemas Pydantic per Ricambi e Magazzino
Progetto: Garage Manager (Gestionale Officina)

Contiene tutti gli schemi per la validazione e serializzazione
dei dati relativi a ricambi, utilizzi e movimenti di magazzino.
"""

import datetime
import logging
import re
import uuid
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

logger = logging.getLogger(__name__)


class MovementType(str, Enum):
    """Tipi di movimento di magazzino."""
    IN = "in"
    OUT = "out"
    ADJUSTMENT = "adjustment"


class UnitOfMeasure(str, Enum):
    """Unità di misura consentite per i ricambi."""
    PZ = "pz"
    LT = "lt"
    KG = "kg"
    MT = "mt"
    ML = "ml"
    GR = "gr"


# ------------------------------------------------------------
# Schemas PartCategory
# ------------------------------------------------------------

class PartCategoryBase(BaseModel):
    """Schema base per la categoria."""
    name: str = Field(..., min_length=1, max_length=100, description="Nome categoria")
    description: Optional[str] = Field(None, description="Descrizione")
    parent_id: Optional[uuid.UUID] = Field(None, description="Categoria padre (opzionale)")
    is_active: bool = Field(default=True, description="Categoria attiva")

class PartCategoryCreate(PartCategoryBase):
    pass

class PartCategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    parent_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None

class PartCategoryRead(PartCategoryBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime
    children: list["PartCategoryRead"] = Field(default_factory=list)

PartCategoryRead.model_rebuild()

# ------------------------------------------------------------
# Schemas Part
# ------------------------------------------------------------

class PartBase(BaseModel):
    """
    Schema base per i ricambi.
    
    Include tutti i campi modificabili comuni a create e update.
    """
    code: str = Field(..., min_length=2, max_length=50, description="Codice identificativo del ricambio")
    description: str = Field(..., min_length=1, max_length=255, description="Descrizione del ricambio")
    brand: Optional[str] = Field(None, max_length=100, description="Marca/fornitore")
    compatible_models: Optional[str] = Field(None, description="Modelli di veicolo compatibili")
    purchase_price: Decimal = Field(default=Decimal("0"), ge=0, description="Prezzo di acquisto")
    sale_price: Decimal = Field(default=Decimal("0"), ge=0, description="Prezzo di vendita")
    # FIX 5: Aggiunto campo vat_rate per gestione IVA per ricambio
    vat_rate: Decimal = Field(default=Decimal("22.00"), ge=Decimal("0"), le=Decimal("100"), description="Aliquota IVA del ricambio")
    min_stock_level: int = Field(default=0, ge=0, description="Livello minimo giacenza per alert")
    location: Optional[str] = Field(None, max_length=50, description="Posizione fisica in magazzino")
    is_active: bool = Field(default=True, description="Indica se il ricambio è attivo")
    category_id: Optional[uuid.UUID] = Field(None, description="UUID della categoria")
    unit_of_measure: UnitOfMeasure = Field(default=UnitOfMeasure.PZ, description="Unità di misura")

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        """Normalizza il codice: strip e uppercase."""
        if v:
            v = v.strip().upper()
        return v

    @field_validator("code")
    @classmethod
    def validate_code_format(cls, v: str) -> str:
        """Valida il formato del codice: solo alfanumerici e trattini."""
        if v and not re.match(r"^[A-Z0-9\-]{2,50}$", v):
            raise ValueError("Il codice deve contenere solo lettere, numeri e trattini (2-50 caratteri)")
        return v

    @model_validator(mode="after")
    def validate_prices(self):
        """Valida che il prezzo di vendita sia >= prezzo di acquisto."""
        if self.purchase_price and self.sale_price is not None:
            if self.sale_price < self.purchase_price:
                logger.warning(
                    "Prezzo di vendita inferiore al prezzo di acquisto per il ricambio %s: "
                    "acquisto=%s, vendita=%s",
                    self.code,
                    self.purchase_price,
                    self.sale_price,
                )
        return self


class PartCreate(PartBase):
    """
    Schema per la creazione di un nuovo ricambio.
    
    Nota: stock_quantity NON è presente — si gestisce SOLO tramite movimenti.
    """
    pass


class PartUpdate(BaseModel):
    """
    Schema per l'aggiornamento di un ricambio.
    
    Tutti i campi sono opzionali per supportare aggiornamenti parziali.
    """
    code: Optional[str] = Field(None, min_length=2, max_length=50, description="Codice identificativo")
    description: Optional[str] = Field(None, min_length=1, max_length=255, description="Descrizione")
    brand: Optional[str] = Field(None, max_length=100, description="Marca/fornitore")
    compatible_models: Optional[str] = Field(None, max_length=255, description="Modelli compatibili")
    purchase_price: Optional[Decimal] = Field(None, ge=0, description="Prezzo di acquisto")
    sale_price: Optional[Decimal] = Field(None, ge=0, description="Prezzo di vendita")
    # FIX 5: Aggiunto campo vat_rate per aggiornamento
    vat_rate: Optional[Decimal] = Field(None, ge=Decimal("0"), le=Decimal("100"), description="Aliquota IVA")
    min_stock_level: Optional[int] = Field(None, ge=0, description="Livello minimo giacenza")
    location: Optional[str] = Field(None, max_length=50, description="Posizione in magazzino")
    is_active: Optional[bool] = Field(None, description="Attivo/disponibile")
    category_id: Optional[uuid.UUID] = Field(None, description="UUID della categoria")
    unit_of_measure: Optional[UnitOfMeasure] = Field(None, description="Unità di misura")

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, v: Optional[str]) -> Optional[str]:
        """Normalizza il codice: strip e uppercase."""
        if v:
            v = v.strip().upper()
        return v

    @field_validator("code")
    @classmethod
    def validate_code_format(cls, v: Optional[str]) -> Optional[str]:
        """Valida il formato del codice."""
        if v and not re.match(r"^[A-Z0-9\-]{2,50}$", v):
            raise ValueError("Il codice deve contenere solo lettere, numeri e trattini (2-50 caratteri)")
        return v


class PartRead(PartBase):
    """
    Schema per la lettura di un ricambio.
    
    Include tutti i campi del database e i computed fields.
    """
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    stock_quantity: int = Field(..., description="Giacenza attuale")
    created_at: datetime.datetime
    updated_at: datetime.datetime
    category: Optional[PartCategoryRead] = Field(None, description="Categoria del ricambio")

    @computed_field
    @property
    def is_below_minimum(self) -> bool:
        """True se la giacenza è sotto il livello minimo."""
        return self.stock_quantity < self.min_stock_level


class PartList(BaseModel):
    """
    Schema per la lista paginata di ricambi.
    """
    items: list[PartRead]
    total: int
    page: int
    per_page: int
    total_pages: int = 0

    @model_validator(mode="after")
    def calculate_total_pages(self):
        """Calcola automaticamente il totale delle pagine."""
        if self.per_page > 0:
            self.total_pages = (self.total + self.per_page - 1) // self.per_page
        return self


# ------------------------------------------------------------
# Schemas PartUsage
# ------------------------------------------------------------

class PartUsageBase(BaseModel):
    """
    Schema base per l'utilizzo di ricambi in ordini di lavoro.
    """
    part_id: uuid.UUID = Field(..., description="UUID del ricambio")
    quantity: int = Field(..., ge=1, description="Quantità utilizzata")
    unit_price: Decimal = Field(..., ge=0, description="Prezzo unitario")


class PartUsageCreate(PartUsageBase):
    """
    Schema per l'aggiunta di un ricambio a un ordine di lavoro.
    """
    pass


class PartUsageRead(PartUsageBase):
    """
    Schema per la lettura di un utilizzo ricambio.
    
    Include dati denormalizzati dal ricambio per comodità.
    """
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    work_order_id: uuid.UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime
    part_code: Optional[str] = Field(None, description="Codice ricambio (denormalizzato)")
    part_description: Optional[str] = Field(None, description="Descrizione ricambio (denormalizzato)")
    unit_of_measure: UnitOfMeasure = Field(default=UnitOfMeasure.PZ, description="Unità di misura")

    @computed_field
    @property
    def line_total(self) -> Decimal:
        """Totale riga: quantity * unit_price."""
        return self.quantity * self.unit_price


class PartUsageList(BaseModel):
    """
    Schema per la lista di utilizzi ricambio (non paginata).
    """
    items: list[PartUsageRead]
    total: int


# ------------------------------------------------------------
# Schemas StockMovement
# ------------------------------------------------------------

class StockMovementBase(BaseModel):
    """
    Schema base per i movimenti di magazzino.
    """
    part_id: uuid.UUID = Field(..., description="UUID del ricambio")
    movement_type: MovementType = Field(..., description="Tipo di movimento")
    quantity: int = Field(..., description="Quantità del movimento")
    reference: Optional[str] = Field(None, max_length=255, description="Riferimento")
    notes: Optional[str] = Field(None, description="Note aggiuntive")

    @field_validator("quantity")
    @classmethod
    def validate_quantity_nonzero(cls, v: int) -> int:
        """Valida che la quantità non sia zero."""
        if v == 0:
            raise ValueError("La quantità non può essere zero")
        return v

    @model_validator(mode="after")
    def validate_out_quantity(self):
        """Valida che per movement_type OUT la quantity sia positiva nel payload."""
        if self.movement_type == MovementType.OUT and self.quantity < 0:
            raise ValueError("Per movimenti di tipo OUT, la quantità deve essere positiva nel payload")
        return self


class StockMovementCreate(StockMovementBase):
    """
    Schema per la creazione di un movimento di magazzino.
    """
    pass


class StockMovementRead(StockMovementBase):
    """
    Schema per la lettura di un movimento di magazzino.
    
    Include dati denormalizzati dal ricambio.
    """
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime.datetime
    part_code: Optional[str] = Field(None, description="Codice ricambio (denormalizzato)")
    part_description: Optional[str] = Field(None, description="Descrizione ricambio (denormalizzato)")


class StockMovementList(BaseModel):
    """
    Schema per la lista paginata di movimenti di magazzino.
    """
    items: list[StockMovementRead]
    total: int
    page: int
    per_page: int
    total_pages: int = 0

    @model_validator(mode="after")
    def calculate_total_pages(self):
        """Calcola automaticamente il totale delle pagine."""
        if self.per_page > 0:
            self.total_pages = (self.total + self.per_page - 1) // self.per_page
        return self


# ------------------------------------------------------------
# Schemas Alert Scorte
# ------------------------------------------------------------

class LowStockAlert(BaseModel):
    """
    Schema per un alert di stock basso.
    """
    part_id: uuid.UUID
    code: str
    description: str
    stock_quantity: int
    min_stock_level: int

    @computed_field
    @property
    def deficit(self) -> int:
        """Deficit: quantità mancante per raggiungere il livello minimo."""
        return self.min_stock_level - self.stock_quantity


class LowStockAlertList(BaseModel):
    """
    Schema per la lista degli alert di stock basso.
    """
    items: list[LowStockAlert]
    total: int
