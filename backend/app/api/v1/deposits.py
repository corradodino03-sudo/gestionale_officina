import uuid
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.invoice import DepositCreate, DepositRead
from app.services.deposit_service import DepositService

router = APIRouter(prefix="/deposits", tags=["Caparre e Acconti"])

@router.post("/", response_model=DepositRead)
async def create_deposit(
    data: DepositCreate,
    db: AsyncSession = Depends(get_db),
):
    """Registra una nuova caparra/acconto."""
    return await DepositService.create(data, db)


@router.get("/client/{client_id}", response_model=List[DepositRead])
async def get_client_deposits(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Recupera tutte le caparre di un cliente."""
    return await DepositService.get_by_client(client_id, db)


@router.get("/{deposit_id}", response_model=DepositRead)
async def get_deposit(
    deposit_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Recupera il dettaglio di una singola caparra."""
    return await DepositService.get_by_id(deposit_id, db)


@router.post("/{deposit_id}/apply/{invoice_id}", response_model=DepositRead)
async def apply_deposit_to_invoice(
    deposit_id: uuid.UUID,
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Scala una caparra da una fattura (crea Payment e PaymentAllocation)."""
    return await DepositService.apply_to_invoice(deposit_id, invoice_id, db)


@router.post("/{deposit_id}/refund", response_model=DepositRead)
async def refund_deposit(
    deposit_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Rimborsa una caparra in stato pending."""
    return await DepositService.refund(deposit_id, db)
