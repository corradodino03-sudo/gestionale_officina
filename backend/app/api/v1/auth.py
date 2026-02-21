"""
Router per l'autenticazione
Progetto: Garage Manager (Gestionale Officina)

Endpoints per registrazione, login, refresh token e profilo utente.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, oauth2_scheme
from app.core.security import decode_token
from app.models.user import User
from app.schemas.token import TokenRefresh, TokenResponse
from app.schemas.user import UserCreate, UserLogin, UserResponse
from app.services.auth_service import AuthService, get_auth_service

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


async def get_db_session() -> AsyncSession:
    """Dependency per ottenere la sessione database."""
    async for session in get_db():
        yield session


async def get_service() -> AuthService:
    """Dependency per ottenere il servizio di autenticazione."""
    return get_auth_service()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registra un nuovo utente",
)
async def register(
    data: UserCreate,
    db: AsyncSession = Depends(get_db_session),
    service: AuthService = Depends(get_service),
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    """
    Registra un nuovo utente nel sistema.
    
    Se esistono già utenti nel DB:
    - Richiede autenticazione
    - Verifica che l'utente corrente sia admin
    
    Se NON esistono utenti (primo utente):
    - Permette registrazione libera
    - Forza automaticamente il ruolo admin
    """
    # Verifica se ci sono già utenti nel sistema
    count_result = await db.execute(select(func.count(User.id)))
    user_count = count_result.scalar()
    
    if user_count > 0:
        # Se ci sono utenti, richiedi autenticazione
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Autenticazione richiesta per registrare nuovi utenti",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Estrai e valida il token
        token = authorization.replace("Bearer ", "")
        
        try:
            token_data = decode_token(token)
            if token_data.type != "access":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token di accesso richiesto",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalido",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Carica l'utente corrente
        from uuid import UUID
        
        try:
            user_id = UUID(token_data.sub)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="ID utente invalido nel token",
            )
        
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        current_user = result.scalar_one_or_none()
        
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Utente non trovato",
            )
        
        # Verifica che sia admin
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo gli admin possono registrare nuovi utenti",
            )
        
        # Se è admin, usa il ruolo specificato nella richiesta
        pass  # Continua con la registrazione normale
    
    # Se è il primo utente, il serviceforcerà il ruolo admin
    user = await service.register(db, data)
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Effettua il login",
)
async def login(
    data: UserLogin,
    db: AsyncSession = Depends(get_db_session),
    service: AuthService = Depends(get_service),
):
    """
    Effettua il login e restituisce i token JWT.
    
    Args:
        data: Credenziali dell'utente
        
    Returns:
        TokenResponse con access_token e refresh_token
    """
    return await service.login(db, data)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Aggiorna i token",
)
async def refresh(
    data: TokenRefresh,
    db: AsyncSession = Depends(get_db_session),
    service: AuthService = Depends(get_service),
):
    """
    Aggiorna i token JWT usando un refresh token.
    
    Args:
        data: Refresh token
        
    Returns:
        TokenResponse con nuovi access_token e refresh_token
    """
    return await service.refresh(db, data.refresh_token)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Ottieni il profilo utente corrente",
)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """
    Restituisce i dati dell'utente corrente.
    
    Requires:
        Token JWT valido
        
    Returns:
        Dati dell'utente corrente
    """
    return current_user


# Export
__all__ = ["router"]
