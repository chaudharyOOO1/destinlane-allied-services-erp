from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.crud.crud_user import user as crud_user
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.token import LoginRequest, Token
from app.schemas.user import UserResponse

router = APIRouter()


class AdminSetupRequest(BaseModel):
    setup_token: str = Field(min_length=8)
    login_id: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=12, max_length=72)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=12, max_length=72)


@router.post('/login', response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    account = crud_user.authenticate(db, login_id=payload.login_id, password=payload.password)
    if not account or not account.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid Login ID or password', headers={'WWW-Authenticate': 'Bearer'})
    token = create_access_token(account.id, role=account.role)
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
    account = db.query(User).filter(User.login_id == payload.login_id.strip().upper()).first()
    if not account or account.role not in [UserRole.OWNER, UserRole.SUPER_ADMIN] or not account.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Administrator account not found.')
    crud_user.update(db, db_obj=account, obj_in={
        'password': payload.new_password,
        'password_initialized_at': datetime.now(timezone.utc),
    })
    return {'success': True, 'message': 'Administrator password has been reset. You can now sign in.'}


@router.post('/change-password', response_model=UserResponse)
def change_password(payload: ChangePasswordRequest, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    if not crud_user.authenticate(db, login_id=current_user.login_id or current_user.email, password=payload.current_password):
        raise HTTPException(status_code=400, detail='Current password is incorrect.')
    return crud_user.update(db, db_obj=current_user, obj_in={
        'password': payload.new_password,
        'password_initialized_at': datetime.now(timezone.utc),
    })
