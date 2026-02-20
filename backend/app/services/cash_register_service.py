from datetime import date
from decimal import Decimal
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessValidationError, NotFoundError
from app.models.invoice import Payment
from app.models.cash_register import CashRegisterClose
from app.schemas.cash_register import CashRegisterSummary

class CashRegisterService:
    @staticmethod
    async def get_daily_summary(target_date: date, db: AsyncSession) -> CashRegisterSummary:
        """Restituisce un'anteprima della cassa per la data specificata."""
        stmt = select(Payment).where(Payment.payment_date == target_date)
        result = await db.execute(stmt)
        payments = result.scalars().all()
        
        summary = CashRegisterSummary(
            close_date=target_date,
            total_cash=Decimal("0.00"),
            total_pos=Decimal("0.00"),
            total_bank_transfer=Decimal("0.00"),
            total_check=Decimal("0.00"),
            total_other=Decimal("0.00"),
            total_amount=Decimal("0.00"),
            payments_count=len(payments)
        )
        
        for p in payments:
            if p.payment_method == "cash":
                summary.total_cash += p.amount
            elif p.payment_method == "pos":
                summary.total_pos += p.amount
            elif p.payment_method == "bank_transfer":
                summary.total_bank_transfer += p.amount
            elif p.payment_method == "check":
                summary.total_check += p.amount
            else:
                summary.total_other += p.amount
            summary.total_amount += p.amount
            
        return summary
        
    @staticmethod
    async def close_day(
        target_date: date, closed_by: Optional[str], notes: Optional[str], db: AsyncSession
    ) -> CashRegisterClose:
        """Chiude la cassa calcolando i totali dei pagamenti della giornata."""
        stmt = select(CashRegisterClose).where(CashRegisterClose.close_date == target_date)
        res = await db.execute(stmt)
        if res.scalar_one_or_none():
            raise BusinessValidationError("Cassa già chiusa per questa data")
            
        summary = await CashRegisterService.get_daily_summary(target_date, db)
        
        close_record = CashRegisterClose(
            close_date=summary.close_date,
            closed_by=closed_by,
            notes=notes,
            total_cash=summary.total_cash,
            total_pos=summary.total_pos,
            total_bank_transfer=summary.total_bank_transfer,
            total_check=summary.total_check,
            total_other=summary.total_other,
            total_amount=summary.total_amount,
            payments_count=summary.payments_count,
            is_reconciled=False
        )
        
        db.add(close_record)
        await db.commit()
        await db.refresh(close_record)
        return close_record
        
    @staticmethod
    async def get_by_date(target_date: date, db: AsyncSession) -> CashRegisterClose:
        """Recupera la chiusura cassa di una specifica data."""
        stmt = select(CashRegisterClose).where(CashRegisterClose.close_date == target_date)
        res = await db.execute(stmt)
        record = res.scalar_one_or_none()
        if not record:
            raise NotFoundError("Nessuna chiusura trovata per questa data")
        return record
        
    @staticmethod
    async def get_history(
        from_date: Optional[date], to_date: Optional[date], db: AsyncSession,
        skip: int = 0, limit: int = 50
    ) -> Sequence[CashRegisterClose]:
        """Storico delle chiusure con eventuale filtro per data."""
        stmt = select(CashRegisterClose).order_by(CashRegisterClose.close_date.desc())
        if from_date:
            stmt = stmt.where(CashRegisterClose.close_date >= from_date)
        if to_date:
            stmt = stmt.where(CashRegisterClose.close_date <= to_date)
            
        stmt = stmt.offset(skip).limit(limit)
        res = await db.execute(stmt)
        return res.scalars().all()
        
    @staticmethod
    async def reconcile(target_date: date, db: AsyncSession) -> CashRegisterClose:
        """Segna come riconciliata una chiusura."""
        record = await CashRegisterService.get_by_date(target_date, db)
        record.is_reconciled = True
        await db.commit()
        await db.refresh(record)
        return record
