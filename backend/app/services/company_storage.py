import json
import urllib.request
import urllib.error
from urllib.parse import quote
from fastapi import HTTPException
from app.core.config import settings

BUCKET = 'company-legal-documents'
MAX_BYTES = 3 * 1024 * 1024
ALLOWED_MIME = {'application/pdf': b'%PDF-', 'image/jpeg': b'\xff\xd8\xff', 'image/png': b'\x89PNG\r\n\x1a\n'}


def storage_request(method, path, body=None, mime='application/json'):
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(503, 'Company document storage is not configured.')
    key = settings.SUPABASE_SERVICE_ROLE_KEY
    request = urllib.request.Request(f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/{path}", data=body,
        headers={'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': mime}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            content = response.read()
            return json.loads(content) if content else {}
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise HTTPException(404, 'Company document storage item was not found.') from None
        if exc.code == 409:
            raise HTTPException(409, 'Storage item already exists.') from None
        raise HTTPException(502, 'Company document storage request failed. Please retry.') from None
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise HTTPException(503, 'Company document storage is temporarily unavailable.') from None


def ensure_private_bucket():
    try:
        bucket = storage_request('GET', f'bucket/{BUCKET}')
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        body = {'id': BUCKET, 'name': BUCKET, 'public': False, 'file_size_limit': MAX_BYTES, 'allowed_mime_types': list(ALLOWED_MIME)}
        try:
            storage_request('POST', 'bucket', json.dumps(body).encode())
        except HTTPException as create_error:
            if create_error.status_code != 409:
                raise
        bucket = storage_request('GET', f'bucket/{BUCKET}')
    if bucket.get('public') is not False:
        raise HTTPException(503, 'Company legal documents require private storage.')


def upload_company_file(path, content, mime):
    ensure_private_bucket()
    storage_request('POST', f'object/{BUCKET}/{quote(path, safe="/")}', content, mime)


def signed_company_url(path):
    ensure_private_bucket()
    result = storage_request('POST', f'object/sign/{BUCKET}/{quote(path, safe="/")}', json.dumps({'expiresIn': 60}).encode())
    signed = result.get('signedURL') or result.get('signedUrl')
    if not signed:
        raise HTTPException(502, 'Unable to open this company document.')
    return signed if signed.startswith('https://') else f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1{signed}"


def remove_failed_upload(path):
    # Compensation only for an upload that never obtained a database record.
    storage_request('DELETE', f'object/{BUCKET}', json.dumps({'prefixes': [path]}).encode())
