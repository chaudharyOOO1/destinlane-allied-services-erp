"""Operational accounts writes. MD double-entry books use their own service."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import require_accounts_or_admin
from app.core.business_time import business_date
from app.core.database import get_db

router = APIRouter()
Money = Annotated[Decimal, Field(ge=0, le=99999999, max_digits=10, decimal_places=2)]
InvoiceState = Literal['DRAFT','SENT','PAID','OVERDUE','CANCELLED']


class Command(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class InvoiceCreate(Command):
    client_id: int = Field(gt=0, le=2147483647)
    invoice_number: str = Field(min_length=1, max_length=100)
    billing_month: str = Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    issue_date: date = Field(default_factory=business_date)
    due_date: date
    subtotal: Money
    tax_rate: Decimal = Field(default=Decimal('18'), ge=0, le=Decimal('99.99'), max_digits=4, decimal_places=2)
    tax_mode: Literal['INTRA','INTER'] = 'INTRA'
    status: InvoiceState = 'DRAFT'
    clearance_status: Literal['PENDING','PARTIAL','PAID'] = 'PENDING'
    notes: str | None = Field(default=None, max_length=5000)

    @model_validator(mode='after')
    def dates(self):
        if self.due_date < self.issue_date: raise ValueError('Due date cannot precede issue date')
        return self


class InvoicePatch(Command):
    status: InvoiceState | None = None
    clearance_status: Literal['PENDING','PARTIAL','PAID'] | None = None
    due_date: date | None = None
    billing_month: str | None = Field(default=None, pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator('status','clearance_status','due_date','billing_month')
    @classmethod
    def not_null(cls,value):
        if value is None: raise ValueError('This field cannot be null')
        return value


class ExpenseCreate(Command):
    category: str = Field(min_length=1, max_length=100)
    amount: Money
    expense_date: date = Field(default_factory=business_date)
    branch: str | None = Field(default=None, max_length=150)
    client_id: int | None = Field(default=None, gt=0, le=2147483647)
    description: str | None = Field(default=None, max_length=5000)


class BookkeepingCreate(Command):
    account_type: str = Field(min_length=1, max_length=100)
    entry_date: date = Field(default_factory=business_date)
    reference_type: str | None = Field(default=None, max_length=100)
    reference_id: str | None = Field(default=None, max_length=200)
    debit: Money = Decimal('0')
    credit: Money = Decimal('0')
    description: str | None = Field(default=None, max_length=5000)

    @model_validator(mode='after')
    def one_side(self):
        if (self.debit > 0) == (self.credit > 0): raise ValueError('Enter one positive debit or credit per ledger line')
        return self


def save(db, query, data):
    try:
        row = db.execute(text(query), data).mappings().first()
        if not row: raise HTTPException(404,'Record not found')
        result = dict(row)
        db.commit()
        return result
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,'Check for a duplicate reference or unavailable linked record') from None


def insert(db, table, data):
    # Only server-defined table names and Pydantic field names reach this helper.
    columns = ', '.join(data)
    values = ', '.join(f':{key}' for key in data)
    return save(db, f'insert into {table} ({columns}) values ({values}) returning *', data)


@router.post('/accounts/invoices')
def create_invoice(payload:InvoiceCreate, db:Session=Depends(get_db), current_user=Depends(require_accounts_or_admin)):
    data = payload.model_dump(exclude={'tax_mode'})
    tax = (payload.subtotal * payload.tax_rate / 100).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    cgst = (tax/2).quantize(Decimal('.01'), rounding=ROUND_HALF_UP) if payload.tax_mode=='INTRA' else Decimal(0)
    data.update(cgst=cgst, sgst=tax-cgst if payload.tax_mode=='INTRA' else Decimal(0),
                igst=tax if payload.tax_mode=='INTER' else Decimal(0), tax_amount=tax, total_amount=payload.subtotal+tax)
    return insert(db,'invoices',data)


@router.patch('/accounts/invoices/{invoice_id}')
def update_invoice(invoice_id:int, payload:InvoicePatch, db:Session=Depends(get_db), current_user=Depends(require_accounts_or_admin)):
    data = payload.model_dump(exclude_unset=True)
    if not data: raise HTTPException(400,'No editable fields supplied')
    sets = ', '.join(f'{key}=:{key}' for key in data)
    return save(db, f'update invoices set {sets},updated_at=now() where id=:id returning *', {**data,'id':invoice_id})


@router.post('/accounts/expenses')
def create_expense(payload:ExpenseCreate, db:Session=Depends(get_db), current_user=Depends(require_accounts_or_admin)):
    return insert(db,'expenses',payload.model_dump())


@router.post('/accounts/bookkeeping')
def create_bookkeeping_entry(payload:BookkeepingCreate, db:Session=Depends(get_db), current_user=Depends(require_accounts_or_admin)):
    return insert(db,'bookkeeping_ledger',payload.model_dump())
