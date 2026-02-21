"""
Schemas Pydantic per l'entità Client
Progetto: Garage Manager (Gestionale Officina)
"""
# Definisce gli schemi di validazione e serializzazione per l'API.

import datetime
import logging
import re
import uuid
from enum import Enum
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

from app.schemas.invoice import PaymentMethod
from app.core.exceptions import BusinessValidationError

# Logger per questo modulo
logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Import libreria esterna per validazione Codice Fiscale
# -------------------------------------------------------------------
try:
    import codicefiscale as _cf_lib
    _HAS_CF_LIB = True
except ImportError:
    _cf_lib = None  # type: ignore
    _HAS_CF_LIB = False


# -------------------------------------------------------------------
# Enum per Codici Fiscali
# -------------------------------------------------------------------
class VatExemptionCode(str, Enum):
    """Codici Natura IVA per FatturaPA."""
    N1 = "N1"          # Escluse ex art.15
    N2 = "N2"          # Non soggette
    N2_1 = "N2.1"      # Non soggette - extra UE
    N2_2 = "N2.2"      # Non soggette - intra UE
    N3 = "N3"          # Non imponibili
    N3_1 = "N3.1"      # Non imponibili - esportazioni
    N3_5 = "N3.5"      # Non imponibili - dichiarazioni intento
    N4 = "N4"          # Esenti
    N5 = "N5"          # Regime del margine
    N6 = "N6"          # Inversione contabile
    N6_1 = "N6.1"      # RC - rottami
    N6_9 = "N6.9"      # RC - altri casi
    N7 = "N7"          # IVA assolta in altro stato UE


class VatRegime(str, Enum):
    """Codici Regime Fiscale per FatturaPA."""
    RF01 = "RF01"   # Ordinario
    RF02 = "RF02"   # Contribuenti minimi
    RF04 = "RF04"   # Agricoltura
    RF19 = "RF19"   # Forfettario


class ClientType(str, Enum):
    """Tipo di cliente."""
    PRIVATE    = "private"     # Persona fisica privata
    COMPANY    = "company"     # Azienda / Società
    FREELANCER = "freelancer"  # Libero professionista
    PA         = "pa"          # Ente Pubblico (PA)


# -------------------------------------------------------------------
# Funzioni di normalizzazione e validazione
# -------------------------------------------------------------------

def normalize_phone(phone: Optional[str]) -> Optional[str]:
    """
    Normalizza il numero di telefono.
    
    Rimuove spazi e accetta solo +, numeri e spazi.
    
    Args:
        phone: Numero di telefono da normalizzare
        
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
    Normalizza la provincia in maiuscolo a 2 o 3 caratteri.
    
    Args:
        province: Sigla provincia
        
    Returns:
        Sigla provincia normalizzata o None
        
    Raises:
        ValueError: Se la provincia non è 2 o 3 caratteri alfabetici
    """
    if province is None:
        return None
    
    normalized = province.strip().upper()
    
    # Regex: 2 o 3 lettere maiuscole
    if not re.match(r"^[A-Z]{2,3}$", normalized):
        raise ValueError("La provincia deve essere 2 o 3 caratteri alfabetici")
    
    return normalized


def normalize_zip_code(zip_code: Optional[str], info=None) -> Optional[str]:
    """
    Normalizza e valida il CAP (Codice di Avviamento Postale) italiano.
    
    Il CAP deve essere esattamente 5 cifre numeriche per clienti italiani.
    Per clienti esteri, accetta qualsiasi formato non vuoto.
    
    Args:
        zip_code: CAP da validare
        info: FieldValidationInfo per accedere ad altri campi
        
    Returns:
        CAP normalizzato o None
        
    Raises:
        ValueError: Se il CAP non è valido
    """
    if zip_code is None:
        return None
    
    normalized = zip_code.strip()
    
    # Check if this is a foreign client by checking the context
    # We need to check is_foreign and country_code fields
    # This is a workaround since field_validator doesn't have easy access to other fields
    # So we just accept any non-empty string for now and do strict validation at model level
    
    # For Italian clients, require 5 numeric digits
    # For foreign clients, accept any format
    # We do a lenient validation here and let model_validator do strict checks
    if not normalized:
        raise ValueError("Il CAP non può essere vuoto")
    
    # Accept any format here - the model validator will do strict validation
    # for Italian clients
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


def _validate_codice_fiscale(tax_id: str) -> None:
    """
    Valida il checksum di un Codice Fiscale italiano.
    
    Usa la libreria 'codicefiscale' se disponibile,
    altrimenti accetta il CF senza checksum.
    
    Args:
        tax_id: Codice Fiscale (16 caratteri, già normalizzato)
        
    Raises:
        BusinessValidationError: Se il checksum non è corretto
    """
    if not _HAS_CF_LIB:
        # Libreria non installata, accetta senza checksum
        return
    
    try:
        is_valid = (
            _cf_lib.is_valid(tax_id)
            if hasattr(_cf_lib, "is_valid")
            else _cf_lib.isvalid(tax_id)
        )
        if not is_valid:
            raise BusinessValidationError(
                "Codice Fiscale non valido: checksum non corretto"
            )
    except BusinessValidationError:
        raise
    except Exception as e:
        raise BusinessValidationError(
            f"Errore durante la validazione del Codice Fiscale: {e}"
        )


def normalize_fiscal_code_basic(fiscal_code: Optional[str]) -> Optional[str]:
    """
    Normalizza il Codice Fiscale: strip e uppercase.
    
    La validazione rigorosa (struttura + checksum) viene eseguita
    nel model_validator per clienti italiani.
    
    Args:
        fiscal_code: Codice Fiscale italiano
        
    Returns:
        Valore normalizzato o None
    """
    if fiscal_code is None:
        return None
    return fiscal_code.strip().upper()


def normalize_vat_number_basic(vat_number: Optional[str]) -> Optional[str]:
    """
    Normalizza la Partita IVA: strip (solo cifre, nessun uppercase necessario).
    
    Args:
        vat_number: Partita IVA italiana (11 cifre)
        
    Returns:
        Valore normalizzato o None
    """
    if vat_number is None:
        return None
    return vat_number.strip()


# -------------------------------------------------------------------
# Schemas per Creazione e Lettura (usati nel Mixin per distinguere)
# -------------------------------------------------------------------
class _ClientCreateMixin(BaseModel):
    """
    Schema base vuoto usato per identificare il tipo di operazione.
    
    NOTA: Questa classe è rinominata da ClientBase originale per evitare
    conflitti di ereditarietà. È usata solo per distinguere tra CREATE e UPDATE.
    """
    pass



class ClientValidatorsMixin(BaseModel):
    """
    Mixin che contiene i validator comuni per i campi del cliente.
    
    Include validazione per: tax_id, phone, province, zip_code.
    Include validazione per: sdi_code, pec, country_code.
    
    NOTA: I campi NON sono dichiarati qui per evitare conflitti di ereditarietà.
    Le classi figlie dichiarano i propri campi. I validator usano check_fields=False
    per essere applicati solo se i campi esistono nelle classi figlie.
    
    Per vat_regime e vat_exemption_code, la validazione è gestita nativamente
    dagli Enum in ClientBase/ClientUpdate.
    
    FIX: Dichiarazione stub campi per Pydantic v2 - i campi usati nel validator
    devono essere definiti almeno come stub type-annotated nel Mixin.
    Le classi figlie li sovrascriveranno con Field completi.
    """
    
    # Stub per campi usati nel validator (senza Field, solo type hints)
    # Le classi figlie li sovrascriveranno con Field completi
    fiscal_code: Optional[str] = None
    vat_number: Optional[str] = None
    client_type: Optional[str] = None
    gdpr_consent: Optional[bool] = None
    is_foreign: Optional[bool] = None
    country_code: Optional[str] = None
    sdi_code: Optional[str] = None
    pec: Optional[str] = None
    vat_exemption: Optional[bool] = None
    vat_exemption_code: Optional[VatExemptionCode] = None
    split_payment: Optional[bool] = None
    credit_limit_action: Optional[str] = None
    
    # NOTA: Dichiarazione campi rimossa per evitare conflitti di ereditarietà.
    # I validator usano check_fields=False per funzionare correttamente.
    
    # Validator base per fiscal_code: strip e uppercase
    _normalize_fiscal_code = field_validator(
        "fiscal_code",
        mode="before",
        check_fields=False
    )(normalize_fiscal_code_basic)

    # Validator base per vat_number: strip
    _normalize_vat_number = field_validator(
        "vat_number",
        mode="before",
        check_fields=False
    )(normalize_vat_number_basic)
    
    _normalize_phone = field_validator(
        "phone", 
        mode="before",
        check_fields=False
    )(normalize_phone)
    
    _normalize_province = field_validator(
        "province", 
        mode="before",
        check_fields=False
    )(normalize_province)
    
    _normalize_zip_code = field_validator(
        "zip_code", 
        mode="before",
        check_fields=False
    )(normalize_zip_code)
    
    # Validatori per campi fiscali
    @field_validator("sdi_code", mode="before", check_fields=False)
    @classmethod
    def normalize_sdi_code(cls, v: Optional[str]) -> Optional[str]:
        """Normalizza il codice SDI: uppercase, strip, valida formato."""
        if v is None:
            return None
        normalized = v.strip().upper()
        # Valori speciali accettati
        if normalized in ("0000000", "XXXXXXX"):
            return normalized
        # Deve essere esattamente 7 caratteri alfanumerici
        if not re.match(r"^[A-Z0-9]{7}$", normalized):
            raise ValueError(
                "Il codice SDI deve essere esattamente 7 caratteri alfanumerici "
                "(o '0000000' per PEC, 'XXXXXXX' per esteri)"
            )
        return normalized
    
    @field_validator("country_code", mode="before", check_fields=False)
    @classmethod
    def normalize_country_code(cls, v: Optional[str]) -> Optional[str]:
        """Normalizza il codice paese: uppercase, esattamente 2 lettere."""
        if v is None:
            return None
        normalized = v.strip().upper()
        if not re.match(r"^[A-Z]{2}$", normalized):
            raise ValueError(
                "Il codice paese deve essere esattamente 2 caratteri alfabetici (ISO 3166-1 alpha-2)"
            )
        return normalized
    
    @field_validator("credit_limit_action", mode="before", check_fields=False)
    @classmethod
    def validate_credit_limit_action(cls, v: Optional[str]) -> Optional[str]:
        """Valida che credit_limit_action sia 'block' o 'warn'."""
        if v is None:
            return v
        if v not in ("block", "warn"):
            raise ValueError("credit_limit_action deve essere 'block' o 'warn'")
        return v
    
    @model_validator(mode="after")
    def validate_fiscal_consistency(self) -> "ClientValidatorsMixin":
        """
        Valida la coerenza tra i campi fiscali e GDPR.
        
        Distingue tra:
        - CREATE (ClientBase/ClientCreate): validazione completa su tutti i campi
        - UPDATE (ClientUpdate): validazione solo sui campi presenti nel payload,
          usando model_fields_set per evitare falsi positivi
        
        Include:
        - Validazione fiscal_code (16 char alfanumerici o 11 cifre per aziende)
        - Validazione vat_number (11 cifre + checksum Luhn) — SOLO per clienti italiani
        - Obbligatorietà campi fiscali per tipo cliente
        - Controllo sdi_code vs pec
        - Controllo vat_exemption vs vat_exemption_code
        - Controllo split_payment vs client_type
        """
        # Determina se siamo in un update parziale (PATCH)
        is_partial_update = self.__class__.__name__ == "ClientUpdate"
        
        def field_is_relevant(field_name: str) -> bool:
            """
            Ritorna True se il campo deve essere validato.
            - In CREATE: sempre True
            - In UPDATE: True solo se il campo è nel payload inviato
            """
            if not is_partial_update:
                return True
            return field_name in self.model_fields_set
        
        # Determina il client_type effettivo
        effective_client_type = self.client_type or "private"

        # ----------------------------------------------------------------
        # Validazione CODICE FISCALE — SOLO per clienti italiani
        # ----------------------------------------------------------------
        effective_country_code = self.country_code
        if effective_country_code is None and not field_is_relevant("country_code"):
            effective_country_code = "IT"

        is_italian = (
            self.is_foreign is not True
            and effective_country_code in ("IT", None)
        )

        if self.fiscal_code and field_is_relevant("fiscal_code") and is_italian:
            fc = self.fiscal_code  # già normalizzato uppercase
            # Accetta: 16 char alfanumerici (PF) oppure 11 cifre (aziende = uguale a P.IVA)
            if len(fc) == 16 and re.match(r"^[A-Z0-9]+$", fc):
                _validate_codice_fiscale(fc)
            elif len(fc) == 11 and fc.isdigit():
                # Codice fiscale numerico (coincide con P.IVA per le società)
                pass  # Valido per aziende
            else:
                raise BusinessValidationError(
                    "Codice Fiscale non valido: deve essere 16 caratteri alfanumerici (persone fisiche) "
                    "o 11 cifre numeriche (aziende/coincidente con P.IVA)"
                )

        # ----------------------------------------------------------------
        # Validazione PARTITA IVA — SOLO per clienti italiani
        # ----------------------------------------------------------------
        if self.vat_number and field_is_relevant("vat_number") and is_italian:
            piva = self.vat_number
            if not piva.isdigit() or len(piva) != 11:
                raise BusinessValidationError(
                    "Partita IVA non valida: deve essere esattamente 11 cifre numeriche"
                )
            if not _luhn_check_piva(piva):
                raise BusinessValidationError(
                    "Partita IVA non valida: cifra di controllo errata (algoritmo Luhn)"
                )

        # ----------------------------------------------------------------
        # Obbligatorietà campi fiscali per tipo cliente (solo in CREATE)
        # ----------------------------------------------------------------
        if not is_partial_update:
            if effective_client_type == "private":
                # Privato: codice fiscale obbligatorio, P.IVA opzionale
                if not self.fiscal_code and is_italian:
                    raise BusinessValidationError(
                        "Il codice fiscale è obbligatorio per i clienti privati italiani"
                    )
            elif effective_client_type in ("company", "freelancer", "pa"):
                # Azienda/Freelancer/PA: entrambi obbligatori per clienti italiani
                if is_italian:
                    if not self.vat_number:
                        raise BusinessValidationError(
                            f"La Partita IVA è obbligatoria per i clienti di tipo '{effective_client_type}'"
                        )
                    if not self.fiscal_code:
                        raise BusinessValidationError(
                            f"Il codice fiscale è obbligatorio per i clienti di tipo '{effective_client_type}'"
                        )

        # ----------------------------------------------------------------
        # Validazione coerenza campi - con supporto per Partial Updates
        # ----------------------------------------------------------------
        
        # 1. Se sdi_code è "0000000", pec è obbligatorio
        if self.sdi_code == "0000000":
            if field_is_relevant("sdi_code") or field_is_relevant("pec"):
                if not self.pec:
                    raise BusinessValidationError(
                        "Quando il codice SDI è '0000000' (PEC), "
                        "l'indirizzo PEC è obbligatorio"
                    )
        
        # 2. Se vat_exemption è True, vat_exemption_code è obbligatorio
        if self.vat_exemption is True:
            if field_is_relevant("vat_exemption") or field_is_relevant("vat_exemption_code"):
                if not self.vat_exemption_code:
                    raise BusinessValidationError(
                        "Quando il cliente è esente IVA, il codice natura "
                        "esenzione è obbligatorio"
                    )
        
        # 3. Se split_payment è True, il cliente deve essere di tipo non 'private'
        if self.split_payment is True:
            if field_is_relevant("split_payment") or field_is_relevant("client_type"):
                if effective_client_type == "private":
                    raise BusinessValidationError(
                        "Lo split payment si applica solo a enti/aziende "
                        "(client_type: company, freelancer, pa)"
                    )
        
        # 4. Log warning se is_foreign=True ma country_code è "IT" o None
        if self.is_foreign is True and self.country_code in ("IT", None):
            logger.warning(
                "Cliente configurato come estero (is_foreign=True) "
                "ma con country_code '%s'",
                self.country_code
            )
        
        # 5. Se is_foreign è True e sdi_code non specificato, usa "XXXXXXX"
        if self.is_foreign is True and not self.sdi_code:
            self.sdi_code = "XXXXXXX"
        
        # 6. Validazione ZIP code rigorosa - SOLO per clienti italiani
        if self.zip_code and field_is_relevant("zip_code") and is_italian:
            if not re.match(r"^\d{5}$", self.zip_code):
                raise BusinessValidationError(
                    "Il CAP deve essere esattamente 5 cifre numeriche"
                )
        
        # 7. Log informativo per reverse charge
        if self.vat_exemption_code and self.vat_exemption_code.startswith("N6"):
            logger.info(
                "Cliente con regime reverse charge (codice: %s)",
                self.vat_exemption_code
            )
        
        return self


# -------------------------------------------------------------------
# Schemas Base
# -------------------------------------------------------------------
class ClientBase(ClientValidatorsMixin):
    """
    Schema base per i dati anagrafici del cliente.
    
    Include tutti i campi condivisi tra creazione e aggiornamento.
    
    Configurazione:
    - from_attributes=True: supporta conversione ORM → Pydantic
    - use_enum_values=True: l'ORM riceve stringhe invece di oggetti Enum
    """

    # Configurazione Pydantic per supportare ORM e Enum come stringhe
    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True  # L'ORM riceve le stringhe, non gli oggetti Enum
    )

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

    client_type: ClientType = Field(
        default=ClientType.PRIVATE,
        description="Tipo cliente: 'private', 'company', 'freelancer', 'pa'",
    )

    fiscal_code: Optional[str] = Field(
        None,
        max_length=16,
        description="Codice Fiscale italiano (16 char per PF, 11 cifre per aziende coincide con P.IVA)",
    )

    vat_number: Optional[str] = Field(
        None,
        max_length=11,
        description="Partita IVA italiana (11 cifre numeriche). Obbligatoria per company/freelancer/pa",
    )

    gdpr_consent: bool = Field(
        default=False,
        description="Il cliente ha dato il consenso al trattamento dati GDPR",
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
        max_length=3,  # Aggiornato da 2 a 3 per province estere
        description="Sigla provincia (2-3 caratteri)",
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

    # ------------------------------------------------------------
    # Dati Esteri
    # ------------------------------------------------------------
    country_code: str = Field(
        default="IT",  # Default corretto per clienti italiani
        max_length=2,
        description="Codice ISO 3166-1 alpha-2 del paese (default: IT)",
    )

    is_foreign: bool = Field(
        default=False,
        description="True se cliente estero, attiva logiche esenzione IVA",
    )

    # ------------------------------------------------------------
    # Dati Fatturazione Elettronica (SDI)
    # ------------------------------------------------------------
    sdi_code: Optional[str] = Field(
        None,
        max_length=7,
        description="Codice Destinatario SDI (7 caratteri). '0000000' per PEC, 'XXXXXXX' per esteri",
    )

    pec: Optional[EmailStr] = Field(
        None,
        max_length=255,
        description="PEC per fatturazione elettronica",
    )

    # ------------------------------------------------------------
    # Regime Fiscale - Usa Enum nativamente
    # ------------------------------------------------------------
    vat_regime: Optional[VatRegime] = Field(
        None,
        description="Regime fiscale: RF01=Ordinario, RF02=Minimi, RF04=Agricoltura, RF19=Forfettario",
    )

    # ------------------------------------------------------------
    # Regime IVA / Esenzione - Usa Enum nativamente
    # ------------------------------------------------------------
    vat_exemption: bool = Field(
        default=False,
        description="True se il cliente è esente IVA",
    )

    vat_exemption_code: Optional[VatExemptionCode] = Field(
        None,
        description="Codice natura esenzione: N1, N2, N2.1, N2.2, N3, N3.1, N3.5, N4, N5, N6, N6.1, N6.9, N7",
    )

    vat_exemption_reason: Optional[str] = Field(
        None,
        max_length=255,
        description="Descrizione testuale del motivo esenzione",
    )

    # ------------------------------------------------------------
    # Regime Pagamento Speciale
    # ------------------------------------------------------------
    split_payment: bool = Field(
        default=False,
        description="True per enti pubblici soggetti a split payment",
    )

    # ------------------------------------------------------------
    # Aliquota IVA Predefinita (FEAT 1)
    # ------------------------------------------------------------
    default_vat_rate: float = Field(
        default=22.00,
        ge=0,
        le=100,
        description="Aliquota IVA predefinita del cliente (default 22%)",
    )

    # ------------------------------------------------------------
    # Condizioni Pagamento Predefinite (FEAT 2)
    # ------------------------------------------------------------
    payment_terms_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Giorni per la scadenza fattura dalla data emissione (default 30)",
    )

    payment_method_default: Optional[PaymentMethod] = Field(
        None,
        description="Metodo di pagamento predefinito: cash, pos, bank_transfer, check, other",
    )

    # ------------------------------------------------------------
    # Sconto Predefinito Cliente (FEAT 3)
    # ------------------------------------------------------------
    default_discount_percent: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="Sconto predefinito percentuale (0-100). Es: 10.00 = 10% di sconto",
    )

    # ------------------------------------------------------------
    # Indirizzo Sede Legale (FEAT 5)
    # ------------------------------------------------------------
    # I campi address, city, zip_code, province rappresentano la SEDE LEGALE
    # I campi billing_* rappresentano la SEDE DI FATTURAZIONE (opzionali)

    # ------------------------------------------------------------
    # Indirizzo Sede di Fatturazione (FEAT 5)
    # ------------------------------------------------------------
    billing_address: Optional[str] = Field(
        None,
        max_length=255,
        description="Indirizzo sede di fatturazione (se diverso dalla sede legale)",
    )

    billing_city: Optional[str] = Field(
        None,
        max_length=100,
        description="Città sede di fatturazione",
    )

    billing_zip_code: Optional[str] = Field(
        None,
        max_length=10,
        description="CAP sede di fatturazione",
    )

    billing_province: Optional[str] = Field(
        None,
        max_length=3,
        description="Sigla provincia sede di fatturazione (2-3 caratteri)",
    )

    # ------------------------------------------------------------
    # Fido Commerciale (FEAT 7)
    # ------------------------------------------------------------
    credit_limit: Optional[float] = Field(
        None,
        ge=0,
        description="Fido massimo accordato al cliente. None = nessun limite",
    )

    credit_limit_action: str = Field(
        default="warn",
        description="Azione se superato fido: 'block' blocca fattura, 'warn' avvisa",
    )


# -------------------------------------------------------------------
# Schemas per Creazione
# -------------------------------------------------------------------
class ClientCreate(ClientBase):
    """
    Schema per la creazione di un nuovo cliente.
    
    Tutti i campi sono opzionali tranne name.
    
    Nota: ClientCreate estende ClientBase per permettere al mixin di
    distinguere tra CREATE e UPDATE tramite isinstance().
    """

    pass




# -------------------------------------------------------------------
# Schemas per Aggiornamento
# -------------------------------------------------------------------
class ClientUpdate(ClientValidatorsMixin):
    """
    Schema per l'aggiornamento di un cliente esistente.
    
    Tutti i campi sono opzionali per supportare update parziali (PATCH).
    Usa model_fields_set per determinare quali campi sono stati effettivamente
    inviati nel payload.
    
    Nota: model_config include use_enum_values per la validazione Enum.
    """
    
    # Configurazione con use_enum_values per supportare Enum
    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True
    )

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

    client_type: Optional[ClientType] = Field(
        None,
        description="Tipo cliente: 'private', 'company', 'freelancer', 'pa'",
    )

    fiscal_code: Optional[str] = Field(
        None,
        max_length=16,
        description="Codice Fiscale italiano",
    )

    vat_number: Optional[str] = Field(
        None,
        max_length=11,
        description="Partita IVA italiana (11 cifre numeriche)",
    )

    gdpr_consent: Optional[bool] = Field(
        None,
        description="Consenso GDPR del cliente",
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
        max_length=3,  # Aggiornato da 2 a 3 per province estere
        description="Sigla provincia (2-3 caratteri)",
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

    # ------------------------------------------------------------
    # Dati Esteri
    # ------------------------------------------------------------
    country_code: Optional[str] = Field(
        None,
        max_length=2,
        description="Codice ISO 3166-1 alpha-2 del paese",
    )

    is_foreign: Optional[bool] = Field(
        None,
        description="True se cliente estero",
    )

    # ------------------------------------------------------------
    # Dati Fatturazione Elettronica (SDI)
    # ------------------------------------------------------------
    sdi_code: Optional[str] = Field(
        None,
        max_length=7,
        description="Codice Destinatario SDI",
    )

    pec: Optional[EmailStr] = Field(
        None,
        max_length=255,
        description="PEC per fatturazione elettronica",
    )

    # ------------------------------------------------------------
    # Regime Fiscale - Usa Enum nativamente
    # ------------------------------------------------------------
    vat_regime: Optional[VatRegime] = Field(
        None,
        description="Regime fiscale",
    )

    # ------------------------------------------------------------
    # Regime IVA / Esenzione - Usa Enum nativamente
    # ------------------------------------------------------------
    vat_exemption: Optional[bool] = Field(
        None,
        description="True se il cliente è esente IVA",
    )

    vat_exemption_code: Optional[VatExemptionCode] = Field(
        None,
        description="Codice natura esenzione",
    )

    vat_exemption_reason: Optional[str] = Field(
        None,
        max_length=255,
        description="Descrizione motivo esenzione",
    )

    # ------------------------------------------------------------
    # Regime Pagamento Speciale
    # ------------------------------------------------------------
    split_payment: Optional[bool] = Field(
        None,
        description="True per enti pubblici soggetti a split payment",
    )

    # ------------------------------------------------------------
    # Aliquota IVA Predefinita (FEAT 1)
    # ------------------------------------------------------------
    default_vat_rate: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="Aliquota IVA predefinita del cliente",
    )

    # ------------------------------------------------------------
    # Condizioni Pagamento Predefinite (FEAT 2)
    # ------------------------------------------------------------
    payment_terms_days: Optional[int] = Field(
        None,
        ge=1,
        le=365,
        description="Giorni per la scadenza fattura dalla data emissione",
    )

    payment_method_default: Optional[PaymentMethod] = Field(
        None,
        description="Metodo di pagamento predefinito",
    )

    # ------------------------------------------------------------
    # Sconto Predefinito Cliente (FEAT 3)
    # ------------------------------------------------------------
    default_discount_percent: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="Sconto predefinito percentuale (0-100)",
    )

    # ------------------------------------------------------------
    # Indirizzo Sede di Fatturazione (FEAT 5)
    # ------------------------------------------------------------
    billing_address: Optional[str] = Field(
        None,
        max_length=255,
        description="Indirizzo sede di fatturazione",
    )

    billing_city: Optional[str] = Field(
        None,
        max_length=100,
        description="Città sede di fatturazione",
    )

    billing_zip_code: Optional[str] = Field(
        None,
        max_length=10,
        description="CAP sede di fatturazione",
    )

    billing_province: Optional[str] = Field(
        None,
        max_length=3,
        description="Sigla provincia sede di fatturazione",
    )

    # ------------------------------------------------------------
    # Fido Commerciale (FEAT 7)
    # ------------------------------------------------------------
    credit_limit: Optional[float] = Field(
        None,
        ge=0,
        description="Fido massimo accordato al cliente",
    )

    credit_limit_action: Optional[str] = Field(
        None,
        description="Azione se superato fido: 'block' o 'warn'",
    )


# -------------------------------------------------------------------
# Schemas per Lettura (API Response)
# -------------------------------------------------------------------
class ClientRead(ClientBase):
    """
    Schema per la risposta API che include i campi di sistema.
    
    Include id, created_at, updated_at, gdpr_consent_date, gdpr_withdraw_date
    e il campo calcolato is_company per retrocompatibilità.
    
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

    gdpr_consent_date: Optional[datetime.datetime] = Field(
        None,
        description="Data/ora in cui il consenso GDPR è stato dato",
    )

    gdpr_withdraw_date: Optional[datetime.datetime] = Field(
        None,
        description="Data/ora in cui il consenso GDPR è stato revocato",
    )

    @computed_field
    @property
    def is_company(self) -> bool:
        """
        Campo calcolato per retrocompatibilità.
        
        True se client_type è 'company', 'freelancer' o 'pa'.
        """
        ct = self.client_type
        if isinstance(ct, ClientType):
            return ct in (ClientType.COMPANY, ClientType.FREELANCER, ClientType.PA)
        # Gestisce il caso in cui use_enum_values=True ha già convertito in stringa
        return ct in ("company", "freelancer", "pa")


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
