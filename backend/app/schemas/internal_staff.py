import re
from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StaffProfile(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=2, max_length=150)
    phone: str
    email: str = Field(default='', max_length=255)
    department: str = Field(default='', max_length=100)
    designation: str = Field(default='', max_length=100)
    region: Literal['','ALL_REGIONS','UTTARAKHAND','UTTAR_PRADESH','DELHI_NCR'] = ''
    portal_role: Literal['OWNER','SUPER_ADMIN','ADMIN','HR','OPERATIONS','ACCOUNTS','SUPERVISOR','STAFF'] = 'STAFF'
    management_level: Literal['UPPER_MANAGEMENT','MANAGEMENT','BRANCH_HEAD','FIELD_OFFICER','SUPPORT'] = 'SUPPORT'
    branch: str = Field(default='', max_length=100)
    reporting_to: str = Field(default='', max_length=150)
    employment_type: Literal['FULL_TIME','PART_TIME','CONTRACT','INTERN'] = 'FULL_TIME'
    joining_date: date | None = None
    dob: date | None = None
    gender: Literal['','MALE','FEMALE','OTHER'] = ''
    father_spouse_name: str = Field(default='', max_length=150)
    address: str = Field(default='', max_length=1000)
    city: str = Field(default='', max_length=100)
    state: str = Field(default='', max_length=100)
    pincode: str = ''
    emergency_name: str = Field(default='', max_length=150)
    emergency_phone: str = ''
    emergency_relation: str = Field(default='', max_length=80)
    pan: str = ''
    bank_account: str = ''
    bank_name: str = Field(default='', max_length=150)
    bank_ifsc: str = ''
    uan: str = ''
    esic_number: str = ''
    nominee_name: str = Field(default='', max_length=150)
    nominee_relation: str = Field(default='', max_length=80)
    notes: str = Field(default='', max_length=2000)

    @field_validator('joining_date','dob', mode='before')
    @classmethod
    def blank_date(cls, value):
        return None if value == '' else value

    @field_validator('phone','emergency_phone')
    @classmethod
    def phone_format(cls, value, info):
        value = re.sub(r'[\s()-]', '', value)
        if value.startswith('+91'): value = value[3:]
        if not value and info.field_name == 'emergency_phone': return ''
        if not re.fullmatch(r'[6-9][0-9]{9}', value): raise ValueError('Enter a valid 10-digit Indian mobile number.')
        return value

    @field_validator('pan','bank_ifsc')
    @classmethod
    def identifiers(cls, value, info):
        value = value.upper()
        pattern = r'[A-Z]{5}[0-9]{4}[A-Z]' if info.field_name == 'pan' else r'[A-Z]{4}0[A-Z0-9]{6}'
        if value and not re.fullmatch(pattern, value): raise ValueError('Invalid PAN or IFSC format.')
        return value

    @field_validator('pincode','bank_account','uan','esic_number')
    @classmethod
    def numbers(cls, value, info):
        patterns = {'pincode':r'[1-9][0-9]{5}', 'bank_account':r'[0-9]{8,20}', 'uan':r'[0-9]{12}', 'esic_number':r'[0-9]{10}'}
        if value and not re.fullmatch(patterns[info.field_name], value): raise ValueError('Invalid ' + info.field_name.replace('_',' ') + '.')
        return value

    @field_validator('email')
    @classmethod
    def email_format(cls, value):
        if value and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value): raise ValueError('Invalid email address.')
        return value.lower()

    @model_validator(mode='after')
    def dates_and_bank(self):
        if self.dob and (self.dob >= date.today() or (self.joining_date and self.dob >= self.joining_date)):
            raise ValueError('Date of birth must be before today and joining date.')
        if any([self.bank_account,self.bank_name,self.bank_ifsc]) and not all([self.bank_account,self.bank_name,self.bank_ifsc]):
            raise ValueError('Bank account, bank name and IFSC must be entered together.')
        return self

    def ready_for_submission(self):
        if not self.department or not self.designation or not self.joining_date:
            raise ValueError('Department, designation and joining date are required before submission.')
        if self.joining_date > date.today():
            raise ValueError('Joining date cannot be in the future when submitting staff.')


class StaffCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    profile: StaffProfile
    submit: bool = False


class StaffUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(ge=1)
    profile: StaffProfile


class StaffAction(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    version: int = Field(ge=1)
    reason: str = Field(default='', max_length=1000)
    decision: Literal['APPROVE','RETURN'] = 'APPROVE'
    status: Literal['ACTIVE','INACTIVE','TERMINATED'] = 'INACTIVE'


class ApprovalSettingUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(ge=1)
    approver_id: int | None = Field(default=None, ge=1)
