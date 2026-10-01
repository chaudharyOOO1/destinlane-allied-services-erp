from datetime import timedelta
from typing import Any
import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.api.permissions import effective_permissions
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, get_password_hash, verify_password
from app.core.supabase_auth import verify_supabase_password
from app.crud.crud_user import user as crud_user
from app.models.user import User
from app.schemas.token import Token, LoginRequest
from app.schemas.user import UserResponse

router = APIRouter()

def _authenticate(db: Session, login_id: str, password: str) -> User | None:
    identifier = login_id.strip()
    user = crud_user.get_by_login_id(db, login_id=identifier)
    if not user:
        user = crud_user.get_by_email(db, email=identifier)
    if not user:
        user = db.query(User).filter(User.phone_number == identifier).first()
    if not user:
        return None

    # Supabase Auth is the primary password authority when configured.
    auth_result = verify_supabase_password(identifier=user.email, password=password)
    if auth_result:
        return user

    # Local hash remains as a migration fallback.
    if verify_password(password, user.hashed_password):
        return user
    return None


@router.post("/login", response_model=Token)
def login_json(login_data: LoginRequest, db: Session = Depends(get_db)) -> Any:
    user = _authenticate(db, login_id=login_data.login_id, password=login_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Login ID or password.")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user account.")
    return {
        "access_token": create_access_token(user.id, expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES), role=user.role),
        "token_type": "bearer",
        "user": user,
    }

@router.post("/login/access-token", response_model=Token)
def login_access_token(db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()) -> Any:
    user = _authenticate(db, login_id=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect email or password.")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user account.")
    return {
        "access_token": create_access_token(user.id, expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES), role=user.role),
        "token_type": "bearer",
        "user": user,
    }

class AdminSetupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=72)
    setup_token: str = Field(min_length=16, max_length=256)

@router.post("/setup-admin")
def setup_admin_password(setup_data: AdminSetupRequest, db: Session = Depends(get_db)) -> dict:
    configured_token = settings.ADMIN_SETUP_TOKEN
    if not configured_token or not secrets.compare_digest(setup_data.setup_token, configured_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid administrator setup token.")
    admin = db.query(User).filter(User.email == setup_data.email).first()
    if not admin or not admin.is_active or not admin.is_superuser:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Administrator account not found.")
    if getattr(admin, "password_initialized_at", None) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Administrator password has already been initialized.")
    from sqlalchemy import func
    admin.hashed_password = get_password_hash(setup_data.password)
    admin.password_initialized_at = db.query(func.now()).scalar()
    db.add(admin)
    db.commit()
    return {"status": "success", "message": "Administrator password initialized. You can now sign in normally."}

class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=12, max_length=72)

@router.post("/change-password")
def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> dict:
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect.")
    if data.current_password == data.new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password must be different.")
    current_user.hashed_password = get_password_hash(data.new_password)
    from sqlalchemy import func
    current_user.password_initialized_at = db.query(func.now()).scalar()
    db.add(current_user)
    db.commit()
    return {"status": "success", "message": "Password changed successfully."}

@router.get("/me", response_model=UserResponse)
def read_current_user(current_user: User = Depends(get_current_active_user)) -> Any:
    return current_user

@router.get("/permissions")
def read_permissions(current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)) -> dict:
    return {"permissions": effective_permissions(db, current_user)}
