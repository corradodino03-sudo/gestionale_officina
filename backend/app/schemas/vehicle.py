"""
Schemas Pydantic per l'entità Vehicle
Progetto: Garage Manager (Gestionale Officina)

Definisce gli schemi di validazione e serializzazione per l'API.
"""

from enum import Enum
import datetime
import re
import uuid
from typing import TYPE_CHECKING, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
)

class FuelType(str, Enum):
    """Tipi di carburante validi per i veicoli."""
    BENZINA = "benzina"
    DIESEL = "diesel"
    GPL = "gpl"
    METANO = "metano"
    ELETTRICO = "elettrico"
    IBRIDO = "ibrido"
    IBRIDO_PLUGIN = "ibrido_plugin"

# Caratteri non validi nel VIN (standard VIN: no I, O, Q)
VIN_INVALID_CHARS = set("IOQ")


# -------------------------------------------------------------------
# Funzioni di normalizzazione e validazione
# -------------------------------------------------------------------

def normalize_plate(plate: Optional[str]) -> Optional[str]:
    """
    Normalizza la targa del veicolo.
    
    Converte in maiuscolo, rimuove spazi e valida il formato.
    Accetta formati italiani (es. "AB 123 CD", "AB123CD") e europei.
    
    Args:
        plate: Targa da normalizzare
        
    Returns:
        Targa normalizzata (maiuscolo, senza spazi) o None
        
    Raises:
        ValueError: Se il formato non è valido
    """
    if plate is None:
        return None
    
    # Rimuovi spazi e converti in maiuscolo
    normalized = plate.strip().upper().replace(" ", "")
    
    # Valida formato: 2-20 caratteri alfanumerici
    if not re.match(r"^[A-Z0-9]{2,20}$", normalized):
        raise ValueError(
            "Targa non valida: deve contenere 2-20 caratteri alfanumerici"
        )
    
    return normalized


def normalize_vin(vin: Optional[str]) -> Optional[str]:
    """
    Normalizza il numero telaio (VIN).
    
    Converte in maiuscolo, rimuove spazi e valida il formato standard VIN.
    Il VIN deve essere esattamente 17 caratteri alfanumerici
    (esclusi I, O, Q per standard VIN).
    
    Args:
        vin: Numero telaio da normalizzare
        
    Returns:
        VIN normalizzato (maiuscolo, 17 char) o None
        
    Raises:
        ValueError: Se il formato non è valido
    """
    if vin is None:
        return None
    
    # Rimuovi spazi e converti in maiuscolo
    normalized = vin.strip().upper().replace(" ", "")
    
    # Deve essere esattamente 17 caratteri
    if len(normalized) != 17:
        raise ValueError("Il numero telaio (VIN) deve essere esattamente 17 caratteri")
    
    # Solo caratteri alfanumerici
    if not re.match(r"^[A-Z0-9]+$", normalized):
        raise ValueError(
            "Il numero telaio (VIN) deve contenere solo caratteri alfanumerici"
        )
    
    # Non deve contenere I, O, Q (standard VIN)
    if any(c in VIN_INVALID_CHARS for c in normalized):
        raise ValueError(
            "Il numero telaio (VIN) non può contenere le lettere I, O, Q"
        )
    
    return normalized


def validate_year(year: Optional[int]) -> Optional[int]:
    """
    Valida l'anno di immatricolazione.
    
    L'anno deve essere >= 1900 e <= anno corrente + 1.
    
    Args:
        year: Anno da validare
        
    Returns:
        Anno validato o None
        
    Raises:
        ValueError: Se l'anno non è valido
    """
    if year is None:
        return None
    
    current_year = datetime.datetime.now().year
    max_year = current_year + 1
    
    if year < 1900:
        raise ValueError("L'anno di immatricolazione deve essere >= 1900")
    
    if year > max_year:
        raise ValueError(
            f"L'anno di immatricolazione non può essere superiore a {max_year}"
        )
    
    return year


# -------------------------------------------------------------------
# Mixin con validators comuni
# -------------------------------------------------------------------
class VehicleValidatorsMixin(BaseModel):
    """
    Mixin che contiene i validator comuni per i campi del veicolo.
    
    Include validazione per: plate, vin, year, current_km, fuel_type.
    
    I campi sono dichiarati come Optional con default None ESCLUSIVAMENTE
    per permettere a Pydantic v2 di registrare i field_validator su questi campi.
    Le classi figlie (VehicleBase, VehicleUpdate) DEVONO sovrascrivere questi campi
    con i propri tipi e vincoli — l'ordine MRO garantisce che i validator del mixin
    vengano applicati ai campi ridefiniti nelle classi figlie.
    
    ATTENZIONE: Non modificare i default di questo mixin senza verificare
    l'impatto sulle classi figlie.
    """
    
    # Campi dichiarati per far funzionare i validator
    plate: Optional[str] = None
    vin: Optional[str] = None
    year: Optional[int] = None
    current_km: Optional[int] = None
    fuel_type: Optional[FuelType] = None
    
    _normalize_plate = field_validator("plate", mode="before")(normalize_plate)
    _normalize_vin = field_validator("vin", mode="before")(normalize_vin)
    _validate_year = field_validator("year", mode="before")(validate_year)


# -------------------------------------------------------------------
# Schemas Base
# -------------------------------------------------------------------
class VehicleBase(VehicleValidatorsMixin):
    """
    Schema base per i dati del veicolo.
    
    Include tutti i campi condivisi tra creazione e aggiornamento.
    """

    # NOTA: from_attributes=True è applicato solo su VehicleRead
    # per supportare la conversione ORM → Pydantic

    client_id: uuid.UUID = Field(
        ...,
        description="UUID del cliente proprietario",
    )

    plate: str = Field(
        ...,
        min_length=2,
        max_length=20,
        description="Targa del veicolo",
    )

    brand: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Marca del veicolo",
    )

    model: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Modello del veicolo",
    )
    
    color: Optional[str] = Field(
        None,
        max_length=50,
        description="Colore",
    )

    year: Optional[int] = Field(
        None,
        description="Anno di immatricolazione",
    )

    current_km: Optional[int] = Field(
        default=0,
        ge=0,
        description="Chilometraggio attuale",
    )

    vin: Optional[str] = Field(
        default=None,
        min_length=17,
        max_length=17,
        description="Numero telaio (VIN)",
    )

    fuel_type: Optional[FuelType] = Field(
        default=None,
        description="Tipo di carburante",
    )

    notes: Optional[str] = Field(
        default=None,
        description="Note aggiuntive sul veicolo",
    )


# -------------------------------------------------------------------
# Schemas per Creazione
# -------------------------------------------------------------------
class VehicleCreate(VehicleBase):
    """
    Schema per la creazione di un nuovo veicolo.
    
    Eredita tutti i campi obbligatori da VehicleBase.
    """
    pass


# -------------------------------------------------------------------
# Schemas per Aggiornamento
# -------------------------------------------------------------------
class VehicleUpdate(VehicleValidatorsMixin):
    """
    Schema per l'aggiornamento di un veicolo esistente.
    
    Tutti i campi sono opzionali per supportare update parziali (PATCH).
    NOTA: Non eredita da VehicleBase perché i campi obbligatori
    diventano Optional per supportare semantica PATCH.
    """

    model_config = ConfigDict(from_attributes=True)

    client_id: Optional[uuid.UUID] = Field(
        None,
        description="UUID del cliente proprietario",
    )

    plate: Optional[str] = Field(
        None,
        min_length=2,
        max_length=20,
        description="Targa del veicolo",
    )

    brand: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Marca del veicolo",
    )

    model: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Modello del veicolo",
    )
    
    color: Optional[str] = Field(
        None,
        max_length=50,
        description="Colore",
    )

    year: Optional[int] = Field(
        None,
        description="Anno di immatricolazione",
    )

    current_km: Optional[int] = Field(
        None,
        ge=0,
        description="Chilometraggio attuale",
    )

    vin: Optional[str] = Field(
        None,
        min_length=17,
        max_length=17,
        description="Numero telaio (VIN)",
    )

    fuel_type: Optional[FuelType] = Field(
        None,
        description="Tipo di carburante",
    )

    notes: Optional[str] = Field(
        None,
        description="Note aggiuntive sul veicolo",
    )


# -------------------------------------------------------------------
# Schemas per Lettura (API Response)
# -------------------------------------------------------------------
# Import condizionale per evitare circular import
if TYPE_CHECKING:
    from app.schemas.client import ClientRead


class VehicleRead(VehicleBase):
    """
    Schema per la risposta API che include i campi di sistema.
    
    Include id, created_at, updated_at.
    Opzionalmente include i dati del cliente se caricati.
    
    Nota: model_config con from_attributes=True è necessario per
    la conversione da oggetto ORM a schema Pydantic.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(
        ...,
        description="UUID del veicolo",
    )

    created_at: datetime.datetime = Field(
        ...,
        description="Data/ora di creazione",
    )

    updated_at: datetime.datetime = Field(
        ...,
        description="Data/ora ultimo aggiornamento",
    )

    # Campo opzionale per includere i dati del cliente
    # Dichiarato con forward reference per evitare circular import a runtime
    client: Optional["ClientRead"] = Field(
        default=None,
        description="Dati del cliente proprietario",
    )


# -------------------------------------------------------------------
# Schemas per Lista Paginata
# -------------------------------------------------------------------
class VehicleList(BaseModel):
    """
    Schema per risposte paginate.
    
    Include la lista dei veicoli con metadati di paginazione.
    """

    items: list[VehicleRead] = Field(
        default_factory=list,
        description="Lista dei veicoli",
    )

    total: int = Field(
        ...,
        ge=0,
        description="Numero totale di veicoli",
    )

    page: int = Field(
        ...,
        ge=1,
        description="Numero pagina corrente",
    )

    per_page: int = Field(
        ...,
        ge=1,
        description="Numero elementi per pagina",
    )

    @computed_field
    def total_pages(self) -> int:
        """
        Numero totale di pagine.
        
        Calcolato automaticamente in base a total e per_page usando
        la formula: ceil(total / per_page)
        
        Returns:
            Numero totale di pagine
        """
        if self.per_page > 0:
            return (self.total + self.per_page - 1) // self.per_page
        return 0


# NOTA: VehicleRead.model_rebuild() deve essere chiamato dopo l'import di ClientRead
# per risolvere il forward reference. Questo viene fatto in app/schemas/__init__.py
