from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, require_admin
from app.api.permissions import all_permission_keys, effective_permissions
from app.core.database import get_db
from app.core.security import get_password_hash
from app.core.supabase_auth import provision_supabase_password_user
from app.crud.crud_user import user as crud_user
from app.models.enums import UserRole
from app.models.user import User
from app.models.internal_staff import InternalStaff
from app.schemas.user import UserCreate, UserUpdate, UserResponse

router = APIRouter()
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
    if user_in.login_id:
        user_in.login_id = user_in.login_id.strip().upper()
        if user_in.login_id.startswith('S-DAS-'):
            staff_record = db.query(InternalStaff).filter_by(staff_code=user_in.login_id).first()
            if not staff_record or staff_record.status != 'ACTIVE':
                raise HTTPException(409, 'Staff must be registered and approved before creating their login.')
    if user_in.role in ADMIN_ROLES and _role_value(current_user.role) != "OWNER":
        raise HTTPException(403, "Only the Owner can create administrator accounts.")
    if crud_user.get_by_email(db, email=user_in.email):
        raise HTTPException(400, "A user with this email already exists.")
    if user_in.login_id and crud_user.get_by_login_id(db, login_id=user_in.login_id):
        raise HTTPException(400, "A user with this Login ID already exists.")

    auth_user = provision_supabase_password_user(email=user_in.email, password=user_in.password)
    if not auth_user:
        raise HTTPException(502, "Supabase Auth account provisioning failed.")

    try:
        return crud_user.create(db, obj_in=user_in)
    except Exception:
        db.rollback()
        raise HTTPException(409, "Unable to create the account. Check for duplicate account details.")


@router.get("/{user_id}", response_model=UserResponse)
def read_user(
    *,
    db: Session = Depends(get_db),
    user_id: int,
    current_user: User = Depends(get_current_active_user),
) -> UserResponse:
    if not (current_user.is_superuser or current_user.role in ADMIN_ROLES) and current_user.id != user_id:
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
    if "password" in update_dict:
        auth_user = provision_supabase_password_user(email=db_user.email, password=update_dict["password"])
        if not auth_user:
            raise HTTPException(502, "Supabase Auth password synchronization failed.")

    return crud_user.update(db, db_obj=db_user, obj_in=update_dict)


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=12, max_length=72)


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
    _assert_manage_target(current_user, db_user)

    auth_user = provision_supabase_password_user(email=db_user.email, password=data.new_password)
    if not auth_user:
        raise HTTPException(502, "Supabase Auth password synchronization failed.")

    db_user.hashed_password = get_password_hash(data.new_password)
    db_user.password_initialized_at = None
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
    return {"permissions": effective_permissions(db, db_user), "catalog": all_permission_keys()}


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
    _assert_manage_target(current_user, db_user)
    if db_user.role == UserRole.OWNER and db_user.is_superuser:
        raise HTTPException(400, "The Owner break-glass account cannot have permissions disabled.")

    db.execute(
        text(
            """
            insert into public.user_permissions(user_id, permission_key, allowed, updated_at)
            values (:user_id, :permission_key, :allowed, now())
            on conflict (user_id, permission_key)
            do update set allowed=excluded.allowed, updated_at=now()
            """
        ),
        {"user_id": user_id, "permission_key": data.permission_key, "allowed": data.allowed},
    )
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
    _assert_manage_target(current_user, db_user)

    if db_user.role in ADMIN_ROLES:
        active_admins = db.query(User).filter(User.is_active.is_(True), User.role.in_(list(ADMIN_ROLES))).count()
        if active_admins <= 1:
            raise HTTPException(400, "The last active administrator cannot be deleted.")
    return crud_user.remove(db, id=user_id)
