"""
Service Layer per la Fatturazione
Progetto: Garage Manager (Gestionale Officina)

Definisce la logica di business per la gestione delle fatture,
incluse la generazione da ordini di lavoro, gestione pagamenti e report.
"""

import logging
import uuid
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy import and_, delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    BusinessValidationError,
    ConflictError,
    NotFoundError,
)
from app.models import Invoice, InvoiceLine, PartUsage, Payment, PaymentAllocation, WorkOrder
from app.models.client import Client
from app.models.intent_declaration import IntentDeclaration
from app.schemas.invoice import (
    CreateInvoiceFromWorkOrder,
    InvoiceList,
    InvoiceUpdate,
    PaymentAllocationCreate,
    PaymentCreate,
    RevenueReport,
    InvoiceCreationResponse,
    PendingDepositSummary,
    DepositStatus,
)
from app.core.config import settings

# Logger per questo modulo
logger = logging.getLogger(__name__)


class InvoiceService:
    """
    Service per la gestione delle operazioni sulle fatture.
    
    Fornisce metodi asincroni per interagire con il database
    in modo centralizzato, senza dipendenze da FastAPI.
    
    Implementa:
    - Generazione fattura da ordine di lavoro completato
    - Gestione pagamenti parziali
    - Calcolo automatico stato fattura
    - Numerazione progressiva annuale
    - Report incassi
    """

    async def create_from_work_order(
        self,
        db: AsyncSession,
        work_order_id: uuid.UUID,
        data: CreateInvoiceFromWorkOrder,
    ) -> InvoiceCreationResponse:
        """
        Genera una fattura da un ordine di lavoro COMPLETATO.
        
        Steps:
        1. Verifica che work_order esista
        2. Verifica che work_order.status == "completed"
        3. Verifica che non esista già una fattura per questo ordine
        4. Recupera il cliente (per regime fiscale)
        5. Genera invoice_number progressivo annuale
        6. Calcola subtotal sommando:
           - work_order_items (manodopera/servizi)
           - part_usages (ricambi)
        7. Applica regime fiscale cliente (FEAT 4):
           - Se RF19 (Forfettario): IVA = 0%, aggiungi dicitura legale
           - Se RF02 (Minimi): IVA = 0%, aggiungi dicitura legale
           - Se vat_exemption: IVA = 0%, usa vat_exemption_code
           - Altrimenti: vat_amount = subtotal * vat_rate / 100
        8. FEAT 1: Usa client.default_vat_rate come fallback se non specificato
        9. FEAT 2: Calcola due_date usando client.payment_terms_days
        10. FEAT 3: Applica default_discount_percent a ogni riga
        11. FEAT 5: Usa effective_billing_address per dati fatturazione
        12. FEAT 6: Verifica e aggiorna dichiarazione di intento
        13. FEAT 7: Verifica credito e blocca/warna se superato
        14. Crea InvoiceLines da work_order_items e part_usages
        15. Crea Invoice
        16. Cambia stato work_order a "invoiced"
        17. Restituisci Invoice con relazioni caricate
        
        Args:
            db: Sessione database
            work_order_id: UUID dell'ordine di lavoro
            data: Dati per la creazione della fattura
            
        Returns:
            InvoiceCreationResponse: La fattura creata e le caparre in sospeso
            
        Raises:
            NotFoundError: work_order non esiste
            BusinessValidationError: ordine non completato o già fatturato
            ConflictError: errore di integrità (numero fattura duplicato)
        """
        # Step 1: Verifica esistenza work_order
        stmt = (
            select(WorkOrder)
            .where(WorkOrder.id == work_order_id)
            .with_for_update()
            .options(
                selectinload(WorkOrder.client),
                selectinload(WorkOrder.items),
                selectinload(WorkOrder.part_usages).selectinload(PartUsage.part),
                selectinload(WorkOrder.invoice),
            )
        )
        result = await db.execute(stmt)
        work_order = result.scalar_one_or_none()
        
        if not work_order:
            raise NotFoundError(f"Ordine di lavoro {work_order_id} non trovato")
        
        # Step 2: Verifica stato completato
        if work_order.status != "completed":
            raise BusinessValidationError(
                f"L'ordine di lavoro deve essere completato per essere fatturato. "
                f"Stato attuale: {work_order.status}"
            )
        
        # Step 3: Verifica che non esista già fattura
        if work_order.invoice is not None:
            raise BusinessValidationError(
                f"Una fattura esiste già per questo ordine di lavoro: "
                f"{work_order.invoice.invoice_number}"
            )
        
        # Step 4: Recupera cliente
        client = work_order.client
        if not client:
            raise BusinessValidationError("Il cliente associato all'ordine non è stato trovato")
            
        # FEAT 3: Fattura a terzi
        billing_client = client
        bill_to_name = None
        bill_to_tax_id = None
        bill_to_address = None
        
        if getattr(data, 'bill_to_client_id', None):
            stmt_billing = select(Client).where(Client.id == data.bill_to_client_id)
            res_billing = await db.execute(stmt_billing)
            billing_client_res = res_billing.scalar_one_or_none()
            if not billing_client_res:
                raise NotFoundError("Cliente terzo per fatturazione non trovato")
                
            billing_client = billing_client_res
            
            # Popola i dati denormalizzati
            bill_to_name = f"{billing_client.first_name} {billing_client.last_name}".strip()
            if billing_client.company_name:
                bill_to_name = billing_client.company_name
                
            bill_to_tax_id = billing_client.vat_number or billing_client.tax_code
            
            bill_to_address = billing_client.effective_billing_address if hasattr(billing_client, 'effective_billing_address') else (
                f"{billing_client.address}, {billing_client.city} ({billing_client.province}) {billing_client.zip_code}"
            )
        
        # Step 5: Genera numero fattura
        invoice_date = data.invoice_date or date.today()
        invoice_number = await self._generate_invoice_number(db, invoice_date)
        
        # FEAT 1: Determina l'aliquota IVA da usare
        # Se specificata nella richiesta, usa quella; altrimenti usa default del cliente di fatturazione
        effective_vat_rate = data.vat_rate
        if effective_vat_rate is None:
            if getattr(billing_client, 'default_vat_rate', None) is not None:
                effective_vat_rate = Decimal(str(billing_client.default_vat_rate))
            else:
                effective_vat_rate = Decimal("22.00")
        
        # FEAT 4: Determina il regime IVA in base a vat_regime e vat_exemption
        # La logica ha precedenza su default_vat_rate quando il regime lo impone
        is_vat_exempt = False
        vat_exemption_code = getattr(billing_client, 'vat_exemption_code', None)
        vat_notes = None
        
        # Controlla il regime fiscale del cliente di fatturazione
        if getattr(billing_client, 'vat_regime', None) == "RF19":  # Forfettario
            is_vat_exempt = True
            effective_vat_rate = Decimal("0")
            vat_exemption_code = "N3.5"  # Non imponibili - dichiarazioni intento
            vat_notes = "Operazione effettuata ai sensi dell'art. 1, commi 54-89, L. 190/2014 - Regime Forfettario"
        elif getattr(billing_client, 'vat_regime', None) == "RF02":  # Minimi
            is_vat_exempt = True
            effective_vat_rate = Decimal("0")
            vat_exemption_code = "N3.5"
            vat_notes = "Operazione effettuata ai sensi dell'art. 27, commi 1 e 2, D.L. 98/2011 - Regime dei Minimi"
        elif getattr(billing_client, 'vat_exemption', False):  # Esente IVA generico
            is_vat_exempt = True
            effective_vat_rate = Decimal("0")
            # vat_exemption_code è già valorizzato dal cliente
        
        # Step 6: Calcola subtotal da work_order items e part_usages
        subtotal = Decimal("0")
        exempt_subtotal = Decimal("0")
        
        line_number = 1
        invoice_lines = []
        total_vat = Decimal("0")
        
        # FEAT 3: Determina lo sconto predefinito del cliente
        default_discount_percent = (
            Decimal(str(billing_client.default_discount_percent))
            if getattr(billing_client, 'default_discount_percent', None) is not None
            else Decimal("0")
        )
        
        for item in work_order.items:
            item_subtotal = item.quantity * item.unit_price
            
            # FEAT 3: Applica sconto predefinito se presente
            discount_percent = default_discount_percent
            discount_amount = Decimal("0")
            if discount_percent > 0:
                discount_amount = (item_subtotal * Decimal(str(discount_percent))) / Decimal("100")
            
            subtotal += (item_subtotal - discount_amount)
            
            # Usa effective_vat_rate (potrebbe essere 0 per regimi speciali)
            item_vat_rate = effective_vat_rate
            item_vat = ((item_subtotal - discount_amount) * item_vat_rate) / Decimal("100")
            total_vat += item_vat
            
            if item_vat_rate == Decimal("0"):
                exempt_subtotal += (item_subtotal - discount_amount)
            
            invoice_line = InvoiceLine(
                line_type=item.item_type,
                description=item.description,
                quantity=item.quantity,
                unit_price=item.unit_price,
                discount_percent=discount_percent,
                discount_amount=discount_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                vat_rate=item_vat_rate,
                line_number=line_number,
            )
            invoice_lines.append(invoice_line)
            line_number += 1
        
        # Processa part_usages (ricambi)
        for part_usage in work_order.part_usages:
            part_subtotal = part_usage.quantity * part_usage.unit_price
            
            part_desc = part_usage.part.description if part_usage.part else "Ricambio non disponibile"
            description = f"{part_desc} (x{part_usage.quantity})"
            
            # FEAT 3: Applica sconto predefinito se presente
            discount_percent = default_discount_percent
            discount_amount = Decimal("0")
            if discount_percent > 0:
                discount_amount = (part_subtotal * Decimal(str(discount_percent))) / Decimal("100")
            
            subtotal += (part_subtotal - discount_amount)
            
            # FEAT 1: Leggi l'aliquota dal Part se disponibile, altrimenti usa effective_vat_rate
            if part_usage.part and hasattr(part_usage.part, 'vat_rate'):
                part_vat_rate = part_usage.part.vat_rate or effective_vat_rate
            else:
                part_vat_rate = effective_vat_rate
            
            part_vat = ((part_subtotal - discount_amount) * part_vat_rate) / Decimal("100")
            total_vat += part_vat
            
            if part_vat_rate == Decimal("0"):
                exempt_subtotal += (part_subtotal - discount_amount)
            
            invoice_line = InvoiceLine(
                line_type="part",
                description=description,
                quantity=part_usage.quantity,
                unit_price=part_usage.unit_price,
                discount_percent=discount_percent,
                discount_amount=discount_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                vat_rate=part_vat_rate,
                line_number=line_number,
            )
            invoice_lines.append(invoice_line)
            line_number += 1
        
        if subtotal <= 0:
            raise BusinessValidationError(
                "L'ordine di lavoro non ha importi da fatturare"
            )
        
        # Arrotonda subtotal a 2 decimali
        subtotal = subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        # FEAT 2: Calcola la data di scadenza usando payment_terms_days del cliente
        if data.due_date:
            due_date = data.due_date
        else:
            # Usa i giorni predefiniti del cliente (default 30)
            payment_terms = getattr(billing_client, 'payment_terms_days', 30) or 30
            due_date = invoice_date + timedelta(days=payment_terms)
        
        # Calcola IVA preliminare
        if is_vat_exempt:
            vat_amount = Decimal("0")
            exempt_subtotal = subtotal
        else:
            vat_amount = total_vat.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        total = subtotal + vat_amount
        # Arrotonda total preliminare a 2 decimali
        total = total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        # FEAT 5: Prepara indirizzo fatturazione effettivo
        billing_address = getattr(billing_client, 'effective_billing_address', None) or {
            "address": getattr(billing_client, 'address', ''),
            "city": getattr(billing_client, 'city', ''),
            "zip_code": getattr(billing_client, 'zip_code', ''),
            "province": getattr(billing_client, 'province', ''),
        }
        
        # FEAT 6: Gestione dichiarazioni di intento
        # Se il cliente ha una dichiarazione di intento attiva e valida
        active_intent = None
        if not is_vat_exempt:  # Solo se non già esente per altro motivo
            # Cerca dichiarazione di intento attiva e valida
            intent_stmt = (
                select(IntentDeclaration)
                .where(
                    IntentDeclaration.client_id == billing_client.id,
                    IntentDeclaration.is_active == True,
                    IntentDeclaration.expiry_date >= invoice_date,
                )
                .order_by(IntentDeclaration.expiry_date.desc())
            )
            intent_result = await db.execute(intent_stmt)
            active_intent = intent_result.scalar_one_or_none()
            
            if active_intent and active_intent.remaining_amount >= total:
                # Usa la dichiarazione di intento - IVA = 0%
                is_vat_exempt = True
                effective_vat_rate = Decimal("0")
                vat_amount = Decimal("0")
                vat_exemption_code = "N3.5"
                vat_notes = "Operazione effettuata ai sensi dell'art. 1, c. 100, L. 244/2007 - Dichiarazione di intento"
                
                # Ricalcola: tutto diventa esente
                exempt_subtotal = subtotal
                
                # Ricalcola il total ritirando l'IVA
                total = subtotal
                
                # Forza vat_rate a 0 su tutte le righe
                for line in invoice_lines:
                    line.vat_rate = Decimal("0")
                
                # Aggiorna used_amount calcolando il totale pre-bollo
                active_intent.used_amount = (active_intent.used_amount + total).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            elif active_intent and active_intent.remaining_amount < total:
                # Superato il plafond
                raise BusinessValidationError(
                    f"Impossibile emettere fattura: l'importo ({total}) supera il plafond residuo "
                    f"della dichiarazione di intento ({active_intent.remaining_amount}). "
                    f"Plafond dichiarato: {active_intent.amount_limit}, "
                    f"già utilizzato: {active_intent.used_amount}"
                )
        
        # FEAT 3: Marca da bollo automatica (Fix per casi misti e dichiarazioni intento)
        stamp_duty_applied = False
        stamp_duty_amount = Decimal("0.00")
        
        if exempt_subtotal > settings.stamp_duty_threshold:
            stamp_duty_applied = True
            stamp_duty_amount = settings.stamp_duty_amount
            total += stamp_duty_amount
        
        # FEAT 7: Controllo fido commerciale
        credit_limit_warning = None
        if client.credit_limit is not None and client.credit_limit > 0:
            # Calcola l'esposizione corrente del cliente
            # Approccio: total_fatture - total_pagamenti (semplificato)
            # Poiché status è una computed property, non possiamo filtrare via SQL
            
            # Get total of all invoices for this client
            total_invoices_stmt = (
                select(func.coalesce(func.sum(Invoice.total), 0))
                .where(Invoice.client_id == client.id)
            )
            total_invoices_result = await db.execute(total_invoices_stmt)
            total_invoiced = total_invoices_result.scalar() or Decimal("0")
            
            # Get total of all payments allocated to this client's invoices
            total_payments_stmt = (
                select(func.coalesce(func.sum(Payment.amount), 0))
                .join(PaymentAllocation)
                .join(Invoice)
                .where(Invoice.client_id == client.id)
            )
            total_payments_result = await db.execute(total_payments_stmt)
            total_paid = total_payments_result.scalar() or Decimal("0")
            
            current_exposure = total_invoiced - total_paid
            new_exposure = current_exposure + total
            
            if new_exposure > Decimal(str(client.credit_limit)):
                if client.credit_limit_action == "block":
                    raise BusinessValidationError(
                        f"Impossibile emettere fattura: il cliente ha superato il fido accordato. "
                        f"Esposizione attuale: {current_exposure}, "
                        f"nuovo importo: {total}, "
                        f"totale: {new_exposure}, "
                        f"fido: {client.credit_limit}"
                    )
                else:
                    # WARN - aggiungi nota di avviso
                    credit_limit_warning = (
                        f"ATTENZIONE: Superato il fido accordato ({client.credit_limit}). "
                        f"Esposizione attuale: {current_exposure}, nuovo importo: {total}"
                    )
        
        # Combina le note
        notes = data.customer_notes or ""
        if vat_notes:
            notes = f"{notes}\n{vat_notes}".strip()
        if credit_limit_warning:
            notes = f"{notes}\n{credit_limit_warning}".strip()
        
        # FEAT 2: Dati bancari
        payment_iban = None
        if getattr(billing_client, "payment_method_default", None) == "bank_transfer":
            payment_iban = settings.invoice_iban
            
        payment_reference = invoice_number

        # Step 14-15: Crea Invoice
        invoice = Invoice(
            work_order_id=work_order_id,
            client_id=client.id,
            bill_to_client_id=data.bill_to_client_id,
            bill_to_name=bill_to_name,
            bill_to_tax_id=bill_to_tax_id,
            bill_to_address=bill_to_address if isinstance(bill_to_address, str) else str(bill_to_address),
            claim_number=getattr(data, "claim_number", None),
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            due_date=due_date,
            subtotal=subtotal,
            vat_rate=effective_vat_rate,
            vat_amount=vat_amount,
            total=total,
            vat_exemption=is_vat_exempt,
            vat_exemption_code=vat_exemption_code,
            split_payment=getattr(billing_client, 'split_payment', False),
            notes=notes,
            customer_notes=data.customer_notes,
            stamp_duty_applied=stamp_duty_applied,
            stamp_duty_amount=stamp_duty_amount,
            payment_iban=payment_iban,
            payment_reference=payment_reference,
        )
        
        # Aggiunge le righe
        for line in invoice_lines:
            invoice.lines.append(line)
        
        # Salva nel database
        db.add(invoice)
        
        # Step 16: Cambia stato work_order
        work_order.status = "invoiced"
        
        try:
            await db.commit()
            await db.refresh(invoice)
        except IntegrityError as e:
            await db.rollback()
            logger.error(f"Errore di integrità durante creazione fattura: {e}")
            raise ConflictError("Errore durante la creazione della fattura")
        
        # Step 17: Ricarica con relazioni
        final_invoice = await self.get_by_id(db, invoice.id)
        
        # Controllare se esistono caparre pending (FEAT 2)
        from app.services.deposit_service import DepositService
        deposits = await DepositService.get_by_client(final_invoice.client_id, db)
        
        pending_deposits = [
            d for d in deposits 
            if d.status == DepositStatus.PENDING.value and (d.work_order_id == work_order_id or d.work_order_id is None)
        ]
        
        pending_deposits_summary = None
        if pending_deposits:
            total_available = sum(d.amount for d in pending_deposits)
            pending_deposits_summary = PendingDepositSummary(
                deposits=pending_deposits,
                total_amount=total_available
            )
            
        return InvoiceCreationResponse(
            invoice=final_invoice,
            pending_deposits=pending_deposits_summary
        )

    async def _generate_invoice_number(
        self,
        db: AsyncSession,
        invoice_date: date,
    ) -> str:
        """
        Genera numero fattura progressivo annuale.
        
        Formato: YYYY/NNNN (es. 2025/0001)
        
        Logica:
        1. Estrae l'anno da invoice_date
        2. Acquisisce advisory lock PostgreSQL per evitare race condition
        3. Cerca l'ultima fattura dell'anno
        4. Incrementa il progressivo
        5. Formatta con zero-padding (0001, 0002, ..., 9999)
        
        Args:
            db: Sessione database
            invoice_date: Data della fattura
            
        Returns:
            str: Numero fattura formattato
            
        Raises:
            ConflictError: Se si raggiunge il limite di 9999 fatture annue
        """
        year = invoice_date.year
        year_prefix = f"{year}/"
        
        # P0-Fix 3: Aggiunto advisory lock per evitare race condition
        # SELECT FOR UPDATE non blocca nulla se non esistono righe per l'anno corrente
        await db.execute(text("SELECT pg_advisory_xact_lock(:lock_key)"), {"lock_key": year})
        
        # Rimosso with_for_update() - non serve più con advisory lock
        stmt = (
            select(Invoice)
            .where(Invoice.invoice_number.like(f"{year_prefix}%"))
            .order_by(Invoice.invoice_number.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        last_invoice = result.scalar_one_or_none()
        
        # Determina il prossimo numero
        if last_invoice:
            # Estrai il numero dalla ultima fattura
            last_number = int(last_invoice.invoice_number.split("/")[1])
            next_number = last_number + 1
        else:
            next_number = 1
        
        # P3-Fix 7: Verifica limite aumentato a 9999
        if next_number > 9999:
            raise ConflictError(
                f"Limite numerazione fatture raggiunto per l'anno {year}"
            )
        
        # Formatta con zero-padding a 4 cifre
        return f"{year_prefix}{next_number:04d}"

    async def get_all(
        self,
        db: AsyncSession,
        client_id: Optional[uuid.UUID] = None,
        status_filter: Optional[str] = None,
        overdue_only: bool = False,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        page: int = 1,
        per_page: int = 10,
    ) -> InvoiceList:
        """
        Recupera la lista paginata delle fatture con filtri.
        
        Args:
            db: Sessione database
            client_id: Filtro per cliente
            status_filter: Filtro per stato (paid, partial, unpaid, overdue)
            overdue_only: Se True, restituisce solo fatture scadute
            from_date: Filtro data inizio
            to_date: Filtro data fine
            page: Numero pagina
            per_page: Elementi per pagina
            
        Returns:
            InvoiceList: Lista paginata delle fatture
        """
        # Build base query with eager loading
        stmt = select(Invoice).options(
            selectinload(Invoice.client),
            selectinload(Invoice.lines),
            selectinload(Invoice.payment_allocations),
        )
        
        # Build filter conditions
        conditions = []
        
        if client_id:
            conditions.append(Invoice.client_id == client_id)
        
        if from_date:
            conditions.append(Invoice.invoice_date >= from_date)
        
        if to_date:
            conditions.append(Invoice.invoice_date <= to_date)
        
        if overdue_only:
            today = date.today()
            conditions.append(Invoice.due_date < today)
        
        # Apply conditions
        if conditions:
            stmt = stmt.where(and_(*conditions))
        
        # P0-Fix 2: Se ci sono filtri calcolati (status/overdue), recupera tutto e filtra in Python
        needs_python_filter = bool(status_filter) or overdue_only
        
        if needs_python_filter:
            # Recupera TUTTE le fatture che soddisfano i filtri SQL
            result = await db.execute(stmt.order_by(Invoice.invoice_date.desc()))
            invoices = result.scalars().all()
            
            # Filtra per status in Python
            if status_filter:
                status_map = {
                    "paid": "paid",
                    "partial": "partial",
                    "unpaid": "unpaid",
                    "overdue": "overdue",
                }
                target_status = status_map.get(status_filter)
                if target_status:
                    invoices = [inv for inv in invoices if inv.status == target_status]
            
            # Filtra overdue in Python
            if overdue_only:
                invoices = [inv for inv in invoices if inv.is_overdue]
            
            # Paginazione manuale
            total = len(invoices)
            start = (page - 1) * per_page
            page_items = invoices[start:start + per_page]
            
            total_pages = (total + per_page - 1) // per_page if total > 0 else 1
            
            return InvoiceList(
                items=list(page_items),
                total=total,
                page=page,
                per_page=per_page,
                total_pages=total_pages,
            )
        
        # Get total count (senza filtri calcolati - paginazione SQL)
        count_stmt = select(func.count(Invoice.id))
        if conditions:
            count_stmt = count_stmt.where(and_(*conditions))
        
        count_result = await db.execute(count_stmt)
        total = count_result.scalar()
        
        # Apply pagination and ordering
        stmt = stmt.order_by(Invoice.invoice_date.desc())
        offset = (page - 1) * per_page
        stmt = stmt.offset(offset).limit(per_page)
        
        result = await db.execute(stmt)
        invoices = result.scalars().all()
        
        # Calculate total pages
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        
        return InvoiceList(
            items=list(invoices),
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
        )

    async def get_by_id(
        self,
        db: AsyncSession,
        invoice_id: uuid.UUID,
    ) -> Invoice:
        """
        Recupera una fattura per ID con tutte le relazioni caricate.
        
        Args:
            db: Sessione database
            invoice_id: UUID della fattura
            
        Returns:
            Invoice: La fattura con relazioni
            
        Raises:
            NotFoundError: Fattura non trovata
        """
        stmt = (
            select(Invoice)
            .where(Invoice.id == invoice_id)
            .options(
                selectinload(Invoice.work_order),
                selectinload(Invoice.client),
                selectinload(Invoice.lines),
                selectinload(Invoice.payment_allocations),
            )
        )
        result = await db.execute(stmt)
        invoice = result.scalar_one_or_none()
        
        if not invoice:
            raise NotFoundError(f"Fattura {invoice_id} non trovata")
        
        return invoice

    async def get_by_invoice_number(
        self,
        db: AsyncSession,
        invoice_number: str,
    ) -> Invoice:
        """
        Recupera una fattura per numero.
        
        Args:
            db: Sessione database
            invoice_number: Numero fattura (formato YYYY/NNNN)
            
        Returns:
            Invoice: La fattura con relazioni
            
        Raises:
            NotFoundError: Fattura non trovata
        """
        stmt = (
            select(Invoice)
            .where(Invoice.invoice_number == invoice_number)
            .options(
                selectinload(Invoice.work_order),
                selectinload(Invoice.client),
                selectinload(Invoice.lines),
                selectinload(Invoice.payment_allocations),
            )
        )
        result = await db.execute(stmt)
        invoice = result.scalar_one_or_none()
        
        if not invoice:
            raise NotFoundError(f"Fattura {invoice_number} non trovata")
        
        return invoice

    async def update(
        self,
        db: AsyncSession,
        invoice_id: uuid.UUID,
        data: InvoiceUpdate,
    ) -> Invoice:
        """
        Aggiorna una fattura.
        
        Permette solo: notes, customer_notes, due_date
        NON permette modificare importi (ricalcola da work_order se necessario)
        
        Args:
            db: Sessione database
            invoice_id: UUID della fattura
            data: Dati da aggiornare
            
        Returns:
            Invoice: La fattura aggiornata
            
        Raises:
            NotFoundError: Fattura non trovata
        """
        invoice = await self.get_by_id(db, invoice_id)
        
        # Aggiorna solo i campi permessi
        if data.notes is not None:
            invoice.notes = data.notes
        
        if data.customer_notes is not None:
            invoice.customer_notes = data.customer_notes
        
        if data.due_date is not None:
            invoice.due_date = data.due_date
        
        await db.commit()
        await db.refresh(invoice)
        
        return await self.get_by_id(db, invoice_id)

    async def delete(
        self,
        db: AsyncSession,
        invoice_id: uuid.UUID,
    ) -> None:
        """
        Elimina una fattura.
        
        Solo se payments è vuoto (nessun incasso registrato).
        Riporta work_order a status "completed" solo se era "invoiced".
        
        Args:
            db: Sessione database
            invoice_id: UUID della fattura
            
        Raises:
            NotFoundError: Fattura non trovata
            BusinessValidationError: La fattura ha pagamenti registrati
        """
        invoice = await self.get_by_id(db, invoice_id)
        
        # Verifica che non ci siano allocazioni
        if invoice.payment_allocations:
            raise BusinessValidationError(
                "Impossibile eliminare una fattura con pagamenti registrati. "
                "Rimuovere prima i pagamenti."
            )
        
        # P3-Fix 9: Verifica stato work_order prima di sovrascrivere
        work_order = invoice.work_order
        if work_order:
            if work_order.status == "invoiced":
                work_order.status = "completed"
            else:
                logger.warning(
                    f"Work order {work_order.id} stato non modificato: "
                    f"stato attuale '{work_order.status}' != 'invoiced'"
                )
        
        # Elimina fattura (cascade elimina anche lines)
        await db.delete(invoice)
        await db.commit()

    async def create_payment(
        self,
        db: AsyncSession,
        payment_data: PaymentCreate,
    ) -> Payment:
        """
        Crea un nuovo pagamento con allocazioni automatiche o manuali.
        
        Steps:
        1. Verifica cliente esiste
        2. Verifica amount > 0 (già validato da Pydantic)
        3. Crea Payment
        4. Alloca su fatture secondo strategia
        5. Restituisce Payment con allocations
        
        Args:
            db: Sessione database
            payment_data: Dati del pagamento con strategia di allocazione
            
        Returns:
            Payment: Il pagamento creato con allocazioni
            
        Raises:
            NotFoundError: cliente non esiste
            BusinessValidationError: nessuna fattura aperta, importi incoerenti
        """
        # Verifica cliente esiste
        stmt = select(Client).where(Client.id == payment_data.client_id)
        result = await db.execute(stmt)
        client = result.scalar_one_or_none()
        
        if not client:
            raise NotFoundError(f"Cliente {payment_data.client_id} non trovato")
        
        # Crea Payment
        payment = Payment(
            client_id=payment_data.client_id,
            amount=payment_data.amount,
            payment_date=payment_data.payment_date,
            payment_method=payment_data.payment_method.value,
            reference=payment_data.reference,
            notes=payment_data.notes
        )
        db.add(payment)
        await db.flush()  # Genera payment.id
        
        # Alloca su fatture
        manual_allocs = None
        if payment_data.allocations:
            manual_allocs = [
                {"invoice_id": a.invoice_id, "amount": a.amount}
                for a in payment_data.allocations
            ]
        
        allocations = await self._allocate_payment(
            db,
            payment,
            strategy=payment_data.allocation_strategy or "fifo",
            manual_allocations=manual_allocs
        )
        
        await db.commit()
        await db.refresh(payment, ["allocations", "client"])
        
        return payment

    async def _allocate_payment(
        self,
        db: AsyncSession,
        payment: Payment,
        strategy: str = "fifo",
        manual_allocations: Optional[list[dict]] = None
    ) -> list[PaymentAllocation]:
        """
        Alloca un pagamento su fatture aperte del cliente.
        
        Args:
            payment: Pagamento da allocare
            strategy: "fifo", "overdue_first", "manual"
            manual_allocations: Lista [{"invoice_id": UUID, "amount": Decimal}]
        
        Returns:
            Lista di PaymentAllocation create
        
        Raises:
            BusinessValidationError: importo insufficiente, fattura non trovata, etc.
        """
        allocations_created = []
        
        if strategy == "manual":
            # Allocazione manuale esplicita
            if not manual_allocations:
                raise BusinessValidationError("Strategy 'manual' richiede lista allocations")
            
            total_to_allocate = sum(Decimal(str(a["amount"])) for a in manual_allocations)
            if total_to_allocate > payment.amount:
                raise BusinessValidationError(
                    f"Somma allocazioni ({total_to_allocate}) supera importo pagamento ({payment.amount})"
                )
            
            for alloc_data in manual_allocations:
                invoice_id = alloc_data["invoice_id"]
                amount = Decimal(str(alloc_data["amount"]))
                
                # Verifica fattura esiste e appartiene al cliente
                stmt = select(Invoice).where(
                    Invoice.id == invoice_id,
                    Invoice.client_id == payment.client_id
                ).options(selectinload(Invoice.payment_allocations))
                
                result = await db.execute(stmt)
                invoice = result.scalar_one_or_none()
                
                if not invoice:
                    raise NotFoundError(f"Fattura {invoice_id} non trovata o non appartiene al cliente")
                
                # Verifica che non si paghi più del dovuto
                if amount > invoice.remaining_amount:
                    raise BusinessValidationError(
                        f"Fattura {invoice.invoice_number}: importo allocato ({amount}) "
                        f"supera residuo ({invoice.remaining_amount})"
                    )
                
                # Crea allocazione
                allocation = PaymentAllocation(
                    payment_id=payment.id,
                    invoice_id=invoice_id,
                    amount=amount
                )
                db.add(allocation)
                allocations_created.append(allocation)
        
        elif strategy == "fifo":
            # Allocazione automatica FIFO (fatture più vecchie prima)
            stmt = select(Invoice).where(
                Invoice.client_id == payment.client_id
            ).options(
                selectinload(Invoice.payment_allocations)
            ).order_by(Invoice.invoice_date.asc())
            
            result = await db.execute(stmt)
            invoices = result.scalars().all()
            
            # Filtra solo fatture con residuo > 0
            open_invoices = [inv for inv in invoices if inv.remaining_amount > Decimal("0")]
            
            if not open_invoices:
                raise BusinessValidationError("Nessuna fattura aperta da pagare per questo cliente")
            
            remaining = payment.amount
            
            for invoice in open_invoices:
                if remaining <= Decimal("0"):
                    break
                
                to_allocate = min(remaining, invoice.remaining_amount)
                
                allocation = PaymentAllocation(
                    payment_id=payment.id,
                    invoice_id=invoice.id,
                    amount=to_allocate
                )
                db.add(allocation)
                allocations_created.append(allocation)
                
                remaining -= to_allocate
            
            # P0-Fix 6: Segnala overpayment
            if remaining > Decimal("0"):
                logger.warning(
                    f"Pagamento {payment.id}: {remaining}€ non allocati (credito residuo)"
                )
        
        elif strategy == "overdue_first":
            # Prima le scadute, poi FIFO sulle altre
            stmt = select(Invoice).where(
                Invoice.client_id == payment.client_id
            ).options(
                selectinload(Invoice.payment_allocations)
            ).order_by(
                # Prima le scadute (due_date < oggi)
                (Invoice.due_date < date.today()).desc(),
                # Poi per data fattura
                Invoice.invoice_date.asc()
            )
            
            result = await db.execute(stmt)
            invoices = result.scalars().all()
            
            open_invoices = [inv for inv in invoices if inv.remaining_amount > Decimal("0")]
            
            if not open_invoices:
                raise BusinessValidationError("Nessuna fattura aperta da pagare")
            
            remaining = payment.amount
            
            for invoice in open_invoices:
                if remaining <= Decimal("0"):
                    break
                
                to_allocate = min(remaining, invoice.remaining_amount)
                
                allocation = PaymentAllocation(
                    payment_id=payment.id,
                    invoice_id=invoice.id,
                    amount=to_allocate
                )
                db.add(allocation)
                allocations_created.append(allocation)
                
                remaining -= to_allocate
            
            # P0-Fix 6: Segnala overpayment
            if remaining > Decimal("0"):
                logger.warning(
                    f"Pagamento {payment.id}: {remaining}€ non allocati (credito residuo)"
                )
        
        else:
            raise BusinessValidationError(f"Strategia allocazione '{strategy}' non supportata")
        
        await db.flush()
        
        # Refresh per caricare relazioni
        for alloc in allocations_created:
            await db.refresh(alloc, ["payment", "invoice"])
        
        return allocations_created

    async def reallocate_payment(
        self,
        db: AsyncSession,
        payment_id: uuid.UUID,
        new_allocations: list[dict]  # [{"invoice_id": UUID, "amount": Decimal}]
    ) -> Payment:
        """
        Storna le allocazioni esistenti e ricrea nuove allocazioni.
        
        Use case: errore di registrazione, cliente chiede di riallocare su altre fatture.
        
        Steps:
        1. Verifica payment esiste
        2. Cancella tutte le allocazioni esistenti
        3. Crea nuove allocazioni secondo lista
        4. Restituisce payment aggiornato
        
        Args:
            db: Sessione database
            payment_id: UUID del pagamento
            new_allocations: Lista nuove allocazioni
            
        Returns:
            Payment: Il pagamento aggiornato
            
        Raises:
            NotFoundError: payment non esiste
            BusinessValidationError: somma nuove allocazioni > payment.amount
        """
        
        # Recupera payment
        stmt = select(Payment).where(Payment.id == payment_id).options(
            selectinload(Payment.allocations)
        )
        result = await db.execute(stmt)
        payment = result.scalar_one_or_none()
        
        if not payment:
            raise NotFoundError(f"Pagamento {payment_id} non trovato")
        
        # Verifica somma nuove allocazioni
        total_new = sum(Decimal(str(a["amount"])) for a in new_allocations)
        if total_new > payment.amount:
            raise BusinessValidationError(
                f"Somma nuove allocazioni ({total_new}) supera importo pagamento ({payment.amount})"
            )
        
        # Cancella allocazioni esistenti (CASCADE eliminerà le righe)
        stmt = delete(PaymentAllocation).where(PaymentAllocation.payment_id == payment_id)
        await db.execute(stmt)
        await db.flush()
        
        # Crea nuove allocazioni (riusa logica manuale)
        allocations = await self._allocate_payment(
            db,
            payment,
            strategy="manual",
            manual_allocations=new_allocations
        )
        
        await db.commit()
        await db.refresh(payment, ["allocations"])
        
        return payment

    async def delete_payment(
        self,
        db: AsyncSession,
        payment_id: uuid.UUID
    ) -> None:
        """
        Elimina un pagamento (e tutte le sue allocazioni tramite cascade).
        
        Use case: errore di registrazione totale.
        
        Args:
            db: Sessione database
            payment_id: UUID del pagamento
            
        Raises:
            NotFoundError: payment non esiste
        """
        stmt = select(Payment).where(Payment.id == payment_id)
        result = await db.execute(stmt)
        payment = result.scalar_one_or_none()
        
        if not payment:
            raise NotFoundError(f"Pagamento {payment_id} non trovato")
        
        await db.delete(payment)
        await db.commit()

    # Mantiene la vecchia signature per retrocompatibilità
    async def add_payment(
        self,
        db: AsyncSession,
        invoice_id: uuid.UUID,
        payment_data: PaymentCreate,
    ) -> Payment:
        """
        Registra un pagamento su una fattura (retrocompatibilità).
        
        DEPRECATA: Usa create_payment con allocation_strategy='manual'.
        
        Args:
            db: Sessione database
            invoice_id: UUID della fattura
            payment_data: Dati del pagamento
            
        Returns:
            Payment: Il pagamento registrato
        """
        # Recupera la fattura per ottenere il client_id
        stmt = select(Invoice).where(Invoice.id == invoice_id)
        result = await db.execute(stmt)
        invoice = result.scalar_one_or_none()
        
        if not invoice:
            raise NotFoundError(f"Fattura {invoice_id} non trovata")
        
        # Crea un PaymentCreate con allocazione manuale
        payment_create = PaymentCreate(
            client_id=invoice.client_id,
            amount=payment_data.amount,
            payment_date=payment_data.payment_date,
            payment_method=payment_data.payment_method,
            reference=payment_data.reference,
            notes=payment_data.notes,
            allocation_strategy="manual",
            allocations=[
                PaymentAllocationCreate(
                    invoice_id=invoice_id,
                    amount=payment_data.amount
                )
            ]
        )
        
        return await self.create_payment(db, payment_create)

    async def remove_payment(
        self,
        db: AsyncSession,
        payment_id: uuid.UUID,
    ) -> None:
        """
        Rimuove un pagamento (es. per errore di registrazione).
        
        Args:
            db: Sessione database
            payment_id: UUID del pagamento
        """
        await self.delete_payment(db, payment_id)

    async def get_overdue_invoices(
        self,
        db: AsyncSession,
    ) -> list[Invoice]:
        """
        Restituisce tutte le fatture scadute e non completamente pagate.
        
        Filtro: due_date < today AND paid_amount < total
        Ordina per: due_date ASC (più vecchie prima)
        
        Args:
            db: Sessione database
            
        Returns:
            list[Invoice]: Lista fatture scadute
        """
        today = date.today()
        
        stmt = (
            select(Invoice)
            .where(
                and_(
                    Invoice.due_date < today,
                )
            )
            .options(
                selectinload(Invoice.client),
                selectinload(Invoice.lines),
                selectinload(Invoice.payment_allocations),
            )
            .order_by(Invoice.due_date.asc())
        )
        
        result = await db.execute(stmt)
        invoices = result.scalars().all()
        
        # Filtra quelle non completamente pagate
        return [inv for inv in invoices if inv.remaining_amount > 0]

    async def get_revenue_report(
        self,
        db: AsyncSession,
        from_date: date,
        to_date: date,
    ) -> RevenueReport:
        """
        Report incassi nel periodo.
        
        Args:
            db: Sessione database
            from_date: Data inizio periodo
            to_date: Data fine periodo
            
        Returns:
            RevenueReport: Report con totali
        """
        # P3-Fix 8: Ottimizzato da 5 query a 3 query
        # Unisco count+sum fatture in una sola query
        invoice_stmt = select(
            func.count(Invoice.id),
            func.coalesce(func.sum(Invoice.total), 0)
        ).where(
            and_(
                Invoice.invoice_date >= from_date,
                Invoice.invoice_date <= to_date,
            )
        )
        invoice_result = await db.execute(invoice_stmt)
        invoices_count, total_invoiced = invoice_result.one()
        
        # Unisco count+sum pagamenti in una sola query
        payment_stmt = select(
            func.count(Payment.id),
            func.coalesce(func.sum(Payment.amount), 0)
        ).where(
            and_(
                Payment.payment_date >= from_date,
                Payment.payment_date <= to_date,
            )
        )
        payment_result = await db.execute(payment_stmt)
        payments_count, total_paid = payment_result.one()
        
        # Totale residuo (tutte le fatture non pagate completamente)
        unpaid_stmt = (
            select(Invoice)
            .options(selectinload(Invoice.payment_allocations))
            .where(
                and_(
                    Invoice.invoice_date >= from_date,
                    Invoice.invoice_date <= to_date,
                )
            )
        )
        unpaid_result = await db.execute(unpaid_stmt)
        unpaid_invoices = unpaid_result.scalars().all()
        
        total_unpaid = sum(
            inv.remaining_amount for inv in unpaid_invoices
        )
        
        return RevenueReport(
            total_invoiced=total_invoiced,
            total_paid=total_paid,
            total_unpaid=total_unpaid,
            invoices_count=invoices_count,
            payments_count=payments_count,
        )
