"""
Schemas Pydantic per l'autenticazione JWT
Progetto: Garage Manager (Gestionale Officina)

Schemas per token JWT e relativi payload.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    """
    Schema per la risposta contenente i token JWT.
    
    Attributes:
        access_token: Token di accesso JWT
        refresh_token: Token di refresh JWT
        token_type: Tipo di token (default: bearer)
    """

    access_token: str = Field(..., description="Token di accesso JWT")
    refresh_token: str = Field(..., description="Token di refresh JWT")
    token_type: str = Field(
        default="bearer",
        description="Tipo di token",
    )


class TokenRefresh(BaseModel):
    """
    Schema per la richiesta di refresh token.
    
    Attributes:
        refresh_token: Token di refresh JWT
    """

    refresh_token: str = Field(..., description="Token di refresh JWT")


class TokenPayload(BaseModel):
    """
    Schema per il payload contenuto nei token JWT.
    
    Attributes:
        sub: Subject - ID dell'utente come stringa
        role: Ruolo dell'utente
        exp: Expiration - Data/ora di scadenza
        type: Tipo di token ("access" o "refresh")
    """

    sub: str = Field(..., description="ID utente")
    role: str = Field(..., description="Ruolo dell'utente")
    exp: datetime = Field(..., description="Data/ora di scadenza")
    type: str = Field(..., description="Tipo di token (access/refresh)")


# Export degli schemas
__all__ = [
    "TokenResponse",
    "TokenRefresh",
    "TokenPayload",
]
