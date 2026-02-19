"""
Eccezioni Custom per l'applicazione.
Progetto: Garage Manager (Gestionale Officina)

Definisce eccezioni specifiche del dominio per una gestione
centralizzata degli errori.

NOTA: BusinessValidationError è volutamente distinta da pydantic.ValidationError.
- pydantic.ValidationError: errori di formato/tipo nei dati di input (gestiti da FastAPI → 422)
- BusinessValidationError: violazioni delle regole di business logic (gestiti dal nostro handler → 422)
"""

__all__ = [
    "AppException",
    "NotFoundError",
    "DuplicateError",
    "BusinessValidationError",
    "ConflictError",
]


class AppException(Exception):
    """
    Base exception per l'applicazione.
    
    Tutte le eccezioni custom ereditano da questa classe base.
    """

    def __init__(self, detail: str) -> None:
        """
        Inizializza l'eccezione.
        
        Args:
            detail: Messaggio di errore dettagliato
        """
        self.detail = detail
        super().__init__(detail)


class NotFoundError(AppException):
    """
    Eccezione sollevata quando una risorsa non viene trovata.
    
    Utilizzata quando un'entità cercata non esiste nel database.
    """

    def __init__(self, detail: str = "Risorsa non trovata") -> None:
        """
        Inizializza l'eccezione NotFoundError.
        
        Args:
            detail: Messaggio di errore (default: "Risorsa non trovata")
        """
        super().__init__(detail)


class DuplicateError(AppException):
    """
    Eccezione sollevata quando si tenta di creare una risorsa duplicata.
    
    Utilizzata per violazioni di vincoli unique (es. codice fiscale già esistente).
    """

    def __init__(self, detail: str = "Risorsa già esistente") -> None:
        """
        Inizializza l'eccezione DuplicateError.
        
        Args:
            detail: Messaggio di errore (default: "Risorsa già esistente")
        """
        super().__init__(detail)


class BusinessValidationError(AppException):
    """
    Eccezione sollevata per violazioni delle regole di business logic.
    
    NON confondere con pydantic.ValidationError che gestisce
    la validazione dello schema/formato dei dati in input.
    
    Esempi di utilizzo:
        - "Il veicolo non appartiene al cliente selezionato"
        - "Solo ordini in bozza possono essere eliminati"
        - "Giacenza insufficiente per lo scarico richiesto"
        - "Transizione di stato non consentita"
    """

    def __init__(self, detail: str = "Validazione dati fallita") -> None:
        """
        Inizializza l'eccezione BusinessValidationError.
        
        Args:
            detail: Messaggio di errore (default: "Validazione dati fallita")
        """
        super().__init__(detail)


class ConflictError(AppException):
    """
    Eccezione sollevata per conflitti di stato.
    
    Utilizzata quando un'operazione non può essere eseguita
    a causa dello stato corrente della risorsa.
    """

    def __init__(self, detail: str = "Conflitto di stato") -> None:
        """
        Inizializza l'eccezione ConflictError.
        
        Args:
            detail: Messaggio di errore (default: "Conflitto di stato")
        """
        super().__init__(detail)
