import re
from datetime import datetime, date
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator, model_validator

COMPANY_NAME = 'DestinLane Allied Services Pvt Ltd'


def current_financial_year():
    today = datetime.now(ZoneInfo('Asia/Kolkata'))
    return today.year if today.month >= 4 else today.year - 1


class BranchProfile(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    code: str = Field(min_length=2, max_length=20, pattern=r'^[A-Z0-9][A-Z0-9_-]+$')
    name: str = Field(min_length=2, max_length=120)
    address: str = Field(default='', max_length=1000)
    city: str = Field(default='', max_length=100)
    state: str = Field(default='', max_length=100)
    pincode: str = Field(default='', max_length=6)
    is_active: bool = True

    @field_validator('code', mode='before')
    @classmethod
    def normalize_code(cls, value):
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator('pincode')
    @classmethod
    def valid_pincode(cls, value):
        if value and not re.fullmatch(r'[1-9]\d{5}', value):
            raise ValueError('Enter a valid six-digit PIN code.')
        return value


class CompanyProfile(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    legal_name: str = Field(default=COMPANY_NAME, min_length=3, max_length=200)
    display_name: str = Field(default='DestinLane Allied Services', min_length=2, max_length=120)
    address: str = Field(default='', max_length=1000)
    city: str = Field(default='', max_length=100)
    state: str = Field(default='', max_length=100)
    pincode: str = Field(default='', max_length=6)
    contact_email: str = Field(default='', max_length=254)
    contact_phone: str = Field(default='', max_length=25)
    website: str = Field(default='', max_length=500)
    gstin: str = Field(default='', max_length=15)
    pan: str = Field(default='', max_length=10)
    cin: str = Field(default='', max_length=21)
    tan: str = Field(default='', max_length=10)
    registration_date: date | None = None
    gst_registration_date: date | None = None
    registration_authority: str = Field(default='', max_length=200)
    company_type: str = Field(default='Private Limited Company', max_length=100)
    business_description: str = Field(default='', max_length=3000)
    registered_office: str = Field(default='', max_length=1000)
    pf_registration_number: str = Field(default='', max_length=100)
    esic_registration_number: str = Field(default='', max_length=100)
    udyam_registration_number: str = Field(default='', max_length=100)
    labour_registration_number: str = Field(default='', max_length=100)
    psara_registration_number: str = Field(default='', max_length=100)
    financial_year_start_year: int = Field(default_factory=current_financial_year, ge=2000, le=2100)
    financial_year_start_month: int = Field(default=4, ge=1, le=12)
    currency: str = Field(default='INR', pattern=r'^INR$')
    branches: list[BranchProfile] = Field(default_factory=list, max_length=100)

    @field_validator('gstin', 'pan', 'cin', 'tan', mode='before')
    @classmethod
    def normalize_registration(cls, value):
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator('gstin')
    @classmethod
    def valid_gstin(cls, value):
        if value and not re.fullmatch(r'[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]', value):
            raise ValueError('Enter a valid 15-character GSTIN format.')
        return value

    @field_validator('pan')
    @classmethod
    def valid_pan(cls, value):
        if value and not re.fullmatch(r'[A-Z]{5}[0-9]{4}[A-Z]', value):
            raise ValueError('Enter a valid 10-character PAN format.')
        return value

    @field_validator('cin')
    @classmethod
    def valid_cin(cls, value):
        if value and not re.fullmatch(r'[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}', value):
            raise ValueError('Enter a valid 21-character CIN format.')
        return value

    @field_validator('tan')
    @classmethod
    def valid_tan(cls, value):
        if value and not re.fullmatch(r'[A-Z]{4}[0-9]{5}[A-Z]', value):
            raise ValueError('Enter a valid 10-character TAN format.')
        return value

    @field_validator('registration_date', 'gst_registration_date')
    @classmethod
    def valid_registration_date(cls, value):
        if value and value > datetime.now(ZoneInfo('Asia/Kolkata')).date():
            raise ValueError('Registration dates cannot be in the future.')
        return value

    @field_validator('pincode')
    @classmethod
    def valid_pincode(cls, value):
        return BranchProfile.valid_pincode(value)

    @field_validator('contact_email')
    @classmethod
    def valid_email(cls, value):
        if value:
            from pydantic import TypeAdapter
            return str(TypeAdapter(EmailStr).validate_python(value))
        return value

    @field_validator('contact_phone')
    @classmethod
    def valid_phone(cls, value):
        if value and (not re.fullmatch(r'\+?[0-9 ()-]+', value) or not 7 <= len(re.sub(r'\D', '', value)) <= 15):
            raise ValueError('Enter a valid contact phone number.')
        return value

    @field_validator('website')
    @classmethod
    def valid_website(cls, value):
        if value:
            parsed = urlsplit(value)
            if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError('Enter an http or https website URL without credentials.')
        return value

    @model_validator(mode='after')
    def consistent_profile(self):
        codes = [branch.code for branch in self.branches]
        if len(codes) != len(set(codes)):
            raise ValueError('Branch codes must be unique.')
        if self.gstin and self.pan and self.gstin[2:12] != self.pan:
            raise ValueError('GSTIN and PAN must refer to the same company.')
        return self


class CompanyUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(ge=0)
    profile: CompanyProfile
    submit: bool = False
