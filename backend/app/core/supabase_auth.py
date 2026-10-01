import json
import urllib.error
import urllib.request
from typing import Any

from app.core.config import settings


def _auth_headers() -> dict[str, str]:
    key = settings.SUPABASE_SERVICE_ROLE_KEY
    if not settings.SUPABASE_URL or not key:
        return {}
    return {"apikey": key, "Content-Type": "application/json"}


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

    # Existing Auth user: locate it and update its password through the
    # supported Supabase Auth admin endpoint.
    list_request = urllib.request.Request(
        f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/admin/users?per_page=100&page=1",
        headers=headers,
        method="GET",
    )
    try:
        with urllib.request.urlopen(list_request, timeout=8) as response:
            users = json.loads(response.read().decode("utf-8"))
        auth_user = next(
            (item for item in users.get("users", []) if item.get("email", "").lower() == email.lower()),
            None,
        )
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

    identifier = identifier.strip()
    payload: dict[str, str] = {"password": password}
    if "@" in identifier:
        payload["email"] = identifier
    else:
        payload["phone"] = identifier

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
