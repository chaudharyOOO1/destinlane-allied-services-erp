from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, ConfigDict, Field
from app.models.enums import UserRole


class UserBase(BaseModel):
    email: EmailStr
    login_id: Optional[str] = Field(default=None, min_length=3, max_length=255)
    full_name: str
    phone_number: Optional[str] = None
    role: UserRole = UserRole.STAFF
    is_active: bool = True


class UserCreate(UserBase):
    password: str = Field(min_length=12, max_length=72)


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    login_id: Optional[str] = Field(default=None, min_length=3, max_length=255)
    password: Optional[str] = Field(default=None, min_length=12, max_length=72)
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    id: int
    is_superuser: bool
    created_at: datetime
    updated_at: datetime
    password_initialized_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)
