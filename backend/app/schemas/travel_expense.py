from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class TravelItem(Input):
    date: date
    category: Literal['TRANSPORT', 'LODGING', 'MEALS', 'OTHER']
    description: str = Field(min_length=2, max_length=300)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    bill_number: str = Field(default='', max_length=100)


class TravelClaimInput(Input):
    purpose: str = Field(min_length=3, max_length=500)
    origin: str = Field(min_length=2, max_length=150)
    destination: str = Field(min_length=2, max_length=150)
    start_date: date
    end_date: date
    branch: str = Field(default='', max_length=100)
    items: list[TravelItem] = Field(min_length=1, max_length=100)
    missing_receipt_reason: str = Field(default='', max_length=1000)

    @model_validator(mode='after')
    def validate_trip(self):
        if self.end_date < self.start_date:
            raise ValueError('Travel end date cannot precede the start date.')
        if any(not self.start_date <= item.date <= self.end_date for item in self.items):
            raise ValueError('Every expense date must fall within the travel dates.')
        if sum((item.amount for item in self.items), Decimal('0')) > Decimal('9999999999.99'):
            raise ValueError('The claim total exceeds the supported limit.')
        return self


class VersionInput(Input):
    version: int = Field(ge=1)


class TravelClaimUpdate(TravelClaimInput, VersionInput):
    pass


class TravelDecision(VersionInput):
    decision: Literal['APPROVE', 'REJECT']
    remarks: str = Field(default='', max_length=1000)

    @model_validator(mode='after')
    def rejection_reason(self):
        if self.decision == 'REJECT' and not self.remarks:
            raise ValueError('Rejection remarks are required.')
        return self


class TravelPayment(VersionInput):
    payment_date: date
    payment_reference: str = Field(min_length=3, max_length=150)
