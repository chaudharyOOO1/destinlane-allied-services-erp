from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, ConfigDict, Field, field_validator
from app.models.enums import UserRole


def _validate_password_bytes(value: str) -> str:
    if len(value.encode("utf-8")) > 72:
        raise ValueError("Password must be at most 72 UTF-8 bytes.")
    return value


class UserBase(BaseModel):
    email: EmailStr
    login_id: Optional[str] = Field(default=None, min_length=3, max_length=255)
    full_name: str = Field(min_length=2,max_length=150)
    phone_number: Optional[str] = None
    role: UserRole = UserRole.STAFF
    is_active: bool = True

    @field_validator('email')
    @classmethod
    def normalize_email(cls,value): return value.lower()

    @field_validator('login_id')
    @classmethod
    def normalize_login(cls,value):
        import re
        if value is None: return None
        value=value.strip().upper()
        if not re.fullmatch(r'[A-Z0-9][A-Z0-9_-]{2,49}',value): raise ValueError('Login ID must contain 3–50 letters, numbers, underscores or hyphens.')
        return value

    @field_validator('full_name')
    @classmethod
    def normalize_name(cls,value):
        if not value: raise ValueError('Full name is required.')
        value=value.strip()
        if len(value)<2: raise ValueError('Full name is required.')
        return value

    @field_validator('phone_number')
    @classmethod
    def normalize_phone(cls,value):
        import re
        if not value:return None
        value=re.sub(r'[ ()-]','',value)
        if value.startswith('+91'):value=value[3:]
        if not re.fullmatch(r'[6-9][0-9]{9}',value):raise ValueError('Enter a valid 10-digit mobile number.')
        return value


class UserCreate(UserBase):
    password: str = Field(min_length=12, max_length=72)
    _password_bytes = field_validator("password")(_validate_password_bytes)


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    login_id: Optional[str] = Field(default=None, min_length=3, max_length=255)
    password: Optional[str] = Field(default=None, min_length=12, max_length=72)
    full_name: Optional[str] = Field(default=None,min_length=2,max_length=150)
    phone_number: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    _password_bytes = field_validator("password")(_validate_password_bytes)


    _login = field_validator('login_id')(UserBase.normalize_login.__func__)
    _name = field_validator('full_name')(UserBase.normalize_name.__func__)
    _phone = field_validator('phone_number')(UserBase.normalize_phone.__func__)


class UserResponse(BaseModel):
    email: str
    login_id: Optional[str] = None
    full_name: str
    phone_number: Optional[str] = None
    role: UserRole
    is_active: bool
    must_change_password: bool = False
    id: int
    is_superuser: bool
    created_at: datetime
    updated_at: datetime
    password_initialized_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)
