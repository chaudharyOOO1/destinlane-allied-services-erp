from datetime import datetime, timedelta, timezone
from typing import Any, Union, Optional

import bcrypt
from jose import jwt

from app.core.config import settings


def _password_bytes(password: str) -> bytes:
    encoded = password.encode("utf-8")
    if len(encoded) > 72:
        raise ValueError("Password must be at most 72 UTF-8 bytes.")
    return encoded


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(_password_bytes(plain_password), hashed_password.encode("utf-8"))
    except (ValueError, TypeError, AttributeError):
        return False


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt()).decode("utf-8")


def create_access_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None, role: Optional[Union[str, Any]] = None) -> str:
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {"exp": expire, "sub": str(subject)}
    if role is not None:
        payload["role"] = getattr(role, "value", role)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
