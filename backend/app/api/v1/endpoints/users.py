from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, require_admin
from app.api.permissions import all_permission_keys, effective_permissions, permission_supported, MODULE_ROLES
from app.core.database import get_db
from app.core.config import settings
from app.core.security import get_password_hash
from app.core.supabase_auth import provision_supabase_password_user
from app.crud.crud_user import user as crud_user
from app.models.enums import UserRole
from app.models.user import User
from app.models.internal_staff import InternalStaff
from app.models.account_audit import AccountAccessAudit
from app.schemas.user import UserCreate, UserUpdate, UserResponse, _validate_password_bytes

router = APIRouter()


def audit(db, actor, target, action, details):
    db.add(AccountAccessAudit(actor_id=actor.id,target_id=target.id,action=action,details=details))


def assert_unique(db, data, target_id=None):
    filters=[]
    if data.get('email'): filters.append(func.lower(User.email)==data['email'].lower())
    if data.get('login_id'): filters.append(func.upper(User.login_id)==data['login_id'].upper())
    if data.get('phone_number'): filters.append(User.phone_number.in_([data['phone_number'],'+91'+data['phone_number']]))
    for predicate in filters:
        query=db.query(User).filter(predicate)
        if target_id: query=query.filter(User.id!=target_id)
        if query.first(): raise HTTPException(409,'Email, Login ID or mobile number already belongs to another account.')


def assert_staff_login(db, login_id):
    if login_id and login_id.startswith(('DASS','S-DAS-')):
        record=db.query(InternalStaff).filter_by(staff_code=login_id).first()
        if not record or record.status!='ACTIVE': raise HTTPException(409,'Staff must be registered and active before creating their login.')
def assert_staff_account_manager(db, actor, target):
    if actor.role not in {UserRole.OWNER,UserRole.HR} and db.query(InternalStaff).filter_by(user_id=target.id).first():
        raise HTTPException(403,'Only the Owner or HR can manage staff ERP access.')


ADMIN_ROLES = {UserRole.OWNER, UserRole.SUPER_ADMIN, UserRole.ADMIN}


def _role_value(role) -> str:
    return getattr(role, "value", str(role))


def _assert_manage_target(current_user: User, target: User | None = None, new_role: UserRole | None = None) -> None:
    actor = _role_value(current_user.role)
    target_role = _role_value(target.role) if target else None
    next_role = _role_value(new_role) if new_role else target_role

    if target and target.id == current_user.id:
        if new_role and next_role != actor:
            raise HTTPException(403, "You cannot change your own administrator role.")
        return

    if actor == "OWNER":
        return
    if actor not in {"OWNER", "SUPER_ADMIN", "ADMIN"} and (target_role in ADMIN_ROLES or next_role in ADMIN_ROLES):
        raise HTTPException(403, "Only the Owner can manage administrator accounts from Staff Master.")
    if target_role == "OWNER" or next_role == "OWNER":
        raise HTTPException(403, "Only the Owner can manage the Owner account.")
    if actor == "SUPER_ADMIN" and (target_role in {"SUPER_ADMIN", "ADMIN"} or next_role in {"SUPER_ADMIN", "ADMIN"}):
        raise HTTPException(403, "Super Admin cannot manage another administrator account.")
    if actor == "ADMIN" and (target_role in ADMIN_ROLES or next_role in ADMIN_ROLES):
        raise HTTPException(403, "Administrator cannot manage another administrator account.")


@router.get("/", response_model=List[UserResponse])
def read_users(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    role: Optional[UserRole] = None,
    current_user: User = Depends(require_admin),
) -> List[UserResponse]:
    query = db.query(crud_user.model)
    if role:
        query = query.filter(crud_user.model.role == role)
    return query.offset(skip).limit(limit).all()


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    *,
    db: Session = Depends(get_db),
    user_in: UserCreate,
    current_user: User = Depends(require_admin),
) -> UserResponse:
    try:
        db_user = prepare_user(db, user_in, current_user)
        db.commit(); db.refresh(db_user)
        return db_user
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Unable to create the account. Check for duplicate account details.') from None


def prepare_user(db, user_in, current_user):
    """Create and audit an account within the caller's database transaction."""
    if user_in.login_id and user_in.login_id.startswith(('DASS','S-DAS-')) and current_user.role not in {UserRole.OWNER,UserRole.HR}:
        raise HTTPException(403,'Only the Owner or HR can create staff logins.')
    assert_staff_login(db,user_in.login_id)
    if user_in.role in ADMIN_ROLES and current_user.role != UserRole.OWNER:
        raise HTTPException(403,'Only the Owner can create administrator accounts.')
    assert_unique(db,user_in.model_dump())
    auth_user = provision_supabase_password_user(email=user_in.email, password=user_in.password)
    if not auth_user and not (settings.ALLOW_LOCAL_PASSWORD_FALLBACK and not settings.SUPABASE_URL):
        raise HTTPException(502, "Supabase Auth account provisioning failed.")
    data=user_in.model_dump(exclude={'password'})
    db_user=User(**data,hashed_password=get_password_hash(user_in.password),must_change_password=True)
    db.add(db_user);db.flush()
    if user_in.login_id and user_in.login_id.startswith(('DASS','S-DAS-')):
        staff=db.query(InternalStaff).filter_by(staff_code=user_in.login_id).with_for_update().one()
        if staff.user_id is not None:
            raise HTTPException(409,'This staff record already has an ERP account.')
        staff.user_id=db_user.id
    audit(db,current_user,db_user,'CREATE',{'login_id':db_user.login_id,'role':db_user.role.value,'is_active':db_user.is_active})
    return db_user


@router.get("/{user_id}", response_model=UserResponse)
def read_user(
    *,
    db: Session = Depends(get_db),
    user_id: int,
    current_user: User = Depends(get_current_active_user),
) -> UserResponse:
    if not (current_user.role in ADMIN_ROLES) and current_user.id != user_id:
        raise HTTPException(403, "Access forbidden.")
    db_user = crud_user.get(db, id=user_id)
    if not db_user:
        raise HTTPException(404, "User not found.")
    return db_user


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    *,
    db: Session = Depends(get_db),
    user_id: int,
    user_in: UserUpdate,
    current_user: User = Depends(require_admin),
) -> UserResponse:
    db_user = crud_user.get(db, id=user_id)
    if not db_user:
        raise HTTPException(404, "User not found.")
    assert_staff_account_manager(db,current_user,db_user)
    _assert_manage_target(current_user, db_user, user_in.role)

    update_dict = user_in.model_dump(exclude_unset=True)
    if "is_active" in update_dict and update_dict["is_active"] is False and db_user.id == current_user.id:
        raise HTTPException(400, "You cannot disable your own account.")
    if "email" in update_dict and update_dict["email"] != db_user.email:
        raise HTTPException(400, "Email changes are disabled because Supabase Auth uses the account email as its identity.")
    if "login_id" in update_dict and update_dict["login_id"]:
        existing = crud_user.get_by_login_id(db, login_id=update_dict["login_id"])
        if existing and existing.id != db_user.id:
            raise HTTPException(400, "That Login ID is already assigned to another account.")
    if any(update_dict.get(k) is None for k in ('role','full_name','is_active') if k in update_dict):
        raise HTTPException(422,'Role, name and account status cannot be cleared.')
    if 'login_id' in update_dict and update_dict['login_id'] != db_user.login_id:
        if db.query(InternalStaff).filter_by(user_id=db_user.id).first():
            raise HTTPException(409,'A staff account uses its permanent staff ID as Login ID.')
        assert_staff_login(db,update_dict['login_id'])
    if update_dict.get('is_active') is True:
        staff = db.query(InternalStaff).filter_by(user_id=db_user.id).first()
        if staff and staff.status != 'ACTIVE':
            raise HTTPException(409,'Reactivate the staff record before enabling its ERP account.')
    assert_unique(db,update_dict,db_user.id)
    if "password" in update_dict:
        auth_user = provision_supabase_password_user(email=db_user.email, password=update_dict["password"])
        if not auth_user:
            raise HTTPException(502, "Supabase Auth password synchronization failed.")

    if update_dict.get('is_active') is False:
        db_user.session_version+=1
    changes={key:value.value if isinstance(value,UserRole) else value for key,value in update_dict.items() if key!='password'}
    if 'password' in update_dict:
        db_user.hashed_password=get_password_hash(update_dict.pop('password'))
        db_user.must_change_password=True
        db_user.password_initialized_at=None
        db_user.session_version+=1
        changes['temporary_password_reset']=True
    for key,value in update_dict.items(): setattr(db_user,key,value)
    audit(db,current_user,db_user,'UPDATE',changes)
    db.commit();db.refresh(db_user)
    return db_user


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=12, max_length=72)
    _password_bytes = field_validator("new_password")(_validate_password_bytes)


@router.post("/{user_id}/reset-password")
def reset_password(
    *,
    db: Session = Depends(get_db),
    user_id: int,
    data: ResetPasswordRequest,
    current_user: User = Depends(require_admin),
) -> dict:
    db_user = crud_user.get(db, id=user_id)
    if not db_user:
        raise HTTPException(404, "User not found.")
    assert_staff_account_manager(db,current_user,db_user)
    _assert_manage_target(current_user, db_user)

    auth_user = provision_supabase_password_user(email=db_user.email, password=data.new_password)
    if not auth_user:
        raise HTTPException(502, "Supabase Auth password synchronization failed.")

    db_user.hashed_password = get_password_hash(data.new_password)
    db_user.password_initialized_at = None
    db_user.must_change_password = True
    db_user.session_version += 1
    audit(db,current_user,db_user,'PASSWORD_RESET',{})
    db.add(db_user)
    db.commit()
    return {"status": "success", "message": "Password reset. The user should change it after signing in."}


class PermissionUpdate(BaseModel):
    permission_key: str
    allowed: bool


@router.get("/{user_id}/permissions")
def get_user_permissions(
    *,
    db: Session = Depends(get_db),
    user_id: int,
    current_user: User = Depends(get_current_active_user),
) -> dict:
    if current_user.id != user_id and current_user.role not in ADMIN_ROLES:
        raise HTTPException(403, 'You can only view your own permissions.')
    db_user = crud_user.get(db, id=user_id)
    if not db_user:
        raise HTTPException(404, "User not found.")
    return {"permissions": effective_permissions(db, db_user), "catalog": all_permission_keys(), "module_roles": MODULE_ROLES, "supported": {key:permission_supported(_role_value(db_user.role),key) for key in all_permission_keys()}}


@router.put("/{user_id}/permissions")
def set_user_permission(
    *,
    db: Session = Depends(get_db),
    user_id: int,
    data: PermissionUpdate,
    current_user: User = Depends(require_admin),
) -> dict:
    if data.permission_key not in all_permission_keys():
        raise HTTPException(400, "Unknown permission.")
    db_user = crud_user.get(db, id=user_id)
    if not db_user:
        raise HTTPException(404, "User not found.")
    assert_staff_account_manager(db,current_user,db_user)
    _assert_manage_target(current_user, db_user)
    if data.allowed and not permission_supported(_role_value(db_user.role),data.permission_key):
        raise HTTPException(422,'This action is unavailable for the account role.')
    if current_user.id==db_user.id and data.permission_key in {'user_management.view','user_management.edit'} and not data.allowed:
        raise HTTPException(400,'You cannot remove your own account administration access.')
    if db_user.role == UserRole.OWNER and db_user.is_superuser:
        raise HTTPException(400, "The Owner break-glass account cannot have permissions disabled.")

    db.execute(
        text(
            """
            insert into public.user_permissions(user_id, permission_key, allowed, updated_at)
            values (:user_id, :permission_key, :allowed, CURRENT_TIMESTAMP)
            on conflict (user_id, permission_key)
            do update set allowed=excluded.allowed, updated_at=CURRENT_TIMESTAMP
            """
        ),
        {"user_id": user_id, "permission_key": data.permission_key, "allowed": data.allowed},
    )
    audit(db,current_user,db_user,'PERMISSION',{'permission_key':data.permission_key,'allowed':data.allowed})
    db.commit()
    return {"status": "success", "permission_key": data.permission_key, "allowed": data.allowed}


@router.delete("/{user_id}", response_model=UserResponse)
def delete_user(
    *,
    db: Session = Depends(get_db),
    user_id: int,
    current_user: User = Depends(require_admin),
) -> UserResponse:
    db_user = crud_user.get(db, id=user_id)
    if not db_user:
        raise HTTPException(404, "User not found.")
    if db_user.id == current_user.id:
        raise HTTPException(400, "You cannot delete your own account.")
    assert_staff_account_manager(db,current_user,db_user)
    _assert_manage_target(current_user, db_user)

    if db_user.role in ADMIN_ROLES:
        active_admins = db.query(User).filter(User.is_active.is_(True), User.role.in_(list(ADMIN_ROLES))).count()
        if active_admins <= 1:
            raise HTTPException(400, "The last active administrator cannot be deleted.")
    db_user.is_active=False
    db_user.session_version+=1
    audit(db,current_user,db_user,'DISABLE',{})
    db.commit();db.refresh(db_user)
    return db_user


@router.get('/{user_id}/audit')
def account_audit(user_id:int, db:Session=Depends(get_db), current_user:User=Depends(require_admin)):
    if not db.get(User,user_id): raise HTTPException(404,'User not found.')
    rows=db.query(AccountAccessAudit).filter_by(target_id=user_id).order_by(AccountAccessAudit.id.desc()).limit(100).all()
    return [{'id':r.id,'actor_id':r.actor_id,'action':r.action,'details':r.details,'created_at':r.created_at} for r in rows]
