from datetime import timedelta
from typing import Any
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.api.permissions import effective_permissions
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, get_password_hash, verify_password
from app.core.supabase_auth import authenticate_supabase_user, provision_supabase_password_user, verify_supabase_password
from app.crud.crud_user import user as crud_user
from app.models.user import User
from app.schemas.token import Token, LoginRequest
from app.schemas.user import UserResponse

router = APIRouter()


def _authenticate(db: Session, login_id: str, password: str) -> User | None:
    identifier = login_id.strip()

    # Production authentication is anchored to Supabase Auth + public.users.
    # This avoids making login dependent on the serverless function's SQLAlchemy
    # connection pool, which can fail independently of Supabase.
    supabase_user = authenticate_supabase_user(identifier, password)
    if supabase_user:
        return supabase_user

    # Keep the existing database path as a compatibility fallback for local
    # development and environments where Supabase credentials are not configured.
    try:
        user = crud_user.get_by_login_id(db, login_id=identifier)
        if not user:
            user = crud_user.get_by_email(db, email=identifier)
        if not user:
            user = db.query(User).filter(User.phone_number == identifier).first()
        if not user or not user.is_active:
            return None

        auth_result = verify_supabase_password(identifier=user.email, password=password)
        if auth_result:
            return user

        if settings.ALLOW_LOCAL_PASSWORD_FALLBACK and verify_password(password, user.hashed_password):
            return user
    except Exception:
        return None

    return None


def _token_response(user: User) -> dict:
    return {
        "access_token": create_access_token(
            user.id,
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
            role=user.role,
        ),
        "token_type": "bearer",
        "user": user,
    }


@router.post("/login", response_model=Token)
def login_json(login_data: LoginRequest, db: Session = Depends(get_db)) -> Any:
    user = _authenticate(db, login_id=login_data.login_id, password=login_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Login ID or password.")
    return _token_response(user)


@router.post("/login/access-token", response_model=Token)
def login_access_token(
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Any:
    user = _authenticate(db, login_id=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Login ID or password.")
    return _token_response(user)


def _validate_password_bytes(value: str) -> str:
    if len(value.encode("utf-8")) > 72:
        raise ValueError("Password must be at most 72 UTF-8 bytes.")
    return value


class AdminSetupRequest(BaseModel):
    email: EmailStr
    login_id: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=12, max_length=72)
    setup_token: str = Field(min_length=16, max_length=256)
    _password_bytes = field_validator("password")(_validate_password_bytes)


@router.post("/setup-admin")
def setup_admin_password(setup_data: AdminSetupRequest, db: Session = Depends(get_db)) -> dict:
    configured_token = settings.ADMIN_SETUP_TOKEN
    if not configured_token or not secrets.compare_digest(setup_data.setup_token, configured_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid administrator setup token.")

    admin = db.query(User).filter(User.email == setup_data.email).first()
    if not admin or not admin.is_active or not admin.is_superuser:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Administrator account not found.")

    login_id = setup_data.login_id.strip()
    existing = crud_user.get_by_login_id(db, login_id=login_id)
    if existing and existing.id != admin.id:
        raise HTTPException(status_code=409, detail="That Login ID is already assigned to another account.")

    auth_user = provision_supabase_password_user(email=admin.email, password=setup_data.password)
    if not auth_user:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Supabase Auth administrator provisioning failed.",
        )

    admin.login_id = login_id
    admin.hashed_password = get_password_hash(setup_data.password)
    admin.password_initialized_at = db.query(func.now()).scalar()
    db.add(admin)
    db.commit()
    return {"status": "success", "message": "Administrator Login ID and password are now synchronized with Supabase Auth."}


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=12, max_length=72)
    _password_bytes = field_validator("new_password")(_validate_password_bytes)


@router.post("/change-password")
def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> dict:
    current_ok = verify_supabase_password(identifier=current_user.email, password=data.current_password)
    if not current_ok and settings.ALLOW_LOCAL_PASSWORD_FALLBACK:
        current_ok = verify_password(data.current_password, current_user.hashed_password)
    if not current_ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect.")
    if data.current_password == data.new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password must be different.")

    auth_user = provision_supabase_password_user(email=current_user.email, password=data.new_password)
    if not auth_user:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Supabase Auth password update failed.")

    current_user.hashed_password = get_password_hash(data.new_password)
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
