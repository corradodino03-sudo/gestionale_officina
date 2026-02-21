"""
Pytest configuration and fixtures for InvoiceService tests.

Note: This conftest uses pure mocks without importing app modules
to avoid Python version compatibility issues (project requires 3.11+).
"""

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


# ============================================================
# Fixtures per AsyncSession Mock
# ============================================================


@pytest.fixture
def mock_db():
    """Crea un mock di AsyncSession."""
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = MagicMock()
    return db


# ============================================================
# Fixtures per Client Mock (senza importare il modello)
# ============================================================


class MockClient:
    """Mock del modello Client."""
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', uuid.uuid4())
        self.first_name = kwargs.get('first_name', 'Mario')
        self.last_name = kwargs.get('last_name', 'Rossi')
        self.company_name = kwargs.get('company_name', None)
        self.vat_number = kwargs.get('vat_number', 'IT12345678901')
        self.tax_code = kwargs.get('tax_code', 'RSSMRA85T10A562X')
        self.address = kwargs.get('address', 'Via Roma 1')
        self.city = kwargs.get('city', 'Roma')
        self.province = kwargs.get('province', 'RM')
        self.zip_code = kwargs.get('zip_code', '00100')
        self.vat_regime = kwargs.get('vat_regime', None)
        self.vat_exemption = kwargs.get('vat_exemption', False)
        self.vat_exemption_code = kwargs.get('vat_exemption_code', None)
        self.default_vat_rate = kwargs.get('default_vat_rate', Decimal("22.00"))
        self.default_discount_percent = kwargs.get('default_discount_percent', Decimal("0"))
        self.payment_terms_days = kwargs.get('payment_terms_days', 30)
        self.credit_limit = kwargs.get('credit_limit', None)
        self.credit_limit_action = kwargs.get('credit_limit_action', 'block')
        self.payment_method_default = kwargs.get('payment_method_default', 'bank_transfer')
        self.effective_billing_address = kwargs.get('effective_billing_address', {
            "address": "Via Roma 1",
            "city": "Roma",
            "province": "RM",
            "zip_code": "00100",
        })


@pytest.fixture
def mock_client():
    """Crea un mock di Client con dati base."""
    return MockClient()


@pytest.fixture
def mock_client_forfettario():
    """Crea un mock di Client in regime forfettario (RF19)."""
    return MockClient(
        first_name="Luigi",
        last_name="Bianchi",
        vat_number="IT98765432109",
        tax_code="BNCLGU70A01A562Y",
        vat_regime="RF19",
        address="Via Milano 10",
        city="Milano",
        province="MI",
        zip_code="20100",
        effective_billing_address={
            "address": "Via Milano 10",
            "city": "Milano",
            "province": "MI",
            "zip_code": "20100",
        }
    )


@pytest.fixture
def mock_client_minimi():
    """Crea un mock di Client in regime dei minimi (RF02)."""
    return MockClient(
        first_name="Anna",
        last_name="Verdi",
        vat_number="IT11223344556",
        tax_code="VRDNNN85S50A562Z",
        vat_regime="RF02",
        payment_terms_days=60,
        address="Via Napoli 5",
        city="Napoli",
        province="NA",
        zip_code="80100",
        effective_billing_address={
            "address": "Via Napoli 5",
            "city": "Napoli",
            "province": "NA",
            "zip_code": "80100",
        }
    )


# ============================================================
# Fixtures per WorkOrder Mock
# ============================================================


class MockWorkOrderItem:
    """Mock di WorkOrderItem."""
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', uuid.uuid4())
        self.item_type = kwargs.get('item_type', 'labor')
        self.description = kwargs.get('description', 'Test item')
        self.quantity = kwargs.get('quantity', Decimal("1"))
        self.unit_price = kwargs.get('unit_price', Decimal("50.00"))


class MockPart:
    """Mock di Part."""
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', uuid.uuid4())
        self.description = kwargs.get('description', 'Test part')
        self.vat_rate = kwargs.get('vat_rate', Decimal("22.00"))


class MockPartUsage:
    """Mock di PartUsage."""
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', uuid.uuid4())
        self.quantity = kwargs.get('quantity', Decimal("1"))
        self.unit_price = kwargs.get('unit_price', Decimal("25.00"))
        self.part = kwargs.get('part', MockPart())


class MockWorkOrder:
    """Mock di WorkOrder."""
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', uuid.uuid4())
        self.status = kwargs.get('status', 'completed')
        self.client = kwargs.get('client', None)
        self.client_id = kwargs.get('client_id', uuid.uuid4())
        self.invoice = kwargs.get('invoice', None)
        self.items = kwargs.get('items', [])
        self.part_usages = kwargs.get('part_usages', [])


@pytest.fixture
def mock_work_order(mock_client):
    """Crea un mock di WorkOrder completato."""
    return MockWorkOrder(
        client=mock_client,
        items=[
            MockWorkOrderItem(
                item_type="labor",
                description="Cambio olio",
                quantity=Decimal("1"),
                unit_price=Decimal("50.00")
            ),
            MockWorkOrderItem(
                item_type="service",
                description="Tagliando",
                quantity=Decimal("1"),
                unit_price=Decimal("100.00")
            ),
        ],
        part_usages=[
            MockPartUsage(
                quantity=Decimal("2"),
                unit_price=Decimal("25.00"),
                part=MockPart(description="Filtro olio")
            )
        ]
    )


@pytest.fixture
def mock_work_order_invoiced(mock_client):
    """Crea un mock di WorkOrder già fatturato."""
    invoice = MagicMock()
    invoice.invoice_number = "2025/0001"
    return MockWorkOrder(
        client=mock_client,
        invoice=invoice
    )


@pytest.fixture
def mock_work_order_not_completed(mock_client):
    """Crea un mock di WorkOrder non completato."""
    return MockWorkOrder(
        client=mock_client,
        status="in_progress",
        items=[],
        part_usages=[]
    )


# ============================================================
# Fixtures per Invoice Mock
# ============================================================


class MockInvoice:
    """Mock di Invoice."""
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', uuid.uuid4())
        self.work_order_id = kwargs.get('work_order_id', uuid.uuid4())
        self.client_id = kwargs.get('client_id', uuid.uuid4())
        self.client = kwargs.get('client', None)
        self.bill_to_client_id = kwargs.get('bill_to_client_id', None)
        self.bill_to_name = kwargs.get('bill_to_name', None)
        self.bill_to_tax_id = kwargs.get('bill_to_tax_id', None)
        self.bill_to_address = kwargs.get('bill_to_address', None)
        self.invoice_number = kwargs.get('invoice_number', "2025/0001")
        self.invoice_date = kwargs.get('invoice_date', date.today())
        self.due_date = kwargs.get('due_date', date.today() + timedelta(days=30))
        self.subtotal = kwargs.get('subtotal', Decimal("200.00"))
        self.vat_rate = kwargs.get('vat_rate', Decimal("22.00"))
        self.vat_amount = kwargs.get('vat_amount', Decimal("44.00"))
        self.total = kwargs.get('total', Decimal("244.00"))
        self.vat_exemption = kwargs.get('vat_exemption', False)
        self.vat_exemption_code = kwargs.get('vat_exemption_code', None)
        self.split_payment = kwargs.get('split_payment', False)
        self.notes = kwargs.get('notes', None)
        self.customer_notes = kwargs.get('customer_notes', None)
        self.stamp_duty_applied = kwargs.get('stamp_duty_applied', False)
        self.stamp_duty_amount = kwargs.get('stamp_duty_amount', Decimal("0.00"))
        self.payment_iban = kwargs.get('payment_iban', None)
        self.payment_reference = kwargs.get('payment_reference', None)
        self.lines = kwargs.get('lines', [])
        self.payment_allocations = kwargs.get('payment_allocations', [])
        self.work_order = kwargs.get('work_order', None)
    
    @property
    def status(self):
        """Calcola lo stato della fattura."""
        paid_amount = sum(a.amount for a in self.payment_allocations)
        if paid_amount >= self.total:
            return "paid"
        elif paid_amount > 0:
            return "partial"
        elif self.due_date < date.today():
            return "overdue"
        else:
            return "unpaid"
    
    @property
    def paid_amount(self):
        """Calcola l'importo pagato."""
        return sum(a.amount for a in self.payment_allocations)
    
    @property
    def remaining_amount(self):
        """Calcola l'importo residuo."""
        return self.total - self.paid_amount


@pytest.fixture
def mock_invoice(mock_client):
    """Crea un mock di Invoice."""
    return MockInvoice(
        client=mock_client,
        invoice_date=date.today(),
        due_date=date.today() + timedelta(days=30),
    )


# ============================================================
# Fixtures per Payment Mock
# ============================================================


class MockPaymentAllocation:
    """Mock di PaymentAllocation."""
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', uuid.uuid4())
        self.payment_id = kwargs.get('payment_id', uuid.uuid4())
        self.invoice_id = kwargs.get('invoice_id', uuid.uuid4())
        self.amount = kwargs.get('amount', Decimal("100.00"))
        self.payment = kwargs.get('payment', None)
        self.invoice = kwargs.get('invoice', None)


class MockPayment:
    """Mock di Payment."""
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', uuid.uuid4())
        self.client_id = kwargs.get('client_id', uuid.uuid4())
        self.amount = kwargs.get('amount', Decimal("100.00"))
        self.payment_date = kwargs.get('payment_date', date.today())
        self.payment_method = kwargs.get('payment_method', 'bank_transfer')
        self.reference = kwargs.get('reference', 'TEST/001')
        self.notes = kwargs.get('notes', None)
        self.allocations = kwargs.get('allocations', [])


@pytest.fixture
def mock_payment(mock_client):
    """Crea un mock di Payment."""
    return MockPayment(client_id=mock_client.id)


@pytest.fixture
def mock_payment_allocation(mock_invoice, mock_payment):
    """Crea un mock di PaymentAllocation."""
    return MockPaymentAllocation(
        payment_id=mock_payment.id,
        invoice_id=mock_invoice.id,
        amount=Decimal("100.00")
    )


# ============================================================
# Fixtures per Schemas
# ============================================================


class MockCreateInvoiceFromWorkOrder:
    """Mock di CreateInvoiceFromWorkOrder."""
    def __init__(self, **kwargs):
        self.invoice_date = kwargs.get('invoice_date', date.today())
        self.due_date = kwargs.get('due_date', None)
        self.vat_rate = kwargs.get('vat_rate', None)
        self.bill_to_client_id = kwargs.get('bill_to_client_id', None)
        self.claim_number = kwargs.get('claim_number', None)
        self.customer_notes = kwargs.get('customer_notes', None)


@pytest.fixture
def create_invoice_data():
    """Crea i dati per creare una fattura da work order."""
    return MockCreateInvoiceFromWorkOrder()


class MockInvoiceUpdate:
    """Mock di InvoiceUpdate."""
    def __init__(self, **kwargs):
        self.notes = kwargs.get('notes', None)
        self.customer_notes = kwargs.get('customer_notes', None)
        self.due_date = kwargs.get('due_date', None)


@pytest.fixture
def invoice_update_data():
    """Crea i dati per aggiornare una fattura."""
    return MockInvoiceUpdate(
        notes="Nota interna di test",
        customer_notes="Nota per il cliente",
        due_date=date.today() + timedelta(days=60),
    )
