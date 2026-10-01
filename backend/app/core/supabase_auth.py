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
