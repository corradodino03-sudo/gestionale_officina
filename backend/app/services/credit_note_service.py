import logging
import uuid
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BusinessValidationError, ConflictError, NotFoundError
from app.models.invoice import Invoice, CreditNote, CreditNoteLine
from app.schemas.invoice import PartialCreditNoteRequest

logger = logging.getLogger(__name__)

class CreditNoteService:
    async def create_from_invoice(
        self,
        db: AsyncSession,
        invoice_id: uuid.UUID,
        reason: str,
    ) -> CreditNote:
        """
        Crea una nota di credito a storno totale di una fattura.
        Copia tutte le righe con segno negativo.
        """
        # Recupera la fattura
        stmt = select(Invoice).where(Invoice.id == invoice_id).options(
            selectinload(Invoice.lines),
            selectinload(Invoice.credit_notes),
        )
        result = await db.execute(stmt)
        invoice = result.scalar_one_or_none()
        
        if not invoice:
            raise NotFoundError(f"Fattura {invoice_id} non trovata")
            
        # Verifica che non esista già una nota di credito totale
        # (Semplificazione: se la somma dei totali delle note di credito eguaglia il totale fattura)
        credited_amount = sum(abs(cn.total) for cn in invoice.credit_notes)
        if credited_amount >= invoice.total:
            raise BusinessValidationError(f"La fattura {invoice.invoice_number} è già stata completamente stornata")

        cn_date = date.today()
        cn_number = await self._generate_credit_note_number(db, cn_date)
        
        subtotal = Decimal("0")
        vat_amount = Decimal("0")
        stamp_duty = -invoice.stamp_duty_amount if invoice.stamp_duty_applied else Decimal("0")
        
        cn_lines = []
        for line in invoice.lines:
            # Crea riga con segno negativo (sull'unit_price)
            # In questo modo subtotal e total della riga saranno negativi
            cn_line = CreditNoteLine(
                line_type=line.line_type,
                description=line.description,
                quantity=line.quantity,
                unit_price=-line.unit_price,  # Segno negativo
                vat_rate=line.vat_rate,
                discount_percent=line.discount_percent,
                discount_amount=line.discount_amount,
                line_number=line.line_number,
            )
            cn_lines.append(cn_line)
            
            # Calcolo importi
            gross = line.quantity * (-line.unit_price)
            discount_amount = (gross * Decimal(str(line.discount_percent))) / Decimal("100")
            line_subtotal = (gross - discount_amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            line_vat = (line_subtotal * line.vat_rate) / Decimal("100")
            line_vat = line_vat.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            
            subtotal += line_subtotal
            vat_amount += line_vat
            
        total = subtotal + vat_amount + stamp_duty
        
        credit_note = CreditNote(
            invoice_id=invoice.id,
            client_id=invoice.client_id,
            credit_note_number=cn_number,
            credit_note_date=cn_date,
            reason=reason,
            subtotal=subtotal,
            vat_amount=vat_amount,
            total=total,
            stamp_duty_amount=stamp_duty,
        )
        
        for line in cn_lines:
            credit_note.lines.append(line)
            
        db.add(credit_note)
        
        try:
            await db.commit()
            await db.refresh(credit_note)
        except IntegrityError as e:
            await db.rollback()
            logger.error(f"Errore di integrità durante creazione nota di credito: {e}")
            raise ConflictError("Errore durante la creazione della nota di credito")
            
        return await self.get_by_id(db, credit_note.id)

    async def create_partial(
        self,
        db: AsyncSession,
        invoice_id: uuid.UUID,
        request: PartialCreditNoteRequest,
    ) -> CreditNote:
        """
        Crea una nota di credito a storno parziale di una fattura.
        """
        stmt = select(Invoice).where(Invoice.id == invoice_id).options(
            selectinload(Invoice.lines),
            selectinload(Invoice.credit_notes),
        )
        result = await db.execute(stmt)
        invoice = result.scalar_one_or_none()
        
        if not invoice:
            raise NotFoundError(f"Fattura {invoice_id} non trovata")
            
        # Mappa le righe fattura per ID
        invoice_lines_map = {str(line.id): line for line in invoice.lines}
        
        cn_date = date.today()
        cn_number = await self._generate_credit_note_number(db, cn_date)
        
        subtotal = Decimal("0")
        vat_amount = Decimal("0")
        
        cn_lines = []
        for req_line in request.lines:
            line_id_str = str(req_line.invoice_line_id)
            if line_id_str not in invoice_lines_map:
                raise BusinessValidationError(f"Riga fattura {req_line.invoice_line_id} non trovata")
                
            orig_line = invoice_lines_map[line_id_str]
            
            if req_line.quantity > orig_line.quantity:
                raise BusinessValidationError(
                    f"Quantità da stornare ({req_line.quantity}) maggiore della "
                    f"quantità originale ({orig_line.quantity}) per riga {orig_line.description}"
                )
                
            cn_line = CreditNoteLine(
                line_type=orig_line.line_type,
                description=orig_line.description,
                quantity=req_line.quantity,
                unit_price=-orig_line.unit_price,  # Segno negativo
                vat_rate=orig_line.vat_rate,
                discount_percent=orig_line.discount_percent,
                discount_amount=orig_line.discount_amount,
                line_number=orig_line.line_number,
            )
            cn_lines.append(cn_line)
            
            # Calcolo importi
            gross = req_line.quantity * (-orig_line.unit_price)
            discount_amount = (gross * Decimal(str(orig_line.discount_percent))) / Decimal("100")
            line_subtotal = (gross - discount_amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            line_vat = (line_subtotal * orig_line.vat_rate) / Decimal("100")
            line_vat = line_vat.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            
            subtotal += line_subtotal
            vat_amount += line_vat
            
        # Controllo che il totale stornato non superi il totale fattura
        credited_amount = sum(abs(cn.total) for cn in invoice.credit_notes)
        new_total_abs = abs(subtotal + vat_amount)
        if credited_amount + new_total_abs > invoice.total:
            raise BusinessValidationError("L'importo totale stornato supera il totale della fattura originale")
            
        total = subtotal + vat_amount
        
        # Semplificazione: nello storno parziale non gestiamo in automatico la marca da bollo parziale
        stamp_duty = Decimal("0.00")
        
        credit_note = CreditNote(
            invoice_id=invoice.id,
            client_id=invoice.client_id,
            credit_note_number=cn_number,
            credit_note_date=cn_date,
            reason=request.reason,
            subtotal=subtotal,
            vat_amount=vat_amount,
            total=total,
            stamp_duty_amount=stamp_duty,
        )
        
        for line in cn_lines:
            credit_note.lines.append(line)
            
        db.add(credit_note)
        
        try:
            await db.commit()
            await db.refresh(credit_note)
        except IntegrityError as e:
            await db.rollback()
            logger.error(f"Errore di integrità durante creazione nota di credito parziale: {e}")
            raise ConflictError("Errore durante la creazione della nota di credito parziale")
            
        return await self.get_by_id(db, credit_note.id)

    async def get_by_id(self, db: AsyncSession, credit_note_id: uuid.UUID) -> CreditNote:
        stmt = select(CreditNote).where(CreditNote.id == credit_note_id).options(
            selectinload(CreditNote.lines),
            selectinload(CreditNote.invoice),
            selectinload(CreditNote.client),
        )
        result = await db.execute(stmt)
        cn = result.scalar_one_or_none()
        if not cn:
            raise NotFoundError(f"Nota di credito {credit_note_id} non trovata")
        return cn

    async def get_all(self, db: AsyncSession) -> list[CreditNote]:
        stmt = select(CreditNote).options(
            selectinload(CreditNote.lines),
            selectinload(CreditNote.invoice),
            selectinload(CreditNote.client),
        ).order_by(CreditNote.credit_note_date.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_invoice(self, db: AsyncSession, invoice_id: uuid.UUID) -> list[CreditNote]:
        stmt = select(CreditNote).where(CreditNote.invoice_id == invoice_id).options(
            selectinload(CreditNote.lines),
            selectinload(CreditNote.invoice),
            selectinload(CreditNote.client),
        ).order_by(CreditNote.credit_note_date.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def _generate_credit_note_number(self, db: AsyncSession, cn_date: date) -> str:
        """Genera numerazione NC-YYYY/NNNN"""
        year = cn_date.year
        year_prefix = f"NC-{year}/"
        
        # Chiave di lock separata per le note di credito
        lock_key = year + 1000000  # Evitare conflitti con le fatture
        await db.execute(text("SELECT pg_advisory_xact_lock(:lock_key)"), {"lock_key": lock_key})
        
        stmt = (
            select(CreditNote)
            .where(CreditNote.credit_note_number.like(f"{year_prefix}%"))
            .order_by(CreditNote.credit_note_number.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        last_cn = result.scalar_one_or_none()
        
        if last_cn:
            last_number = int(last_cn.credit_note_number.split("/")[1])
            next_number = last_number + 1
        else:
            next_number = 1
            
        if next_number > 9999:
            raise ConflictError(f"Limite numerazione note di credito raggiunto per l'anno {year}")
            
        return f"{year_prefix}{next_number:04d}"
