"""
Configurazione applicazione - Settings
Progetto: Garage Manager (Gestionale Officina)

Definisce le impostazioni dell'applicazione caricate da variabili d'ambiente.
"""


from __future__ import annotations
import logging
from functools import lru_cache
from typing import Literal, Optional
from decimal import Decimal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configurazione applicazione.

    Carica le impostazioni da variabili d'ambiente.
    Valori di default adatti per sviluppo locale.

    Per ottenere un'istanza singleton:
    - In FastAPI: usa `Depends(get_settings)` per Dependency Injection
    - Altrove: usa `get_settings()` direttamente
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        frozen=True,  # CFG-2: Impedisce mutazioni accidentali dopo la creazione
    )

    # ------------------------------------------------------------
    # Configurazione Database
    # ------------------------------------------------------------
    database_url: str = Field(
        default="postgresql+asyncpg://garage_user:changeme@localhost:5432/garage_db",
        description="URL connessione database PostgreSQL (formato async)",
    )

    db_pool_size: int = Field(
        default=5,
        description="Numero connessioni permanenti nel pool",
    )

    db_max_overflow: int = Field(
        default=10,
        description="Connessioni extra temporanee oltre pool_size",
    )

    # ------------------------------------------------------------
    # Configurazione Applicazione
    # ------------------------------------------------------------
    app_name: str = Field(
        default="Garage Manager",
        description="Nome applicazione",
    )

    app_version: str = Field(
        default="1.0.0",
        description="Versione applicazione",
    )

    app_env: Literal["development", "production", "testing"] = Field(
        default="development",
        description="Ambiente di esecuzione (development | production | testing)",
    )

    debug: bool = Field(
        default=False,  # SEC-2: Default sicuro per produzione
        description="Modalità debug",
    )

    secret_key: str = Field(
        default="changeme-in-production",
        description="Chiave segreta per sessioni/token",
    )

    access_token_expire_minutes: int = Field(
        default=30,
        description="Minuti di validità dell'access token JWT",
    )

    refresh_token_expire_days: int = Field(
        default=7,
        description="Giorni di validità del refresh token JWT",
    )

    jwt_algorithm: str = Field(
        default="HS256",
        description="Algoritmo per firma JWT",
    )

    backend_port: int = Field(
        default=8000,
        description="Porta backend",
    )

    # ------------------------------------------------------------
    # Configurazione CORS
    # ------------------------------------------------------------
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        description="Origini CORS permesse",
    )

    # ------------------------------------------------------------
    # Configurazione Logging
    # ------------------------------------------------------------
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Livello logging",
    )

    # ------------------------------------------------------------
    # Configurazione Fatturazione (MVP)
    # ------------------------------------------------------------
    invoice_company_name: str = Field(
        default="Tua Officina S.r.l.",
        description="Ragione sociale per fatture",
    )

    invoice_iban: str = Field(
        default="",
        description="IBAN per pagamenti con bonifico",
    )

    invoice_pec: str = Field(
        default="",
        description="PEC dell'officina",
    )

    invoice_sdi_code: str = Field(
        default="",
        description="Codice SDI dell'officina",
    )

    invoice_logo_path: Optional[str] = Field(
        default=None,
        description="Path relativo al logo (es. ./static/logo.png)",
    )

    invoice_vat_number: str = Field(
        default="",
        description="Partita IVA officina (formato: IT + 11 cifre, es. IT01234567890)",
    )

    invoice_rea_number: Optional[str] = Field(
        default=None,
        description="Numero REA (es. MI-1234567)",
    )

    invoice_capital: Optional[str] = Field(
        default=None,
        description="Capitale sociale (per S.r.l.)",
    )

    stamp_duty_amount: Decimal = Field(
        default=Decimal("2.00"),
        description="Importo marca da bollo",
    )

    stamp_duty_threshold: Decimal = Field(
        default=Decimal("77.47"),
        description="Soglia per marca da bollo",
    )

    invoice_address: str = Field(
        default="",
        description="Indirizzo per fatture",
    )

    invoice_phone: str = Field(
        default="",
        description="Telefono per fatture",
    )

    invoice_email: str = Field(
        default="",
        description="Email per fatture",
    )

    # ------------------------------------------------------------
    # Configurazione Backup
    # ------------------------------------------------------------
    backup_enabled: bool = Field(
        default=False,
        description="Abilita backup automatico",
    )

    backup_path: str = Field(
        default="/var/lib/garage-manager/backups",  # CFG-6: Percorso assoluto
        description="Percorso cartella backup",
    )

    backup_retention_days: int = Field(
        default=30,
        description="Giorni retention backup",
    )

    @property
    def is_production(self) -> bool:
        """Verifica se l'applicazione è in produzione."""
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        """Verifica se l'applicazione è in sviluppo."""
        return self.app_env == "development"

    # ------------------------------------------------------------
    # Validatori
    # ------------------------------------------------------------

    @field_validator("invoice_vat_number")
    @classmethod
    def validate_invoice_vat_number(cls, v: str) -> str:
        """Valida il formato della partita IVA (IT + 11 cifre)."""
        if v and not v.strip():
            return v
        if v and not v.upper().startswith("IT"):
            raise ValueError("La partita IVA deve iniziare con 'IT'")
        if v and len(v) != 13:
            raise ValueError("La partita IVA deve avere 13 caratteri (IT + 11 cifre)")
        if v and not v[2:].isdigit():
            raise ValueError("La partita IVA deve contenere 11 cifre dopo 'IT'")
        return v.upper()

    @field_validator("invoice_iban")
    @classmethod
    def validate_invoice_iban(cls, v: str) -> str:
        """Valida il formato dell'IBAN italiano."""
        if v and not v.strip():
            return v
        if v and not v.upper().startswith("IT"):
            raise ValueError("L'IBAN italiano deve iniziare con 'IT'")
        if v and len(v) != 27:
            raise ValueError("L'IBAN italiano deve avere 27 caratteri")
        return v.upper()

    @field_validator("stamp_duty_amount", "stamp_duty_threshold", mode="before")
    @classmethod
    def convert_decimal_from_string(cls, v) -> Decimal:
        """Gestisce input con virgola convertendolo in punto."""
        if v is None:
            return v
        if isinstance(v, str):
            # Sostituisci virgola con punto
            v = v.replace(",", ".")
        return Decimal(str(v))

    @field_validator("backup_path")
    @classmethod
    def validate_backup_path(cls, v: str) -> str:
        """Emette warning se il path è relativo."""
        if v and not v.startswith("/"):
            logging.getLogger(__name__).warning(
                f"⚠️  backup_path è relativo: {v}. Usa un percorso assoluto in produzione."
            )
        return v

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        """
        SEC-1: Validazione settings obbligatori in produzione.
        CFG-3: Validazione CORS in produzione.
        """
        if self.app_env != "production":
            return self

        errors = []

        # SEC-1: Blocco credenziali di default
        if self.secret_key == "changeme-in-production" or len(self.secret_key) < 32:
            errors.append("- secret_key: deve essere cambiato e avere almeno 32 caratteri")

        if "changeme" in self.database_url.lower():
            errors.append("- database_url: non deve contenere 'changeme'")

        if not self.invoice_vat_number or not self.invoice_vat_number.strip():
            errors.append("- invoice_vat_number: obbligatorio in produzione")

        if self.debug:
            errors.append("- debug: deve essere False in produzione")

        # CFG-3: Validazione CORS in produzione
        for origin in self.cors_origins:
            if "localhost" in origin or "127.0.0.1" in origin:
                errors.append(
                    f"- cors_origins: l'origine '{origin}' non è consentita in produzione"
                )

        if errors:
            error_msg = "Errore di configurazione in produzione:\n" + "\n".join(errors)
            raise ValueError(error_msg)

        return self


@lru_cache()
def get_settings() -> Settings:
    """
    Restituisce l'istanza singleton delle impostazioni.

    Usa lru_cache per garantire che Settings() venga istanziato
    una sola volta e riutilizzato in tutta l'applicazione.
    In fase di test, usa get_settings.cache_clear() per resettare.

    Returns:
        Settings: Istanza delle impostazioni applicazione
    """
    return Settings()


# Istanza singleton delle impostazioni per uso diretto in modulo
settings = get_settings()
