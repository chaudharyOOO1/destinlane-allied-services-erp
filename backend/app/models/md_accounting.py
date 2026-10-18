"""MD-only books. Posted vouchers are immutable; reversals are new vouchers."""
from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, Numeric, JSON, ForeignKey, CheckConstraint, UniqueConstraint
from app.models.base import BaseModel


class AccountingSetup(BaseModel):
    __tablename__ = 'md_accounting_setup'
    id = Column(Integer, primary_key=True)
    books_start_date = Column(Date, nullable=False)
    financial_year_start_month = Column(Integer, nullable=False, default=4)
    closed_through = Column(Date)
    opening_confirmed = Column(Boolean, nullable=False, default=False)
    opening_reason = Column(String(1000), nullable=False, default='')
    version = Column(Integer, nullable=False, default=1)


class LedgerAccount(BaseModel):
    __tablename__ = 'md_ledger_accounts'
    code = Column(String(20), nullable=False, unique=True)
    name = Column(String(150), nullable=False)
    section = Column(String(30), nullable=False)
    group_name = Column(String(120), nullable=False)
    is_bank = Column(Boolean, nullable=False, default=False)
    bank_details = Column(JSON, nullable=False, default=dict)
    is_active = Column(Boolean, nullable=False, default=True)
    version = Column(Integer, nullable=False, default=1)


class JournalEntry(BaseModel):
    __tablename__ = 'md_journal_entries'
    entry_date = Column(Date, nullable=False, index=True)
    kind = Column(String(20), nullable=False)
    narration = Column(String(1000), nullable=False)
    party = Column(String(200), nullable=False, default='')
    reference = Column(String(150), nullable=False, default='')
    status = Column(String(20), nullable=False, default='DRAFT')
    version = Column(Integer, nullable=False, default=1)
    created_by = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    posted_by = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'))
    posted_at = Column(DateTime(timezone=True))
    reversal_of = Column(Integer, ForeignKey('md_journal_entries.id', ondelete='RESTRICT'), unique=True)
    __table_args__ = (CheckConstraint("status in ('DRAFT','POSTED')", name='md_journal_status'),)


class JournalLine(BaseModel):
    __tablename__ = 'md_journal_lines'
    entry_id = Column(Integer, ForeignKey('md_journal_entries.id', ondelete='RESTRICT'), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey('md_ledger_accounts.id', ondelete='RESTRICT'), nullable=False, index=True)
    debit = Column(Numeric(14,2), nullable=False, default=0)
    credit = Column(Numeric(14,2), nullable=False, default=0)
    description = Column(String(500), nullable=False, default='')
    __table_args__ = (CheckConstraint('(debit > 0 and credit = 0) or (credit > 0 and debit = 0)', name='md_line_one_side'),)


class BankStatementLine(BaseModel):
    __tablename__ = 'md_bank_statement_lines'
    account_id = Column(Integer, ForeignKey('md_ledger_accounts.id', ondelete='RESTRICT'), nullable=False, index=True)
    statement_id = Column(String(150), nullable=False)
    entry_date = Column(Date, nullable=False)
    reference = Column(String(150), nullable=False, default='')
    description = Column(String(500), nullable=False, default='')
    debit = Column(Numeric(14,2), nullable=False, default=0)
    credit = Column(Numeric(14,2), nullable=False, default=0)
    imported_by = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    matched_line_id = Column(Integer, ForeignKey('md_journal_lines.id', ondelete='RESTRICT'), unique=True)
    matched_by = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'))
    matched_at = Column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint('account_id','statement_id'), CheckConstraint('(debit > 0 and credit = 0) or (credit > 0 and debit = 0)', name='md_statement_one_side'))


class AccountingAudit(BaseModel):
    __tablename__ = 'md_accounting_audit'
    actor_id = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    action = Column(String(40), nullable=False)
    reference = Column(String(150), nullable=False, default='')
    details = Column(JSON, nullable=False, default=dict)
