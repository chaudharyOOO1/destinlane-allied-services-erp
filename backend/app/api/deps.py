from typing import Generator, Iterable
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.crud.crud_user import user as crud_user
from app.models.user import User
from app.models.enums import UserRole
from app.schemas.token import TokenPayload
from app.api.permissions import has_permission

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login/access-token"
)


def _request_permission(request: Request) -> str | None:
    path = request.url.path.rstrip("/")
    if path.startswith("/api/v1/auth") or path in {"/health", ""}:
        return None

    mappings = [
        ("/users", "user_management"),
        ("/owner", "owner"),
        ("/erp/employees", "employees"),
        ("/erp/recruitment", "recruitment"),
        ("/erp/staff", "employees"),
        ("/erp/clients", "clients"),
        ("/erp/contracts", "contracts"),
        ("/erp/sites", "sites"),
        ("/erp/rosters", "rosters"),
        ("/erp/attendance", "attendance"),
        ("/erp/payroll", "payroll"),
        ("/erp/accounts", "finance"),
        ("/erp/billing", "billing"),
        ("/erp/compliance", "compliance"),
        ("/erp/risks", "risks"),
    ]
    module = next((module for prefix, module in mappings if path.startswith(prefix)), None)
    if module is None:
        # Fail closed for newly added API routes until their permission mapping
        # is explicitly reviewed.
        return "__unknown__"

    action = {
        "GET": "view",
        "POST": "create",
        "PUT": "edit",
        "PATCH": "edit",
        "DELETE": "delete",
    }.get(request.method.upper(), "view")
    return f"{module}.{action}"


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        token_data = TokenPayload(sub=user_id, role=payload.get("role"))
    except (JWTError, ValidationError):
        raise credentials_exception

    try:
        user_id_int = int(token_data.sub)
    except (TypeError, ValueError):
        raise credentials_exception

    user = crud_user.get(db, id=user_id_int)
    if user is None or not user.is_active:
        raise credentials_exception

    requested_permission = _request_permission(request)
    if requested_permission and not has_permission(db, user, requested_permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {requested_permission}",
        )
    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user


ADMIN_ROLES = [UserRole.OWNER, UserRole.SUPER_ADMIN, UserRole.ADMIN]


class RoleChecker:
    def __init__(self, allowed_roles: Iterable[UserRole], allow_super_admin: bool = True):
        self.allowed_roles = list(allowed_roles)
        self.allow_super_admin = allow_super_admin

    def __call__(self, current_user: User = Depends(get_current_active_user)) -> User:
        if self.allow_super_admin and (
            current_user.is_superuser
            or current_user.role in [UserRole.OWNER, UserRole.SUPER_ADMIN]
        ):
            return current_user
        if current_user.role not in self.allowed_roles:
            role_names = [role.value for role in self.allowed_roles]
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted. Required role in {role_names}, but user has '{current_user.role.value}'.",
            )
        return current_user


def require_roles(*roles: UserRole, allow_super_admin: bool = True) -> RoleChecker:
    return RoleChecker(list(roles), allow_super_admin=allow_super_admin)


def get_current_owner(current_user: User = Depends(get_current_active_user)) -> User:
    if current_user.role != UserRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner clearance is required for this operation.")
    return current_user


require_owner = RoleChecker([UserRole.OWNER], allow_super_admin=False)
require_admin = RoleChecker([UserRole.OWNER, UserRole.SUPER_ADMIN, UserRole.ADMIN])
require_hr_or_admin = RoleChecker([UserRole.OWNER, UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.HR])
require_ops_or_admin = RoleChecker([UserRole.OWNER, UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.OPERATIONS, UserRole.SUPERVISOR])
require_accounts_or_admin = RoleChecker([UserRole.OWNER, UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.ACCOUNTS])
require_client = RoleChecker([UserRole.CLIENT])
require_staff = RoleChecker([UserRole.STAFF], allow_super_admin=False)
require_admin_or_client = RoleChecker([UserRole.OWNER, UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.CLIENT])
require_admin_or_staff = RoleChecker([UserRole.OWNER, UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.STAFF])
