"""
Eccezioni Custom per l'applicazione.
Progetto: Garage Manager (Gestionale Officina)

Definisce eccezioni specifiche del dominio per una gestione
centralizzata degli errori.

NOTA: BusinessValidationError è volutamente distinta da pydantic.ValidationError.
- pydantic.ValidationError: errori di formato/tipo nei dati di input (gestiti da FastAPI → 422)
- BusinessValidationError: violazioni delle regole di business logic (gestiti dal nostro handler → 422)
"""

from typing import Any, Dict, Optional

__all__ = [
    "AppException",
    "NotFoundError",
    "DuplicateError",
    "BusinessValidationError",
    "ValidationError",       # alias di BusinessValidationError
    "ConflictError",
    "AuthorizationError",
]


class AppException(Exception):
    """
    Base exception per l'applicazione.
    
    Tutte le eccezioni custom ereditano da questa classe base.
    
    Attributes:
        status_code: HTTP status code da restituire al client
        error_code: Identificativo univoco dell'errore per il frontend
        detail: Messaggio di errore leggibile per l'utente
        extra: Dizionario con dati aggiuntivi per il frontend
    """

    # Default values - overridden in subclasses
    status_code: int = 500
    error_code: str = "INTERNAL_SERVER_ERROR"

    def __init__(
        self,
        detail: str,
        error_code: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Inizializza l'eccezione.
        
        Args:
            detail: Messaggio di errore dettagliato
            error_code: Identificativo univoco (default: quello di classe)
            extra: Dati aggiuntivi da passare al frontend (default: None)
        """
        self.detail = detail
        # Use provided error_code or fall back to class-level default
        self.error_code = error_code if error_code is not None else self.error_code
        self.extra = extra if extra is not None else None
        self.status_code = self.__class__.status_code
        super().__init__(detail)


class NotFoundError(AppException):
    """
    Eccezione sollevata quando una risorsa non viene trovata.
    
    Utilizzata quando un'entità cercata non esiste nel database.
    """

    status_code: int = 404
    error_code: str = "RESOURCE_NOT_FOUND"

    def __init__(
        self,
        detail: str = "Risorsa non trovata",
        error_code: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Inizializza l'eccezione NotFoundError.
        
        Args:
            detail: Messaggio di errore (default: "Risorsa non trovata")
            error_code: Identificativo univoco (default: "RESOURCE_NOT_FOUND")
            extra: Dati aggiuntivi da passare al frontend (default: None)
        """
        super().__init__(detail, error_code, extra)


class DuplicateError(AppException):
    """
    Eccezione sollevata quando si tenta di creare una risorsa duplicata.
    
    Utilizzata per violazioni di vincoli unique (es. codice fiscale già esistente).
    """

    status_code: int = 409
    error_code: str = "DUPLICATE_RESOURCE"

    def __init__(
        self,
        detail: str = "Risorsa già esistente",
        error_code: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Inizializza l'eccezione DuplicateError.
        
        Args:
            detail: Messaggio di errore (default: "Risorsa già esistente")
            error_code: Identificativo univoco (default: "DUPLICATE_RESOURCE")
            extra: Dati aggiuntivi da passare al frontend (default: None)
        """
        super().__init__(detail, error_code, extra)


class BusinessValidationError(ValueError, AppException):
    """
    Eccezione sollevata per violazioni delle regole di business logic.
    
    Eredita da ValueError per essere catturata dai validatori Pydantic.
    
    NON confondere con pydantic.ValidationError che gestisce
    la validazione dello schema/formato dei dati in input.
    
    Esempi di utilizzo:
        - "Il veicolo non appartiene al cliente selezionato"
        - "Solo ordini in bozza possono essere eliminati"
        - "Giacenza insufficiente per lo scarico richiesto"
        - "Transizione di stato non consentita"
    """

    status_code: int = 422
    error_code: str = "BUSINESS_VALIDATION_ERROR"

    def __init__(
        self,
        detail: str = "Validazione dati fallita",
        error_code: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Inizializza l'eccezione BusinessValidationError.
        
        Args:
            detail: Messaggio di errore (default: "Validazione dati fallita")
            error_code: Identificativo univoco (default: "BUSINESS_VALIDATION_ERROR")
            extra: Dati aggiuntivi da passare al frontend (default: None)
        """
        # Chiama AppException.__init__ direttamente per evitare ValueError
        AppException.__init__(self, detail, error_code, extra)


# Alias per compatibilità
ValidationError = BusinessValidationError


class ConflictError(AppException):
    """
    Eccezione sollevata per conflitti di stato.
    
    Utilizzata quando un'operazione non può essere eseguita
    a causa dello stato corrente della risorsa.
    """

    status_code: int = 409
    error_code: str = "CONFLICT_STATE"

    def __init__(
        self,
        detail: str = "Conflitto di stato",
        error_code: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Inizializza l'eccezione ConflictError.
        
        Args:
            detail: Messaggio di errore (default: "Conflitto di stato")
            error_code: Identificativo univoco (default: "CONFLICT_STATE")
            extra: Dati aggiuntivi da passare al frontend (default: None)
        """
        super().__init__(detail, error_code, extra)


class AuthorizationError(AppException):
    """
    Eccezione sollevata per accesso non autorizzato.
    
    Utilizzata quando un utente tenta di accedere a una risorsa
    o eseguire un'operazione per cui non ha i permessi necessari.
    
    Esempi di utilizzo:
        - "Non hai i permessi per eliminare questo ordine"
        - "Solo gli amministratori possono accedere a questa risorsa"
    """

    status_code: int = 403
    error_code: str = "FORBIDDEN"

    def __init__(
        self,
        detail: str = "Accesso non autorizzato",
        error_code: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Inizializza l'eccezione AuthorizationError.
        
        Args:
            detail: Messaggio di errore (default: "Accesso non autorizzato")
            error_code: Identificativo univoco (default: "FORBIDDEN")
            extra: Dati aggiuntivi da passare al frontend (default: None)
        """
        super().__init__(detail, error_code, extra)
