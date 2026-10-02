import json
import urllib.error
import urllib.request
from urllib.parse import quote, urlencode
from typing import Any

from app.models.enums import UserRole
from app.models.user import User

from app.core.config import settings


def _auth_headers() -> dict[str, str]:
    key = settings.SUPABASE_SERVICE_ROLE_KEY
    if not settings.SUPABASE_URL or not key:
        return {}
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def provision_supabase_password_user(*, email: str, password: str) -> dict[str, Any] | None:
    headers = _auth_headers()
    if not headers:
        return None

    payload = {"email": email, "password": password, "email_confirm": True}
    create_request = urllib.request.Request(
        f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/admin/users",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(create_request, timeout=8) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code != 422:
            return None

    list_request = urllib.request.Request(
        f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/admin/users?per_page=100&page=1",
        headers=headers,
        method="GET",
    )
    try:
        with urllib.request.urlopen(list_request, timeout=8) as response:
            users = json.loads(response.read().decode("utf-8"))
        auth_user = next((item for item in users.get("users", []) if item.get("email", "").lower() == email.lower()), None)
        if not auth_user:
            return None
        user_id = auth_user.get("id")
        update_request = urllib.request.Request(
            f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/admin/users/{user_id}",
            data=json.dumps({"password": password, "email_confirm": True}).encode("utf-8"),
            headers=headers,
            method="PUT",
        )
        with urllib.request.urlopen(update_request, timeout=8) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
        return None


def verify_supabase_password(*, identifier: str, password: str) -> dict[str, Any] | None:
    headers = _auth_headers()
    if not headers:
        return None
    payload: dict[str, str] = {"password": password}
    if "@" in identifier:
        payload["email"] = identifier.strip()
    else:
        payload["phone"] = identifier.strip()

    request = urllib.request.Request(
        f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/token?grant_type=password",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
        return None


def get_supabase_user_profile(identifier: str) -> dict[str, Any] | None:
    headers = _auth_headers()
    if not headers:
        return None
    value = identifier.strip()
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    filters = f"or=(login_id.eq.{quote(escaped, safe='')},email.eq.{quote(escaped, safe='')},phone_number.eq.{quote(escaped, safe='')})"
    query = urlencode({
        "select": "id,email,login_id,full_name,phone_number,role,is_active,is_superuser",
        "limit": "1",
    }) + "&" + filters
    request = urllib.request.Request(
        f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/users?{query}",
        headers={**headers, "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            rows = json.loads(response.read().decode("utf-8"))
        return rows[0] if rows else None
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
        return None


def authenticate_supabase_user(identifier: str, password: str) -> User | None:
    profile = get_supabase_user_profile(identifier)
    if not profile or not profile.get("is_active"):
        return None

    email = str(profile.get("email") or "").strip()
    if not email or not verify_supabase_password(identifier=email, password=password):
        return None

    try:
        role = UserRole(str(profile.get("role") or "STAFF"))
    except ValueError:
        role = UserRole.STAFF

    return User(
        id=int(profile["id"]),
        email=email,
        login_id=profile.get("login_id"),
        full_name=profile.get("full_name") or email,
        phone_number=profile.get("phone_number"),
        role=role,
        is_active=bool(profile.get("is_active")),
        is_superuser=bool(profile.get("is_superuser")),
    )


def upload_supabase_storage(*, bucket: str, path: str, data: bytes, content_type: str) -> str | None:
    headers = _auth_headers()
    if not headers:
        return None
    headers = {**headers, "Content-Type": content_type, "x-upsert": "false"}
    request = urllib.request.Request(
        f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/{bucket}/{path}",
        data=data,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            response.read()
        return path
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return None


def create_supabase_signed_url(*, bucket: str, path: str, expires_in: int = 3600) -> str | None:
    headers = _auth_headers()
    if not headers:
        return None
    request = urllib.request.Request(
        f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/sign/{bucket}/{path}",
        data=json.dumps({"expiresIn": expires_in}).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            result = json.loads(response.read().decode("utf-8"))
        signed = result.get("signedURL") or result.get("signedUrl")
        if not signed:
            return None
        if signed.startswith("http"):
            return signed
        return f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1{signed}"
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
        return None
