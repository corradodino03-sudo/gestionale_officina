"""
Modulo di sicurezza per autenticazione JWT
Progetto: Garage Manager (Gestionale Officina)

Funzioni per hashing password e gestione token JWT.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.schemas.token import TokenPayload

# Context per hashing password
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Hasha una password in chiaro.
    
    Args:
        password: Password in chiaro
        
    Returns:
        Password hashata
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica una password in chiaro contro una hashata.
    
    Args:
        plain_password: Password in chiaro
        hashed_password: Password hashata
        
    Returns:
        True se la password corrisponde, False altrimenti
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: str, role: str) -> str:
    """
    Crea un token di accesso JWT.
    
    Args:
        user_id: ID dell'utente
        role: Ruolo dell'utente
        
    Returns:
        Token JWT codificato
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    
    payload = {
        "sub": user_id,
        "role": role,
        "exp": expire,
        "type": "access",
    }
    
    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(user_id: str, role: str) -> str:
    """
    Crea un token di refresh JWT.
    
    Args:
        user_id: ID dell'utente
        role: Ruolo dell'utente
        
    Returns:
        Token JWT codificato
    """
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    
    payload = {
        "sub": user_id,
        "role": role,
        "exp": expire,
        "type": "refresh",
    }
    
    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> TokenPayload:
    """
    Decodifica e valida un token JWT.
    
    Args:
        token: Token JWT da decodificare
        
    Returns:
        TokenPayload con i dati del token
        
    Raises:
        HTTPException: Se il token è invalido o scaduto
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        
        token_data = TokenPayload(
            sub=payload.get("sub"),
            role=payload.get("role"),
            exp=datetime.fromisoformat(str(payload.get("exp"))),
            type=payload.get("type"),
        )
        
        if not token_data.sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalido: missing subject",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return token_data
        
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token invalido o scaduto: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Export delle funzioni
__all__ = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
]
