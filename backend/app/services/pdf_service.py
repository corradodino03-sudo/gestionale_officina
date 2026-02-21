"""
Service per la generazione di PDF con WeasyPrint + Jinja2.
Progetto: Garage Manager (Gestionale Officina)
"""

import logging
import os
from datetime import date
from jinja2 import Environment, FileSystemLoader
from app.models.invoice import Invoice
from app.core.config import settings

logger = logging.getLogger(__name__)

# Path alle cartelle templates
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

# Lazy import of weasyprint to avoid startup errors if GTK libraries aren't available
def _get_weasyprint():
    """Lazy import of weasyprint to handle missing GTK libraries gracefully."""
    try:
        from weasyprint import HTML, CSS
        return HTML, CSS
    except OSError as e:
        raise RuntimeError(
            "WeasyPrint dependencies not found. Please install GTK libraries: "
            "brew install gtk+3"
        ) from e


class PdfService:
    """
    Genera PDF da template HTML/CSS usando WeasyPrint + Jinja2.
    Il chiamante è responsabile di passare un Invoice con tutte
    le relazioni già caricate (client, lines, work_order).
    """

    def __init__(self):
        self.env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))

    def generate_invoice_pdf(self, invoice: Invoice) -> bytes:
        """
        Genera il PDF di una fattura.
        
        Args:
            invoice: Oggetto Invoice con client e lines caricati
        
        Returns:
            bytes: PDF binario pronto per il download
        """
        # Lazy import weasyprint
        HTML, CSS = _get_weasyprint()
        
        template = self.env.get_template("invoice_template.html")
        
        # Determina dati di fatturazione
        billing_name = invoice.bill_to_name or (
            f"{invoice.client.name} {invoice.client.surname or ''}".strip()
        )
        billing_address = invoice.bill_to_address or invoice.client.address
        billing_tax_id = invoice.bill_to_tax_id or (
            invoice.client.vat_number or invoice.client.fiscal_code
        )
        
        # Raggruppamento IVA per la tabella riepilogativa
        vat_summary = {}
        for line in invoice.lines:
            rate = line.vat_rate
            if rate not in vat_summary:
                vat_summary[rate] = {
                    "rate": rate,
                    "subtotal": 0,
                    "vat_amount": 0,
                    "nature": invoice.vat_exemption_code or ""
                }
            vat_summary[rate]["subtotal"] += float(line.subtotal)
            vat_summary[rate]["vat_amount"] += float(line.vat_amount)
            
        # Veicolo (da work_order, già caricato da invoice_service.get_by_id)
        vehicle = (
            invoice.work_order.vehicle
            if invoice.work_order and invoice.work_order.vehicle
            else None
        )
        
        context = {
            # Dati officina (da settings)
            "garage_name": settings.invoice_company_name,
            "garage_address": settings.invoice_address,
            "garage_vat": settings.invoice_vat_number,
            "garage_phone": settings.invoice_phone,
            "garage_email": settings.invoice_email,
            
            # Fattura
            "invoice": invoice,
            "vat_summary": list(vat_summary.values()),
            "oggi": date.today().strftime("%d/%m/%Y"),
            
            # Dati cliente fatturazione (terzi se bill_to_name, altrimenti cliente)
            "billing_name": billing_name,
            "billing_address": billing_address,
            "billing_tax_id": billing_tax_id,
            
            # Veicolo (da work_order, già caricato da invoice_service.get_by_id)
            "vehicle": vehicle,
            "work_order": invoice.work_order,
            
            # Flag utili per il template
            "is_vat_exempt": invoice.vat_exemption,
            "has_stamp_duty": invoice.stamp_duty_applied,
            "is_split_payment": invoice.split_payment,
        }
        
        html_out = template.render(context)
        css = CSS(filename=os.path.join(TEMPLATES_DIR, "invoice_style.css"))
        
        pdf_bytes = HTML(string=html_out, base_url=TEMPLATES_DIR).write_pdf(stylesheets=[css])
        return pdf_bytes
