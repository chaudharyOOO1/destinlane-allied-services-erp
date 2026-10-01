from typing import Dict, List

from sqlalchemy import text
from sqlalchemy.orm import Session

MODULES = [
    "dashboard", "employees", "recruitment", "clients", "sites", "rosters",
    "attendance", "billing", "payroll", "finance", "compliance", "risks",
    "owner", "user_management",
]
ACTIONS = ["view", "create", "edit", "delete", "approve", "export"]

ROLE_MODULE_DEFAULTS = {
    "OWNER": MODULES,
    "SUPER_ADMIN": MODULES,
    "ADMIN": MODULES,
    "HR": ["dashboard", "employees", "recruitment", "attendance", "compliance"],
    "OPERATIONS": ["dashboard", "sites", "rosters", "attendance", "risks"],
    "ACCOUNTS": ["dashboard", "clients", "billing", "payroll", "finance", "compliance"],
    "SUPERVISOR": ["dashboard", "sites", "rosters", "attendance"],
    "CLIENT": ["dashboard", "clients", "sites", "rosters", "attendance", "billing"],
    "STAFF": ["dashboard", "attendance"],
}


def permission_key(module: str, action: str = "view") -> str:
    return f"{module}.{action}"


def role_allows(role: str, key: str) -> bool:
    module, action = key.split(".", 1)
    if role in {"OWNER", "SUPER_ADMIN", "ADMIN"}:
        return True
    return action == "view" and module in ROLE_MODULE_DEFAULTS.get(role, [])


def _explicit_permission(db: Session, user_id: int, key: str):
    return db.execute(
        text(
            "select allowed from public.user_permissions "
            "where user_id=:user_id and permission_key=:key"
        ),
        {"user_id": user_id, "key": key},
    ).first()


def has_permission(db: Session, user, key: str) -> bool:
    if not user.is_active:
        return False

    role = getattr(user.role, "value", str(user.role))
    # OWNER is the emergency break-glass account and cannot be locked out by
    # a per-user deny rule.
    if role == "OWNER" and user.is_superuser:
        return True

    explicit = _explicit_permission(db, user.id, key)
    if explicit is not None:
        return bool(explicit.allowed)

    if user.is_superuser or role in {"SUPER_ADMIN", "ADMIN"}:
        return True

    return role_allows(role, key)


def effective_permissions(db: Session, user) -> Dict[str, bool]:
    role = getattr(user.role, "value", str(user.role))
    result = {
        permission_key(module, action): role_allows(role, permission_key(module, action))
        for module in MODULES
        for action in ACTIONS
    }

    if user.is_superuser or role in {"SUPER_ADMIN", "ADMIN"}:
        result = {key: True for key in result}

    rows = db.execute(
        text(
            "select permission_key, allowed from public.user_permissions "
            "where user_id=:user_id"
        ),
        {"user_id": user.id},
    ).all()
    for row in rows:
        if not (role == "OWNER" and user.is_superuser):
            result[row.permission_key] = bool(row.allowed)
    return result


def all_permission_keys() -> List[str]:
    return [permission_key(module, action) for module in MODULES for action in ACTIONS]
