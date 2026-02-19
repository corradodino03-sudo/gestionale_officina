"""
Configurazione applicazione - Settings
Progetto: Garage Manager (Gestionale Officina)

Definisce le impostazioni dell'applicazione caricate da variabili d'ambiente.
"""

from typing import List

from pydantic import Field
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

    app_env: str = Field(
        default="development",
        description="Ambiente di esecuzione (development | production)",
    )

    debug: bool = Field(
        default=True,
        description="Modalità debug",
    )

    secret_key: str = Field(
        default="changeme-in-production",
        description="Chiave segreta per sessioni/token",
    )

    backend_port: int = Field(
        default=8000,
        description="Porta backend",
    )

    # ------------------------------------------------------------
    # Configurazione CORS
    # ------------------------------------------------------------
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        description="Origini CORS permesse",
    )

    # ------------------------------------------------------------
    # Configurazione Logging
    # ------------------------------------------------------------
    log_level: str = Field(
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


# Istanza globale delle impostazioni
settings = Settings()
