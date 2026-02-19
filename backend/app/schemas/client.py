"""
Schemas Pydantic per l'entità Client
Progetto: Garage Manager (Gestionale Officina)

Definisce gli schemi di validazione e serializzazione per l'API.
"""

import datetime
import re
import uuid
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    computed_field,
    field_validator,
    model_validator,
)


# -------------------------------------------------------------------
# Funzioni di normalizzazione e validazione
# -------------------------------------------------------------------

def normalize_phone(phone: Optional[str]) -> Optional[str]:
    """
    Normalizza il numero di telefono.
    
    R e accetta solo +, numeri e spazi.
    
    Args:
       imuove spazi phone: Numero di telefono da normalizzare
        
    Returns:
        Numero di telefono normalizzato o None
        
    Raises:
        ValueError: Se il formato non è valido
    """
    if phone is None:
        return None
    
    # Rimuovi spazi
    normalized = phone.strip().replace(" ", "")
    
    # Regex: + seguito da numeri, oppure solo numeri
    if not re.match(r"^\+?\d+$", normalized):
        raise ValueError("Numero di telefono non valido")
    
    return normalized


def normalize_province(province: Optional[str]) -> Optional[str]:
    """
    Normalizza la provincia in maiuscolo a 2 caratteri.
    
    Args:
        province: Sigla provincia
        
    Returns:
        Sigla provincia normalizzata o None
        
    Raises:
        ValueError: Se la provincia non è esattamente 2 caratteri
    """
    if province is None:
        return None
    
    normalized = province.strip().upper()
    
    if len(normalized) != 2:
        raise ValueError("La provincia deve essere esattamente 2 caratteri")
    
    return normalized


def normalize_zip_code(zip_code: Optional[str]) -> Optional[str]:
    """
    Normalizza e valida il CAP (Codice di Avviamento Postale) italiano.
    
    Il CAP deve essere esattamente 5 cifre numeriche.
    
    Args:
        zip_code: CAP da validare
        
    Returns:
        CAP normalizzato o None
        
    Raises:
        ValueError: Se il CAP non è valido
    """
    if zip_code is None:
        return None
    
    normalized = zip_code.strip()
    
    # Deve essere esattamente 5 cifre numeriche
    if not re.match(r"^\d{5}$", normalized):
        raise ValueError("Il CAP deve essere esattamente 5 cifre numeriche")
    
    return normalized


def _luhn_check_piva(piva: str) -> bool:
    """
    Valida Partita IVA italiana con algoritmo di controllo Luhn modificato.
    
    L'algoritmo per P.IVA italiana usa modulo 10 con pesi alternati.
    
    Args:
        piva: Partita IVA da validare (11 cifre)
        
    Returns:
        True se la P.IVA è valida, False altrimenti
    """
    if len(piva) != 11 or not piva.isdigit():
        return False
    
    s = 0
    for i in range(0, 10, 2):
        s += int(piva[i])
    for i in range(1, 10, 2):
        c = 2 * int(piva[i])
        if c > 9:
            c -= 9
        s += c
    
    check = (10 - (s % 10)) % 10
    return check == int(piva[10])


def validate_tax_id(tax_id: Optional[str]) -> Optional[str]:
    """
    Valida il Codice Fiscale o la Partita IVA.
    
    Per il Codice Fiscale, verifica anche il checksum utilizzando
    la libreria 'codicefiscale' se disponibile.
    Per la Partita IVA, valida con algoritmo Luhn per P.IVA italiana.
    
    Args:
        tax_id: Codice Fiscale o Partita IVA
        
    Returns:
        Valore normalizzato o None
        
    Raises:
        ValueError: Se il formato non è valido
    """
    if tax_id is None:
        return None
    
    normalized = tax_id.strip().upper()
    
    # Partita IVA: esattamente 11 cifre
    if len(normalized) == 11 and normalized.isdigit():
        # Validazione Luhn per P.IVA italiana
        if not _luhn_check_piva(normalized):
            raise ValueError("Partita IVA non valida: cifra di controllo errata")
        return normalized
    
    # Codice Fiscale: 16 caratteri alfanumerici (formato base)
    if len(normalized) == 16 and re.match(r"^[A-Z0-9]+$", normalized):
        # Prova a validare il checksum con la libreria codicefiscale
        try:
            import codicefiscale
            # La libreria solleva un'eccezione se il codice non è valido
            # Usa 'is_valid' o 'isvalid' a seconda della versione
            if hasattr(codicefiscale, 'is_valid'):
                is_valid = codicefiscale.is_valid(normalized)
            else:
                is_valid = codicefiscale.isvalid(normalized)
            
            if is_valid:
                return normalized
            else:
                raise ValueError(
                    "Codice Fiscale non valido: checksum non corretto"
                )
        except ImportError:
            # Libreria non installata, fallback alla validazione base
            pass
        except ValueError:
            # Rilancia i ValueError dalla libreria (es. formato non riconosciuto)
            raise
        except Exception as e:
            # Qualsiasi altra eccezione inattesa dalla libreria
            # Rilancia come ValueError con messaggio descrittivo
            raise ValueError(
                f"Errore durante la validazione del Codice Fiscale: {str(e)}"
            )
        return normalized
    
    raise ValueError(
        "Tax ID non valido: deve essere 11 cifre (P.IVA) o 16 caratteri (Codice Fiscale)"
    )


# -------------------------------------------------------------------
# Mixin con validators comuni
# -------------------------------------------------------------------
class ClientValidatorsMixin(BaseModel):
    """
    Mixin che contiene i validator comuni per i campi del cliente.
    
    Include validazione per: tax_id, phone, province, zip_code.
    
    I campi sono dichiarati come Optional con default None per far funzionare
    i validator senza check_fields=False. Le classi figlie li sovrascriveranno
    con i propri tipi e default.
    """
    
    # Campi dichiarati per far funzionare i validator senza check_fields=False
    # Pydantic v2 usa check_fields=True come default
    tax_id: Optional[str] = None
    phone: Optional[str] = None
    province: Optional[str] = None
    zip_code: Optional[str] = None
    
    _normalize_tax_id = field_validator("tax_id", mode="before")(validate_tax_id)
    _normalize_phone = field_validator("phone", mode="before")(normalize_phone)
    _normalize_province = field_validator("province", mode="before")(
        normalize_province
    )
    _normalize_zip_code = field_validator("zip_code", mode="before")(
        normalize_zip_code
    )


# -------------------------------------------------------------------
# Schemas Base
# -------------------------------------------------------------------
class ClientBase(ClientValidatorsMixin):
    """
    Schema base per i dati anagrafici del cliente.
    
    Include tutti i campi condivisi tra creazione e aggiornamento.
    """

    # P0-2: Aggiunto model_config per supportare conversione ORM → Pydantic
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nome o ragione sociale",
    )

    surname: Optional[str] = Field(
        None,
        max_length=100,
        description="Cognome (per persone fisiche)",
    )

    is_company: bool = Field(
        default=False,
        description="Indica se è una persona giuridica",
    )

    tax_id: Optional[str] = Field(
        None,
        max_length=16,
        description="Codice Fiscale (16 char) o Partita IVA (11 cifre)",
    )

    address: Optional[str] = Field(
        None,
        max_length=255,
        description="Indirizzo completo",
    )

    city: Optional[str] = Field(
        None,
        max_length=100,
        description="Città",
    )

    zip_code: Optional[str] = Field(
        None,
        max_length=10,
        description="CAP (5 cifre)",
    )

    province: Optional[str] = Field(
        None,
        max_length=2,
        description="Sigla provincia (2 caratteri)",
    )

    phone: Optional[str] = Field(
        None,
        max_length=20,
        description="Numero di telefono",
    )

    email: Optional[EmailStr] = Field(
        None,
        max_length=255,
        description="Indirizzo email",
    )

    notes: Optional[str] = Field(
        None,
        description="Note aggiuntive sul cliente",
    )


# -------------------------------------------------------------------
# Schemas per Creazione
# -------------------------------------------------------------------
class ClientCreate(ClientBase):
    """
    Schema per la creazione di un nuovo cliente.
    
    Tutti i campi sono opzionali tranne name.
    """

    pass


# -------------------------------------------------------------------
# Schemas per Aggiornamento
# -------------------------------------------------------------------
class ClientUpdate(ClientValidatorsMixin):
    """
    Schema per l'aggiornamento di un cliente esistente.
    
    Tutti i campi sono opzionali per supportare update parziali (PATCH).
    """

    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Nome o ragione sociale",
    )

    surname: Optional[str] = Field(
        None,
        max_length=100,
        description="Cognome (per persone fisiche)",
    )

    is_company: Optional[bool] = Field(
        None,
        description="Indica se è una persona giuridica",
    )

    tax_id: Optional[str] = Field(
        None,
        max_length=16,
        description="Codice Fiscale (16 char) o Partita IVA (11 cifre)",
    )

    address: Optional[str] = Field(
        None,
        max_length=255,
        description="Indirizzo completo",
    )

    city: Optional[str] = Field(
        None,
        max_length=100,
        description="Città",
    )

    zip_code: Optional[str] = Field(
        None,
        max_length=10,
        description="CAP (5 cifre)",
    )

    province: Optional[str] = Field(
        None,
        max_length=2,
        description="Sigla provincia (2 caratteri)",
    )

    phone: Optional[str] = Field(
        None,
        max_length=20,
        description="Numero di telefono",
    )

    email: Optional[EmailStr] = Field(
        None,
        max_length=255,
        description="Indirizzo email",
    )

    notes: Optional[str] = Field(
        None,
        description="Note aggiuntive sul cliente",
    )


# -------------------------------------------------------------------
# Schemas per Lettura (API Response)
# -------------------------------------------------------------------
class ClientRead(ClientBase):
    """
    Schema per la risposta API che include i campi di sistema.
    
    Include id, created_at, updated_at.
    
    Nota: model_config è ereditato da ClientBase.
    """

    id: uuid.UUID = Field(
        ...,
        description="UUID del cliente",
    )

    created_at: datetime.datetime = Field(
        ...,
        description="Data/ora di creazione",
    )

    updated_at: datetime.datetime = Field(
        ...,
        description="Data/ora ultimo aggiornamento",
    )


# -------------------------------------------------------------------
# Schemas per Lista Paginata
# -------------------------------------------------------------------
class ClientList(BaseModel):
    """
    Schema per risposte paginate.
    
    Include la lista dei clienti con metadati di paginazione.
    """

    model_config = ConfigDict(from_attributes=True)

    items: list[ClientRead] = Field(
        default_factory=list,
        description="Lista dei clienti",
    )

    total: int = Field(
        ...,
        ge=0,
        description="Numero totale di clienti",
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

    # P1-3: Usato @computed_field invece di @model_validator per total_pages
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
