"""
Servizio per l'autenticazione
Progetto: Garage Manager (Gestionale Officina)

Business logic per registrazione, login e refresh token.
"""

from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateError, NotFoundError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.models.user import User, UserRole
from app.schemas.token import TokenResponse
from app.schemas.user import UserCreate, UserLogin


class AuthService:
    """Servizio per la gestione dell'autenticazione."""

    async def register(self, db: AsyncSession, data: UserCreate) -> User:
        """
        Registra un nuovo utente nel sistema.
        
        Args:
            db: Sessione database
            data: Dati per la creazione dell'utente
            
        Returns:
            L'utente creato
            
        Raises:
            DuplicateError: Se l'email è già registrata
        """
        # Verifica email non duplicata
        result = await db.execute(
            select(User).where(User.email == data.email)
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            raise DuplicateError(f"L'email {data.email} è già registrata")
        
        # Verifica se è il primo utente nel sistema
        count_result = await db.execute(select(func.count(User.id)))
        user_count = count_result.scalar()
        
        # Se è il primo utente, forza il ruolo admin
        role = data.role
        if user_count == 0:
            role = UserRole.ADMIN
        
        # Crea l'utente
        user = User(
            email=data.email,
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
            role=role.value if isinstance(role, UserRole) else role,
        )
        
        db.add(user)
        await db.flush()
        await db.refresh(user)
        
        return user

    async def login(self, db: AsyncSession, data: UserLogin) -> TokenResponse:
        """
        Autentica un utente e restituisce i token JWT.
        
        Args:
            db: Sessione database
            data: Credenziali dell'utente
            
        Returns:
            TokenResponse con access e refresh token
            
        Raises:
            HTTPException 401: Se le credenziali sono invalide
        """
        # Cerca utente per email
        result = await db.execute(
            select(User).where(User.email == data.email)
        )
        user = result.scalar_one_or_none()
        
        # Verifica utente esista
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email o password non corretti",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Verifica password
        if not verify_password(data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email o password non corretti",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Verifica utente attivo
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Utente disattivato",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Genera token
        access_token = create_access_token(str(user.id), user.role)
        refresh_token = create_refresh_token(str(user.id), user.role)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
        )

    async def refresh(
        self, db: AsyncSession, refresh_token: str
    ) -> TokenResponse:
        """
        Aggiorna i token JWT usando un refresh token.
        
        Args:
            db: Sessione database
            refresh_token: Token di refresh
            
        Returns:
            TokenResponse con nuovi access e refresh token
            
        Raises:
            HTTPException 401: Se il refresh token è invalido
        """
        from app.core.security import decode_token
        
        # Decodifica il refresh token
        token_data = decode_token(refresh_token)
        
        # Verifica che sia un token di refresh
        if token_data.type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token di accesso non valido per il refresh",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Carica utente
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
        
        # Verifica utente attivo
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Utente disattivato",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Genera nuovi token
        access_token = create_access_token(str(user.id), user.role)
        new_refresh_token = create_refresh_token(str(user.id), user.role)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
        )

    async def get_user_by_id(self, db: AsyncSession, user_id: UUID) -> User:
        """
        Ottiene un utente per ID.
        
        Args:
            db: Sessione database
            user_id: ID dell'utente
            
        Returns:
            L'utente trovato
            
        Raises:
            NotFoundError: Se l'utente non esiste
        """
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise NotFoundError(f"Utente con ID {user_id} non trovato")
        
        return user


def get_auth_service() -> AuthService:
    """
    Factory per ottenere un'istanza del servizio di autenticazione.
    
    Returns:
        Istanza di AuthService
    """
    return AuthService()


# Export
__all__ = [
    "AuthService",
    "get_auth_service",
]
