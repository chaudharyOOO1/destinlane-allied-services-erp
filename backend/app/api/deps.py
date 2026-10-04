from typing import Iterable
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

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login/access-token")


def _request_permission(request: Request) -> str | None:
    path = request.url.path.rstrip("/")
    api_prefix = settings.API_V1_STR.rstrip("/")
    if path.startswith(api_prefix + "/"):
        path = path[len(api_prefix):]
    if path == "/auth" or path.startswith("/auth/") or path in {"/health", ""}:
        return None
    if path == "/erp/company/profile" and request.method.upper() == "GET":
        return None
    mappings = [
        ("/erp/company","company"),("/erp/internal-staff","staff"),
        ("/users","user_management"),("/owner","owner"),("/erp/employees","employees"),
        ("/erp/recruitment","recruitment"),("/erp/staff","employees"),("/erp/clients","clients"),
        ("/erp/contracts","contracts"),("/erp/sites","sites"),("/erp/rosters","rosters"),
        ("/erp/attendance","attendance"),("/erp/payroll","payroll"),("/erp/accounts","finance"),
        ("/erp/billing","billing"),("/erp/compliance","compliance"),("/erp/risks","risks"),
        ("/erp/summary","dashboard"),("/erp/ifsc","employees"),
        ("/erp/employee-documents","employees"),("/erp/compliance-expiry","compliance"),
        ("/erp/corporate-compliances","compliance"),("/erp/expenses","finance"),
        ("/erp/risk-flags","risks"),("/erp/risk-engine","risks"),
    ]
    module = next((m for prefix,m in mappings if path == prefix or path.startswith(prefix + "/")), None)
    if module is None:
        return "__unknown__"
    if module == "staff" and (path.endswith("/submit") or path.endswith("/status")):
        return "staff.edit"
    if module == "staff" and path.endswith("/decision"):
        return "staff.approve"
    action = {"GET":"view","POST":"create","PUT":"edit","PATCH":"edit","DELETE":"delete"}.get(request.method.upper(),"view")
    return f"{module}.{action}"


def get_current_user(request: Request, db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials", headers={"WWW-Authenticate":"Bearer"})
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        token_data = TokenPayload(sub=user_id, role=payload.get("role"))
        user_id_int = int(token_data.sub)
    except (JWTError, ValidationError, TypeError, ValueError):
        raise credentials_exception
    user = crud_user.get(db, id=user_id_int)
    if user is None or not user.is_active:
        raise credentials_exception
    requested_permission = _request_permission(request)
    # The permission endpoint already restricts non-admins to their own account.
    # Let every active account read its own access flags for navigation.
    if request.method == 'GET' and request.url.path.rstrip('/') == f'{settings.API_V1_STR}/users/{user.id}/permissions':
        requested_permission = None
    if requested_permission and not has_permission(db, user, requested_permission):
        raise HTTPException(status_code=403, detail=f"Permission denied: {requested_permission}")
    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user


ADMIN_ROLES = [UserRole.OWNER, UserRole.SUPER_ADMIN, UserRole.ADMIN]

class RoleChecker:
    def __init__(self, allowed_roles: Iterable[UserRole], allow_super_admin: bool = True):
        self.allowed_roles = list(allowed_roles)
        self.allow_super_admin = allow_super_admin
    def __call__(self, current_user: User = Depends(get_current_active_user)) -> User:
        if self.allow_super_admin and (current_user.is_superuser or current_user.role in [UserRole.OWNER,UserRole.SUPER_ADMIN]):
            return current_user
        if current_user.role not in self.allowed_roles:
            role_names=[r.value for r in self.allowed_roles]
            raise HTTPException(403, f"Operation not permitted. Required role in {role_names}, but user has '{current_user.role.value}'.")
        return current_user

def require_roles(*roles: UserRole, allow_super_admin: bool = True) -> RoleChecker:
    return RoleChecker(list(roles), allow_super_admin=allow_super_admin)

def get_current_owner(current_user: User = Depends(get_current_active_user)) -> User:
    if current_user.role != UserRole.OWNER:
        raise HTTPException(403, "Owner clearance is required for this operation.")
    return current_user

require_owner = RoleChecker([UserRole.OWNER], allow_super_admin=False)
require_admin = RoleChecker([UserRole.OWNER,UserRole.SUPER_ADMIN,UserRole.ADMIN])
require_hr_or_admin = RoleChecker([UserRole.OWNER,UserRole.SUPER_ADMIN,UserRole.ADMIN,UserRole.HR])
require_ops_or_admin = RoleChecker([UserRole.OWNER,UserRole.SUPER_ADMIN,UserRole.ADMIN,UserRole.OPERATIONS,UserRole.SUPERVISOR])
require_accounts_or_admin = RoleChecker([UserRole.OWNER,UserRole.SUPER_ADMIN,UserRole.ADMIN,UserRole.ACCOUNTS])
require_client = RoleChecker([UserRole.CLIENT])
require_staff = RoleChecker([UserRole.STAFF], allow_super_admin=False)
require_admin_or_client = RoleChecker([UserRole.OWNER,UserRole.SUPER_ADMIN,UserRole.ADMIN,UserRole.CLIENT])
require_admin_or_staff = RoleChecker([UserRole.OWNER,UserRole.SUPER_ADMIN,UserRole.ADMIN,UserRole.STAFF])
