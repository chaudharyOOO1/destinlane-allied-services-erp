import re
from datetime import date
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator


class ClientProfile(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    company_name: str = Field(min_length=2,max_length=255)
    gstin: str
    pan: str = ''
    cin: str = ''
    registration_no: str = Field(default='',max_length=100)
    billing_address: str = Field(min_length=5,max_length=1500)
    city: str = Field(default='',max_length=100)
    state: str = Field(default='',max_length=100)
    pincode: str = ''
    branch: str = Field(default='',max_length=100)
    branch_region: Literal['UTTARAKHAND','UTTAR_PRADESH','DELHI_NCR']
    billing_cycle: Literal['MONTHLY','FORTNIGHTLY','WEEKLY'] = 'MONTHLY'
    contact_person: str = Field(min_length=2,max_length=150)
    contact_email: str = Field(min_length=5,max_length=255)
    contact_phone: str
    accounts_contact_name: str = Field(default='',max_length=150)
    accounts_email: str = Field(default='',max_length=255)
    accounts_phone: str = ''
    credit_terms_days: int = Field(default=30,ge=0,le=365)
    service_verticals: list[Literal['SECURITY','HOUSEKEEPING','HEALTHCARE']] = Field(default_factory=list,max_length=3)
    contract_start_date: date | None = None
    contract_end_date: date | None = None
    field_officer_ids: list[int] = Field(default_factory=list,max_length=20)
    portal_user_id: int | None = Field(default=None,ge=1)
    is_active: bool = True
    notes: str = Field(default='',max_length=2000)

    @field_validator('contract_start_date','contract_end_date',mode='before')
    @classmethod
    def optional_date(cls,value): return None if value=='' else value

    @field_validator('gstin','pan','cin')
    @classmethod
    def identifiers(cls,value,info):
        value=value.upper()
        patterns={'gstin':r'[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]','pan':r'[A-Z]{5}[0-9]{4}[A-Z]','cin':r'[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}'}
        if (value or info.field_name=='gstin') and not re.fullmatch(patterns[info.field_name],value):raise ValueError('Invalid '+info.field_name.upper()+' format.')
        return value

    @field_validator('contact_phone','accounts_phone')
    @classmethod
    def phone(cls,value,info):
        value=re.sub(r'[ ()-]','',value)
        if value.startswith('+91'):value=value[3:]
        if not value and info.field_name=='accounts_phone': return ''
        if not re.fullmatch(r'[6-9][0-9]{9}',value): raise ValueError('Enter a valid 10-digit Indian mobile number.')
        return value

    @field_validator('contact_email','accounts_email')
    @classmethod
    def email(cls,value,info):
        if not value and info.field_name=='accounts_email':return ''
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value):raise ValueError('Invalid contact email address.')
        return value.lower()

    @field_validator('pincode')
    @classmethod
    def pin(cls,value):
        if value and not re.fullmatch(r'[1-9][0-9]{5}',value):raise ValueError('Invalid PIN code.')
        return value

    @model_validator(mode='after')
    def coherence(self):
        if self.pan and self.pan!=self.gstin[2:12]:raise ValueError('PAN must match the PAN in GSTIN.')
        if self.contract_start_date and self.contract_end_date and self.contract_end_date<self.contract_start_date:raise ValueError('Contract end date must follow start date.')
        if bool(self.contract_start_date)!=bool(self.contract_end_date):raise ValueError('Enter both contract dates together.')
        if len(set(self.field_officer_ids))!=len(self.field_officer_ids) or any(x<1 for x in self.field_officer_ids):raise ValueError('Choose unique valid field officers.')
        if len(set(self.service_verticals))!=len(self.service_verticals):raise ValueError('Choose each service vertical once.')
        return self


class ClientUpdate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    version: int = Field(ge=1)
    profile: ClientProfile
