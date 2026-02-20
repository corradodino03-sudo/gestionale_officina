from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.cash_register import (
    CashRegisterCloseCreate,
    CashRegisterCloseRead,
    CashRegisterSummary,
)
from app.services.cash_register_service import CashRegisterService

router = APIRouter(prefix="/cash-register", tags=["Chiusura Cassa"])

@router.get("/preview/{target_date}", response_model=CashRegisterSummary)
async def preview_cash_register(
    target_date: date,
    db: AsyncSession = Depends(get_db),
):
    """Anteprima dei totali di cassa per una data (non chiude la cassa)."""
    return await CashRegisterService.get_daily_summary(target_date, db)


@router.post("/close", response_model=CashRegisterCloseRead)
async def close_cash_register(
    data: CashRegisterCloseCreate,
    db: AsyncSession = Depends(get_db),
):
    """Chiude la cassa per una data specifica."""
    return await CashRegisterService.close_day(
        target_date=data.close_date,
        closed_by=data.closed_by,
        notes=data.notes,
        db=db,
    )


@router.get("/history", response_model=List[CashRegisterCloseRead])
async def get_cash_register_history(
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Recupera lo storico delle chiusure cassa."""
    return await CashRegisterService.get_history(from_date, to_date, db, skip, limit)


@router.get("/{target_date}", response_model=CashRegisterCloseRead)
async def get_cash_register_by_date(
    target_date: date,
    db: AsyncSession = Depends(get_db),
):
    """Recupera la chiusura cassa di una specifica data."""
    return await CashRegisterService.get_by_date(target_date, db)


@router.patch("/{target_date}/reconcile", response_model=CashRegisterCloseRead)
async def reconcile_cash_register(
    target_date: date,
    db: AsyncSession = Depends(get_db),
):
    """Segna la cassa di una data come riconciliata."""
    return await CashRegisterService.reconcile(target_date, db)
