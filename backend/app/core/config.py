"""
Configurazione applicazione - Settings
Progetto: Garage Manager (Gestionale Officina)

Definisce le impostazioni dell'applicazione caricate da variabili d'ambiente.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configurazione applicazione.

    Carica le impostazioni da variabili d'ambiente.
    Valori di default adatti per sviluppo locale.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
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
        default=True,
        description="Modalità debug",
    )

    secret_key: str = Field(
        default="changeme-in-production",
        description="Chiave segreta per sessioni/token",
    )

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if v == "changeme-in-production":
            import logging

            logging.getLogger(__name__).warning(
                "⚠️  SECRET_KEY non impostata — usa un valore sicuro in produzione"
            )
        return v

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

    invoice_tax_id: str = Field(
        default="",
        description="Partita IVA",
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
        default="./backups",
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


# Istanza globale per compatibilità con import diretti
settings = get_settings()
