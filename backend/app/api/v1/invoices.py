"""
Router FastAPI per la Fatturazione
Progetto: Garage Manager (Gestionale Officina)

Definisce gli endpoint API per la gestione delle fatture,
incluse le operazioni CRUD, gestione pagamenti e report.
"""

import logging
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import BusinessValidationError, NotFoundError
from app.schemas.invoice import (
    CreateInvoiceFromWorkOrder,
    InvoiceList,
    InvoiceRead,
    InvoiceUpdate,
    PaymentAllocationCreate,
    PaymentCreate,
    PaymentRead,
    RevenueReport,
)
from app.services.invoice_service import InvoiceService

# Logger per questo modulo
logger = logging.getLogger(__name__)

# Istanza del service
invoice_service = InvoiceService()

# Router con prefix e tag
router = APIRouter(
    prefix="/invoices",
    tags=["Fatturazione"],
)


# -------------------------------------------------------------------
# Endpoints per Fatture
# -------------------------------------------------------------------

@router.get(
    "/",
    name="fatture_lista",
    summary="Lista fatture",
    description="Recupera la lista paginata delle fatture con eventuali filtri.",
    response_model=InvoiceList,
    status_code=status.HTTP_200_OK,
)
async def get_invoices(
    client_id: Optional[uuid.UUID] = Query(
        None,
        description="Filtro per UUID cliente"
    ),
    status_filter: Optional[str] = Query(
        None,
        description="Filtro per stato (paid, partial, unpaid, overdue)"
    ),
    overdue_only: bool = Query(
        False,
        description="Se True, restituisce solo fatture scadute"
    ),
    from_date: Optional[date] = Query(
        None,
        description="Data inizio periodo (formato: YYYY-MM-DD)"
    ),
    to_date: Optional[date] = Query(
        None,
        description="Data fine periodo (formato: YYYY-MM-DD)"
    ),
    page: int = Query(1, ge=1, description="Numero pagina"),
    per_page: int = Query(10, ge=1, le=100, description="Elementi per pagina"),
    db: AsyncSession = Depends(get_db),
) -> InvoiceList:
    """
    Recupera la lista paginata delle fatture.
    
    Filtri disponibili:
    - client_id: filtra per cliente
    - status: filtra per stato (paid, partial, unpaid, overdue)
    - overdue_only: solo fatture scadute
    - from_date/to_date: intervallo date fattura
    """
    return await invoice_service.get_all(
        db=db,
        client_id=client_id,
        status_filter=status_filter,
        overdue_only=overdue_only,
        from_date=from_date,
        to_date=to_date,
        page=page,
        per_page=per_page,
    )


@router.get(
    "/overdue",
    name="fatture_scadute",
    summary="Fatture scadute",
    description="Recupera la lista delle fatture scadute e non completamente pagate.",
    response_model=list[InvoiceRead],
    status_code=status.HTTP_200_OK,
)
async def get_overdue_invoices(
    db: AsyncSession = Depends(get_db),
) -> list[InvoiceRead]:
    """
    Recupera tutte le fatture scadute.
    
    Una fattura è considerata scaduta quando:
    - La data di scadenza (due_date) è antecedente a oggi
    - L'importo residuo è maggiore di 0
    """
    return await invoice_service.get_overdue_invoices(db=db)


@router.get(
    "/{invoice_id}",
    name="fattura_dettaglio",
    summary="Dettaglio fattura",
    description="Recupera i dettagli di una fattura.",
    response_model=InvoiceRead,
    status_code=status.HTTP_200_OK,
)
async def get_invoice(
    invoice_id: uuid.UUID = Path(..., description="UUID della fattura"),
    db: AsyncSession = Depends(get_db),
) -> InvoiceRead:
    """
    Recupera i dettagli di una fattura per ID.
    """
    return await invoice_service.get_by_id(db=db, invoice_id=invoice_id)


@router.get(
    "/number/{invoice_number}",
    name="fattura_per_numero",
    summary="Fattura per numero",
    description="Recupera una fattura cercandola per numero.",
    response_model=InvoiceRead,
    status_code=status.HTTP_200_OK,
)
async def get_invoice_by_number(
    invoice_number: str = Path(..., description="Numero fattura (formato: YYYY/NNN)"),
    db: AsyncSession = Depends(get_db),
) -> InvoiceRead:
    """
    Recupera una fattura cercandola per numero progressivo.
    """
    return await invoice_service.get_by_invoice_number(
        db=db,
        invoice_number=invoice_number,
    )


@router.post(
    "/from-work-order/{work_order_id}",
    name="crea_fattura_da_ordine",
    summary="Crea fattura da ordine di lavoro",
    description="Genera una fattura da un ordine di lavoro completato.",
    response_model=InvoiceRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_invoice_from_work_order(
    work_order_id: uuid.UUID = Path(..., description="UUID dell'ordine di lavoro"),
    data: CreateInvoiceFromWorkOrder = ...,
    db: AsyncSession = Depends(get_db),
) -> InvoiceRead:
    """
    Genera una fattura da un ordine di lavoro COMPLETATO.
    
    L'ordine di lavoro deve essere nello stato 'completed'.
    Se l'ordine ha già una fattura associata, restituisce errore.
    
    Dati obbligatori:
    - work_order_id: UUID dell'ordine di lavoro
    
    Dati opzionali:
    - invoice_date: data emissione fattura (default: oggi)
    - due_date: data scadenza (default: invoice_date + 30 giorni)
    - customer_notes: note per il cliente
    """
    return await invoice_service.create_from_work_order(
        db=db,
        work_order_id=work_order_id,
        data=data,
    )


@router.put(
    "/{invoice_id}",
    name="aggiorna_fattura",
    summary="Aggiorna fattura",
    description="Aggiorna i dati modificabili di una fattura.",
    response_model=InvoiceRead,
    status_code=status.HTTP_200_OK,
)
async def update_invoice(
    invoice_id: uuid.UUID = Path(..., description="UUID della fattura"),
    data: InvoiceUpdate = ...,
    db: AsyncSession = Depends(get_db),
) -> InvoiceRead:
    """
    Aggiorna una fattura.
    
    Campi modificabili:
    - notes: note interne
    - customer_notes: note per il cliente
    - due_date: data scadenza
    
    NOTA: Gli importi non sono modificabili dopo la creazione.
    """
    return await invoice_service.update(
        db=db,
        invoice_id=invoice_id,
        data=data,
    )


@router.delete(
    "/{invoice_id}",
    name="elimina_fattura",
    summary="Elimina fattura",
    description="Elimina una fattura se non ha pagamenti registrati.",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_invoice(
    invoice_id: uuid.UUID = Path(..., description="UUID della fattura"),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Elimina una fattura.
    
    Condizioni per l'eliminazione:
    - La fattura non deve avere pagamenti registrati
    
    Effetti:
    - L'ordine di lavoro tornerà allo stato 'completed'
    """
    await invoice_service.delete(db=db, invoice_id=invoice_id)


# -------------------------------------------------------------------
# Endpoints per Pagamenti (non più nested sotto fatture)
# -------------------------------------------------------------------

@router.post(
    "/payments",
    name="crea_pagamento",
    summary="Crea pagamento",
    description="Crea un nuovo pagamento con allocazione automatica o manuale.",
    response_model=PaymentRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Pagamenti"],
)
async def create_payment(
    data: PaymentCreate,
    db: AsyncSession = Depends(get_db),
) -> PaymentRead:
    """
    Crea un nuovo pagamento con allocazione automatica o manuale.
    
    Strategie allocazione:
    - "fifo" (default): alloca su fatture più vecchie per prime
    - "overdue_first": alloca su fatture scadute per prime
    - "manual": alloca secondo lista esplicita in `allocations`
    
    Esempi:
    
    1. Allocazione automatica FIFO:
    ```json
    {
      "client_id": "uuid-cliente",
      "amount": 1500.00,
      "payment_date": "2025-01-18",
      "payment_method": "cash",
      "allocation_strategy": "fifo"
    }
    ```
    
    2. Allocazione manuale (cliente dice "pago queste due fatture"):
    ```json
    {
      "client_id": "uuid-cliente",
      "amount": 1500.00,
      "payment_date": "2025-01-18",
      "payment_method": "cash",
      "allocation_strategy": "manual",
      "allocations": [
        {"invoice_id": "uuid-fattura-B", "amount": 900.00},
        {"invoice_id": "uuid-fattura-C", "amount": 600.00}
      ]
    }
    ```
    """
    payment = await invoice_service.create_payment(db=db, payment_data=data)
    return payment


@router.get(
    "/payments/{payment_id}",
    name="dettaglio_pagamento",
    summary="Dettaglio pagamento",
    description="Recupera dettagli pagamento con allocazioni.",
    response_model=PaymentRead,
    tags=["Pagamenti"],
)
async def get_payment(
    payment_id: uuid.UUID = Path(..., description="UUID del pagamento"),
    db: AsyncSession = Depends(get_db),
) -> PaymentRead:
    """Recupera dettagli pagamento con allocazioni."""
    from app.models.invoice import Payment
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    
    stmt = select(Payment).where(Payment.id == payment_id).options(
        selectinload(Payment.allocations),
        selectinload(Payment.client)
    )
    result = await db.execute(stmt)
    payment = result.scalar_one_or_none()
    
    if not payment:
        raise NotFoundError(f"Pagamento {payment_id} non trovato")
    
    return payment


@router.put(
    "/payments/{payment_id}/reallocate",
    name="rialloca_pagamento",
    summary="Riallocazione pagamento",
    description="Storna allocazioni esistenti e crea nuove.",
    response_model=PaymentRead,
    tags=["Pagamenti"],
)
async def reallocate_payment(
    payment_id: uuid.UUID = Path(..., description="UUID del pagamento"),
    new_allocations: list[PaymentAllocationCreate] = ...,
    db: AsyncSession = Depends(get_db),
) -> PaymentRead:
    """
    Riallocazione pagamento (storna allocazioni esistenti, crea nuove).
    
    Use case: errore di registrazione, cliente chiede di cambiare fatture pagate.
    """
    allocations_dict = [
        {"invoice_id": a.invoice_id, "amount": a.amount}
        for a in new_allocations
    ]
    
    payment = await invoice_service.reallocate_payment(db=db, payment_id=payment_id, new_allocations=allocations_dict)
    return payment


@router.delete(
    "/payments/{payment_id}",
    name="elimina_pagamento",
    summary="Elimina pagamento",
    description="Elimina pagamento (e tutte le allocazioni cascade).",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Pagamenti"],
)
async def delete_payment(
    payment_id: uuid.UUID = Path(..., description="UUID del pagamento"),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Elimina pagamento (e tutte le allocazioni cascade)."""
    await invoice_service.delete_payment(db=db, payment_id=payment_id)
    return None


@router.get(
    "/clients/{client_id}/payments",
    name="pagamenti_cliente",
    summary="Pagamenti cliente",
    description="Lista tutti i pagamenti di un cliente.",
    response_model=list[PaymentRead],
    tags=["Pagamenti"],
)
async def get_client_payments(
    client_id: uuid.UUID = Path(..., description="UUID del cliente"),
    db: AsyncSession = Depends(get_db),
) -> list[PaymentRead]:
    """Lista tutti i pagamenti di un cliente."""
    from app.models.invoice import Payment
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    
    stmt = select(Payment).where(Payment.client_id == client_id).options(
        selectinload(Payment.allocations)
    ).order_by(Payment.payment_date.desc())
    
    result = await db.execute(stmt)
    payments = result.scalars().all()
    
    return list(payments)


# Mantiene GET /{invoice_id}/payments per vedere allocazioni ricevute da fattura
@router.get(
    "/{invoice_id}/payments",
    name="allocazioni_fattura",
    summary="Allocazioni fattura",
    description="Lista allocazioni ricevute da questa fattura.",
    response_model=list[PaymentRead],
    tags=["Fatturazione"],
)
async def get_invoice_payments(
    invoice_id: uuid.UUID = Path(..., description="UUID della fattura"),
    db: AsyncSession = Depends(get_db),
) -> list[PaymentRead]:
    """Lista allocazioni ricevute da questa fattura."""
    from app.schemas.invoice import PaymentAllocationRead
    from app.models.invoice import Invoice
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    
    stmt = select(Invoice).where(Invoice.id == invoice_id).options(
        selectinload(Invoice.payment_allocations)
    )
    result = await db.execute(stmt)
    invoice = result.scalar_one_or_none()
    
    if not invoice:
        raise NotFoundError(f"Fattura {invoice_id} non trovata")
    
    # Costruisci la lista di PaymentRead dalle allocazioni
    # Per retrocompatibilità, restituiamo i pagamenti completi con le relative allocazioni
    payment_ids = list(set(alloc.payment_id for alloc in invoice.payment_allocations))
    
    from app.models.invoice import Payment
    stmt = select(Payment).where(Payment.id.in_(payment_ids)).options(
        selectinload(Payment.allocations)
    )
    result = await db.execute(stmt)
    payments = result.scalars().all()
    
    return list(payments)


# -------------------------------------------------------------------
# Endpoints per Report
# -------------------------------------------------------------------

@router.get(
    "/reports/revenue",
    name="report_incassi",
    summary="Report incassi",
    description="Restituisce un report degli incassi nel periodo specificato.",
    response_model=RevenueReport,
    status_code=status.HTTP_200_OK,
)
async def get_revenue_report(
    from_date: date = Query(..., description="Data inizio periodo (formato: YYYY-MM-DD)"),
    to_date: date = Query(..., description="Data fine periodo (formato: YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
) -> RevenueReport:
    """
    Report incassi nel periodo specificato.
    
    Restituisce:
    - total_invoiced: somma totale delle fatture nel periodo
    - total_paid: somma totale dei pagamenti nel periodo
    - total_unpaid: residuo da incassare
    - invoices_count: numero fatture nel periodo
    - payments_count: numero pagamenti nel periodo
    """
    return await invoice_service.get_revenue_report(
        db=db,
        from_date=from_date,
        to_date=to_date,
    )
