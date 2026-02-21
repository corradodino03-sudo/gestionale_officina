"""
Dependency Injection per autenticazione
Progetto: Garage Manager (Gestionale Officina)

Funzioni di dependency injection per autenticazione e autorizzazione.
"""

from typing import Annotated, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User

# OAuth2 scheme - estrae il token dall'header Authorization
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,
)


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency per ottenere l'utente corrente dal token JWT.
    
    Args:
        token: Token JWT estratto dall'header Authorization
        db: Sessione database
        
    Returns:
        L'utente corrente
        
    Raises:
        HTTPException 401: Se il token è invalido, scaduto o l'utente non è attivo
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token di autenticazione non fornito",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Decodifica il token
    token_data = decode_token(token)
    
    # Verifica che sia un token di accesso
    if token_data.type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token di refresh non valido per questa operazione",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Carica l'utente dal database
    try:
        user_id = UUID(token_data.sub)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ID utente invalido nel token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utente non trovato",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verifica che l'utente sia attivo
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utente disattivato",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


def require_role(*allowed_roles: str):
    """
    Factory function per creare una dependency che verifica il ruolo.
    
    Args:
        allowed_roles: Ruoli permessi per l'endpoint
        
    Returns:
        Dependency che verifica il ruolo dell'utente
        
    Example:
        @router.post("/admin-only")
        async def admin_endpoint(admin: User = Depends(require_role("admin"))):
            ...
            
        @router.post("/manage-users")
        async def manage_users(
            user: User = Depends(require_role("admin", "manager"))
        ):
            ...
    """
    async def role_checker(
        current_user: Annotated[User, Depends(get_current_user)]
    ) -> User:
        """
        Verifica che l'utente abbia uno dei ruoli permessi.
        
        Args:
            current_user: Utente corrente dalla dependency get_current_user
            
        Returns:
            L'utente corrente se autorizzato
            
        Raises:
            HTTPException 403: Se l'utente non ha i permessi necessari
        """
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Accesso negato. Ruolo richiesto: {', '.join(allowed_roles)}",
            )
        return current_user
    
    return role_checker


# Type aliases per uso comune
CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_role("admin"))]
ManagerUser = Annotated[User, Depends(require_role("admin", "manager"))]


# Export
__all__ = [
    "get_current_user",
    "require_role",
    "oauth2_scheme",
    "CurrentUser",
    "AdminUser",
    "ManagerUser",
]
