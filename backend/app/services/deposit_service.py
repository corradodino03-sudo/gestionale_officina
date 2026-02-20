import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessValidationError, NotFoundError
from app.models.invoice import Deposit, Payment, PaymentAllocation, Invoice
from app.schemas.invoice import DepositCreate, DepositStatus


class DepositService:
    @staticmethod
    async def create(data: DepositCreate, db: AsyncSession) -> Deposit:
        deposit = Deposit(
            client_id=data.client_id,
            work_order_id=data.work_order_id,
            amount=data.amount,
            payment_method=data.payment_method,
            deposit_date=data.deposit_date,
            reference=data.reference,
            notes=data.notes,
            status=DepositStatus.PENDING.value,
        )
        db.add(deposit)
        await db.commit()
        await db.refresh(deposit)
        return deposit

    @staticmethod
    async def apply_to_invoice(
        deposit_id: uuid.UUID, invoice_id: uuid.UUID, db: AsyncSession
    ) -> Deposit:
        deposit = await db.get(Deposit, deposit_id)
        if not deposit:
            raise NotFoundError("Caparra non trovata")
        
        if deposit.status != DepositStatus.PENDING.value:
            raise BusinessValidationError("La caparra non è in stato pending")
            
        invoice = await db.get(Invoice, invoice_id)
        if not invoice:
            raise NotFoundError("Fattura non trovata")
            
        if deposit.amount > invoice.total:
            raise BusinessValidationError(
                "L'importo della caparra supera il totale della fattura"
            )

        # Crea un Payment
        payment = Payment(
            client_id=deposit.client_id,
            amount=deposit.amount,
            payment_date=deposit.deposit_date,
            payment_method=deposit.payment_method,
            reference=f"Caparra {deposit.id}",
            notes=f"Applicazione caparra originaria: {deposit.notes or ''}"
        )
        db.add(payment)
        await db.flush()

        # Crea la PaymentAllocation
        allocation = PaymentAllocation(
            payment_id=payment.id,
            invoice_id=invoice.id,
            amount=deposit.amount
        )
        db.add(allocation)

        # Aggiorna lo stato della caparra
        deposit.status = DepositStatus.APPLIED.value
        deposit.invoice_id = invoice.id

        await db.commit()
        await db.refresh(deposit)
        return deposit

    @staticmethod
    async def refund(deposit_id: uuid.UUID, db: AsyncSession) -> Deposit:
        deposit = await db.get(Deposit, deposit_id)
        if not deposit:
            raise NotFoundError("Caparra non trovata")
        
        if deposit.status != DepositStatus.PENDING.value:
            raise BusinessValidationError(
                "Solo una caparra in stato pending può essere rimborsata"
            )

        deposit.status = DepositStatus.REFUNDED.value
        await db.commit()
        await db.refresh(deposit)
        return deposit

    @staticmethod
    async def get_by_client(client_id: uuid.UUID, db: AsyncSession) -> Sequence[Deposit]:
        stmt = select(Deposit).where(Deposit.client_id == client_id)
        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_by_id(deposit_id: uuid.UUID, db: AsyncSession) -> Deposit:
        deposit = await db.get(Deposit, deposit_id)
        if not deposit:
            raise NotFoundError("Caparra non trovata")
        return deposit
