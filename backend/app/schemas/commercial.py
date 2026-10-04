import re
from datetime import date
from app.core.business_time import business_date
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictProfile(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, validate_default=True)


class ShiftRequirements(StrictProfile):
    day_shift_guards: int = Field(default=0, ge=0, le=1000)
    night_shift_guards: int = Field(default=0, ge=0, le=1000)
    general_shift_personnel: int = Field(default=0, ge=0, le=1000)
    supervisor_required: bool = False


class SiteProfile(StrictProfile):
    client_id: int = Field(ge=1)
    site_name: str = Field(min_length=2, max_length=255)
    address: str = Field(min_length=5, max_length=1500)
    city: str = Field(min_length=2, max_length=100)
    state: str = Field(min_length=2, max_length=100)
    postal_code: str = Field(pattern=r'^[1-9][0-9]{5}$')
    branch: str = Field(default='', max_length=100)
    contract_id: int | None = Field(default=None, ge=1)
    contact_person: str = Field(default='', max_length=150)
    contact_phone: str = ''
    latitude: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    longitude: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    geofence_radius_meters: int = Field(default=100, ge=10, le=1000)
    shift_requirements: ShiftRequirements = Field(default_factory=ShiftRequirements)
    field_officer_ids: list[int] = Field(default_factory=list, max_length=20)
    is_active: bool = True
    notes: str = Field(default='', max_length=2000)

    @field_validator('contact_phone')
    @classmethod
    def mobile(cls, value):
        value = re.sub(r'[ ()-]', '', value)
        if value.startswith('+91'): value = value[3:]
        if value and not re.fullmatch(r'[6-9][0-9]{9}', value):
            raise ValueError('Enter a valid 10-digit Indian mobile number.')
        return value

    @model_validator(mode='after')
    def coherent(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError('Enter both GPS coordinates together.')
        if len(set(self.field_officer_ids)) != len(self.field_officer_ids) or any(x < 1 for x in self.field_officer_ids):
            raise ValueError('Choose unique valid staff coordinators.')
        return self


class SiteUpdate(StrictProfile):
    version: int = Field(ge=1)
    profile: SiteProfile


class ContractProfile(StrictProfile):
    client_id: int = Field(ge=1)
    contract_number: str = Field(min_length=2, max_length=100)
    contract_start_date: date
    contract_end_date: date
    billing_cycle: Literal['MONTHLY','FORTNIGHTLY','WEEKLY'] = 'MONTHLY'
    credit_terms_days: int = Field(default=30, ge=0, le=365)
    wage_indexation_percent: Decimal = Field(default=0, ge=0, le=100, decimal_places=3)
    status: Literal['DRAFT','ACTIVE','EXPIRED','RENEWED','TERMINATED'] = 'DRAFT'
    renewal_notes: str = Field(default='', max_length=3000)
    service_verticals: list[Literal['SECURITY','HOUSEKEEPING','HEALTHCARE']] = Field(default_factory=list, max_length=3)
    scope_of_work: str = Field(default='', max_length=5000)
    signatory_name: str = Field(default='', max_length=150)
    signatory_designation: str = Field(default='', max_length=150)
    signed_date: date | None = None

    @field_validator('contract_number')
    @classmethod
    def reference(cls, value): return value.upper()

    @field_validator('signed_date', mode='before')
    @classmethod
    def optional_date(cls, value): return None if value == '' else value

    @model_validator(mode='after')
    def coherent(self):
        if self.contract_end_date < self.contract_start_date:
            raise ValueError('Contract end date must follow its start date.')
        if self.signed_date and self.signed_date > self.contract_end_date:
            raise ValueError('Signing date cannot follow contract expiry.')
        if len(set(self.service_verticals)) != len(self.service_verticals):
            raise ValueError('Choose each service once.')
        if self.status in {'ACTIVE','RENEWED'} and not self.service_verticals:
            raise ValueError('Select at least one service for an active contract.')
        return self


class ContractUpdate(StrictProfile):
    version: int = Field(ge=1)
    profile: ContractProfile


class RateProfile(StrictProfile):
    contract_id: int = Field(ge=1)
    vertical: Literal['SECURITY','HOUSEKEEPING','HEALTHCARE']
    category: str = Field(min_length=2, max_length=100)
    rate_basis: Literal['DAILY','HOURLY','MONTHLY'] = 'DAILY'
    daily_rate: Decimal = Field(default=0, ge=0, le=9999999999, decimal_places=2)
    hourly_rate: Decimal = Field(default=0, ge=0, le=9999999999, decimal_places=2)
    monthly_rate: Decimal = Field(default=0, ge=0, le=9999999999, decimal_places=2)
    duty_hours: Decimal = Field(default=8, ge=1, le=24, decimal_places=2)
    billable_days: int = Field(default=26, ge=1, le=31)
    wage_indexation_percent: Decimal = Field(default=0, ge=0, le=100, decimal_places=3)
    effective_from: date = Field(default_factory=business_date)
    effective_to: date | None = None
    is_active: bool = True
    notes: str = Field(default='', max_length=2000)

    @field_validator('category')
    @classmethod
    def category_code(cls, value):
        value = re.sub(r'\s+', '_', value.upper())
        if not re.fullmatch(r'[A-Z0-9][A-Z0-9_-]{1,99}', value):
            raise ValueError('Use letters, numbers, spaces, underscores or hyphens for category.')
        return value

    @field_validator('effective_to', mode='before')
    @classmethod
    def optional_date(cls, value): return None if value == '' else value

    @model_validator(mode='after')
    def coherent(self):
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError('Rate end date must follow its start date.')
        amount = {'DAILY':self.daily_rate,'HOURLY':self.hourly_rate,'MONTHLY':self.monthly_rate}[self.rate_basis]
        if amount <= 0: raise ValueError('Enter a positive amount for the selected rate basis.')
        def money(value): return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if self.rate_basis == 'MONTHLY':
            self.daily_rate = money(self.monthly_rate / self.billable_days)
            self.hourly_rate = money(self.daily_rate / self.duty_hours)
        elif self.rate_basis == 'HOURLY':
            self.daily_rate = money(self.hourly_rate * self.duty_hours)
        if self.daily_rate > Decimal('9999999999.99') or self.hourly_rate > Decimal('9999999999.99'):
            raise ValueError('Derived rate exceeds the supported amount.')
        return self


class RateUpdate(StrictProfile):
    version: int = Field(ge=1)
    profile: RateProfile
