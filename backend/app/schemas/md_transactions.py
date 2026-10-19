"""Business-facing input; callers cannot provide ledger lines, totals or status."""
from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import Field
from app.schemas.md_accounting import Input


class MoneyRecord(Input):
    transaction_type: Literal['MONEY_OUT','MONEY_IN','TRANSFER']
    entry_date: date
    bank_account_id: int = Field(gt=0)
    counter_account_id: int = Field(gt=0)
    category: str = Field(min_length=1,max_length=30)
    amount: Decimal = Field(gt=0,max_digits=14,decimal_places=2)
    party: str = Field(default='',max_length=200)
    purpose: str = Field(min_length=3,max_length=1000)
    reference: str = Field(default='',max_length=150)
