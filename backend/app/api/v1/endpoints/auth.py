from datetime import datetime, timezone, timedelta
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.api.deps import get_current_active_user
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, get_password_hash, verify_password
from app.core.supabase_auth import get_recovery_user, update_recovery_password, provision_supabase_password_user
from app.crud.crud_user import user as crud_user
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.token import LoginRequest, Token
from app.schemas.user import UserResponse

router = APIRouter()
logger = logging.getLogger(__name__)
_DUMMY_LOGIN_HASH = get_password_hash("unknown-account-constant-cost")


class EmailRecoveryRequest(BaseModel):
    access_token: str = Field(min_length=16, max_length=8192)
    new_password: str = Field(min_length=12, max_length=72)


@router.post('/reset-password')
def reset_password(payload: EmailRecoveryRequest, db: Session = Depends(get_db)):
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(status_code=503, detail='Email password recovery is not configured. Contact your administrator.')
    if len(payload.new_password.encode('utf-8')) > 72:
        raise HTTPException(status_code=400, detail='Password must be at most 72 UTF-8 bytes.')
    identity = get_recovery_user(payload.access_token)
    if not identity or not identity.get('email') or not identity.get('email_confirmed_at'):
        raise HTTPException(status_code=401, detail='This password reset link is invalid or has expired.')
    account = db.query(User).filter(func.lower(User.email) == str(identity['email']).lower(), User.is_active.is_(True)).first()
    if not account:
        raise HTTPException(status_code=403, detail='Password recovery is unavailable for this ERP account.')
    # Verify the token with Supabase, and bind it to an active ERP account before
    # changing either password. Never accept an account ID/email from the client.
    if not update_recovery_password(access_token=payload.access_token, password=payload.new_password):
        raise HTTPException(status_code=502, detail='Password recovery could not be completed. Please retry.')
    crud_user.update(db, db_obj=account, obj_in={
        'password': payload.new_password,
        'password_initialized_at': datetime.now(timezone.utc),
        'must_change_password': False,
        'session_version': account.session_version + 1,
    })
    return {'success': True, 'message': 'Your ERP password has been updated. You can now sign in.'}


class AdminSetupRequest(BaseModel):
    setup_token: str = Field(min_length=8)
    login_id: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=12, max_length=72)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=12, max_length=72)


@router.post('/login', response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    identifier = payload.login_id.strip()
    # Lock one account across serverless instances. Attempts use the same state
    # whether the user enters a login ID, email or registered phone number.
    account = db.query(User).filter(or_(
        func.upper(User.login_id) == identifier.upper(),
        func.lower(User.email) == identifier.lower(),
        User.phone_number == identifier,
    )).with_for_update().first()
    now = datetime.now(timezone.utc)
    locked = account.login_locked_until if account else None
    if locked and locked.tzinfo is None: locked = locked.replace(tzinfo=timezone.utc)
    if locked and locked > now:
        raise HTTPException(429, 'Too many sign-in attempts. Try again after 15 minutes.', headers={'Retry-After':'900'})
    if account:
        valid = crud_user.authenticate(db, login_id=account.login_id or account.email, password=payload.password) is not None
    else:
        verify_password(payload.password, _DUMMY_LOGIN_HASH)
        valid = False
    if not account or not valid or not account.is_active:
        if account:
            account.failed_login_attempts = (0 if locked and locked <= now else account.failed_login_attempts) + 1
            if account.failed_login_attempts >= 5: account.login_locked_until = now + timedelta(minutes=15)
            db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid Login ID or password', headers={'WWW-Authenticate': 'Bearer'})
    account.failed_login_attempts = 0
    account.login_locked_until = None
    db.commit()
    token = create_access_token(account.id, role=account.role, session_version=account.session_version)
    return {'access_token': token, 'token_type': 'bearer', 'user': account}


@router.get('/me', response_model=UserResponse)
def me(current_user: User = Depends(get_current_active_user)):
    return current_user


@router.post('/setup-admin', response_model=UserResponse)
def setup_admin(payload: AdminSetupRequest, db: Session = Depends(get_db)):
    if not settings.ADMIN_SETUP_TOKEN or payload.setup_token != settings.ADMIN_SETUP_TOKEN:
        raise HTTPException(status_code=403, detail='Administrator setup is not authorized.')

    existing_active_owner = db.query(User).filter(
        User.role.in_([UserRole.OWNER, UserRole.SUPER_ADMIN]),
        User.is_active.is_(True),
    ).first()
    if existing_active_owner:
        raise HTTPException(status_code=409, detail='Administrator setup has already been completed.')

    account = db.query(User).filter(User.id == 1).first()
    if account is None:
        account = db.query(User).filter(User.role == UserRole.OWNER).order_by(User.id.asc()).first()
    if account is None:
        raise HTTPException(status_code=404, detail='No administrator account seed exists.')

    if db.query(User).filter(User.login_id == payload.login_id, User.id != account.id).first():
        raise HTTPException(status_code=409, detail='Login ID is already in use.')

    updated = crud_user.update(db, db_obj=account, obj_in={
        'login_id': payload.login_id.strip().upper(),
        'password': payload.password,
        'is_active': True,
        'is_superuser': True,
        'password_initialized_at': datetime.now(timezone.utc),
        'must_change_password': False,
        'session_version': account.session_version + 1,
    })
    return updated


class AdminRecoveryRequest(BaseModel):
    recovery_token: str = Field(min_length=8)
    login_id: str = Field(min_length=3, max_length=50)
    new_password: str = Field(min_length=12, max_length=72)


@router.post('/admin-recover-password')
def admin_recover_password(payload: AdminRecoveryRequest, db: Session = Depends(get_db)):
    if not settings.ADMIN_SETUP_TOKEN or payload.recovery_token != settings.ADMIN_SETUP_TOKEN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Administrator recovery is not authorized.')
    if len(payload.new_password.encode('utf-8')) > 72:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Password must be at most 72 UTF-8 bytes.')
    account = db.query(User).filter(User.login_id == payload.login_id.strip().upper()).first()
    if not account or account.role not in [UserRole.OWNER, UserRole.SUPER_ADMIN] or not account.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Administrator account not found.')
    try:
        crud_user.update(db, db_obj=account, obj_in={
            'password': payload.new_password,
            'password_initialized_at': datetime.now(timezone.utc),
        'must_change_password': False,
        'session_version': account.session_version + 1,
        })
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        logger.exception('Administrator password recovery failed for login_id=%s', account.login_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='Administrator password reset could not be completed.') from None
    return {'success': True, 'message': 'Administrator password has been reset. You can now sign in.'}


@router.post('/change-password', response_model=UserResponse)
def change_password(payload: ChangePasswordRequest, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if not crud_user.authenticate(db, login_id=current_user.login_id or current_user.email, password=payload.current_password):
        raise HTTPException(status_code=400, detail='Current password is incorrect.')
    if payload.new_password == payload.current_password:
        raise HTTPException(400,'Choose a new password different from your current password.')
    if len(payload.new_password.encode('utf-8')) > 72:
        raise HTTPException(status_code=400, detail='Password must be at most 72 UTF-8 bytes.')
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        if not provision_supabase_password_user(email=current_user.email, password=payload.new_password):
            raise HTTPException(status_code=502, detail='Password synchronization failed. Please retry.')
    return crud_user.update(db, db_obj=current_user, obj_in={
        'password': payload.new_password,
        'password_initialized_at': datetime.now(timezone.utc),
        'must_change_password': False,
        'session_version': current_user.session_version + 1,
    })
