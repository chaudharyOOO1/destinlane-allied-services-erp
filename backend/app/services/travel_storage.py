"""Private receipt storage. Browser roles never receive object paths or service keys."""
import json
import urllib.error
import urllib.request
from urllib.parse import quote
from fastapi import HTTPException
from app.core.config import settings

BUCKET = 'travel-expense-receipts'
MAX_BYTES = 3 * 1024 * 1024
MIME_SIGNATURES = {'application/pdf': b'%PDF-', 'image/jpeg': b'\xff\xd8\xff', 'image/png': b'\x89PNG\r\n\x1a\n'}


def request(method, path, body=None, mime='application/json'):
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(503, 'Private travel receipt storage is not configured.')
    key = settings.SUPABASE_SERVICE_ROLE_KEY
    req = urllib.request.Request(f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/{path}", data=body,
        headers={'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': mime}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise HTTPException(503, 'Travel receipt storage is unavailable. No receipt was confirmed.') from None


def ensure_private_bucket():
    if request('GET', f'bucket/{BUCKET}').get('public') is not False:
        raise HTTPException(503, 'Travel receipts require a private storage bucket.')


def upload(path, content, mime):
    ensure_private_bucket()
    request('POST', f'object/{BUCKET}/{quote(path, safe="/")}', content, mime)


def signed_url(path):
    ensure_private_bucket()
    result = request('POST', f'object/sign/{BUCKET}/{quote(path, safe="/")}', json.dumps({'expiresIn': 60}).encode())
    signed = result.get('signedURL') or result.get('signedUrl')
    if not signed:
        raise HTTPException(502, 'Unable to open this receipt.')
    return signed if signed.startswith('https://') else f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1{signed}"


def remove_uncommitted(path):
    request('DELETE', f'object/{BUCKET}', json.dumps({'prefixes': [path]}).encode())
