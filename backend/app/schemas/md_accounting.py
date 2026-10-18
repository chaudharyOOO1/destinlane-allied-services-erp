from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Section = Literal['NON_CURRENT_ASSET','CURRENT_ASSET','EQUITY','NON_CURRENT_LIABILITY','CURRENT_LIABILITY','REVENUE','EXPENSE']


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Version(Input):
    version: int = Field(ge=1)


class SetupInput(Version):
    books_start_date: date
    financial_year_start_month: int = Field(default=4,ge=1,le=12)
    confirm_opening: bool = False
    opening_reason: str = Field(default='',max_length=1000)


class PeriodInput(Version):
    through: date | None = None
    reason: str = Field(min_length=10,max_length=1000)


class BankDetails(Input):
    bank_name: str = Field(default='',max_length=150)
    account_number: str = Field(default='',max_length=35,pattern=r'^[A-Za-z0-9 -]*$')
    ifsc: str = Field(default='',max_length=11,pattern=r'^$|^[A-Z]{4}0[A-Z0-9]{6}$')


class AccountInput(Input):
    code: str = Field(min_length=2,max_length=20,pattern=r'^[A-Z0-9_-]+$')
    name: str = Field(min_length=2,max_length=150)
    section: Section
    group_name: str = Field(min_length=2,max_length=120)
    is_bank: bool = False
    bank_details: BankDetails = Field(default_factory=BankDetails)
    is_active: bool = True

    @model_validator(mode='after')
    def valid_bank(self):
        if self.is_bank and self.section != 'CURRENT_ASSET':
            raise ValueError('A bank ledger must be a current asset account.')
        return self


class AccountUpdate(AccountInput,Version):
    pass


class LineInput(Input):
    account_id: int = Field(gt=0)
    debit: Decimal = Field(default=Decimal('0.00'),ge=0,max_digits=14,decimal_places=2)
    credit: Decimal = Field(default=Decimal('0.00'),ge=0,max_digits=14,decimal_places=2)
    description: str = Field(default='',max_length=500)

    @model_validator(mode='after')
    def one_side(self):
        if not ((self.debit > 0 and self.credit == 0) or (self.credit > 0 and self.debit == 0)):
            raise ValueError('Each line requires either a debit or a credit, never both.')
        return self


class JournalInput(Input):
    entry_date: date
    kind: Literal['OPENING','PAYMENT','RECEIPT','CONTRA','JOURNAL'] = 'JOURNAL'
    narration: str = Field(min_length=3,max_length=1000)
    party: str = Field(default='',max_length=200)
    reference: str = Field(default='',max_length=150)
    lines: list[LineInput] = Field(min_length=2,max_length=200)


class JournalUpdate(JournalInput,Version):
    pass


class ReversalInput(Version):
    entry_date: date
    reason: str = Field(min_length=10,max_length=1000)


class StatementInput(Input):
    statement_id: str = Field(min_length=1,max_length=150)
    entry_date: date
    reference: str = Field(default='',max_length=150)
    description: str = Field(default='',max_length=500)
    debit: Decimal = Field(default=Decimal('0.00'),ge=0,max_digits=14,decimal_places=2)
    credit: Decimal = Field(default=Decimal('0.00'),ge=0,max_digits=14,decimal_places=2)

    @model_validator(mode='after')
    def one_side(self):
        if not ((self.debit > 0 and self.credit == 0) or (self.credit > 0 and self.debit == 0)):
            raise ValueError('Bank statement rows require one debit withdrawal or credit deposit.')
        return self


class StatementBatch(Input):
    account_id: int = Field(gt=0)
    rows: list[StatementInput] = Field(min_length=1,max_length=5000)


class MatchInput(Input):
    journal_line_id: int = Field(gt=0)


class ReconciliationInput(Input):
    account_id: int = Field(gt=0)
    as_of: date
    statement_balance: Decimal = Field(max_digits=14,decimal_places=2)
    reference: str = Field(min_length=3,max_length=150)


class GSTInput(Input):
    taxable_amount: Decimal = Field(ge=0,max_digits=14,decimal_places=2)
    rate: Decimal = Field(ge=0,le=100,max_digits=5,decimal_places=2)
    supply: Literal['INTRA_STATE','INTER_STATE']
