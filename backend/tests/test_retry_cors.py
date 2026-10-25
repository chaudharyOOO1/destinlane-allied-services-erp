"""CORS contracts for browser safe retry. No production services."""
from fastapi.testclient import TestClient
from app.main import app

def test_browser_safe_retry_preflight_accepts_only_configured_origin():
    with TestClient(app) as http:
        headers={
          'Origin':'http://localhost:5173',
          'Access-Control-Request-Method':'POST',
          'Access-Control-Request-Headers':'authorization,content-type,idempotency-key',
        }
        result=http.options('/api/v1/erp/internal-staff',headers=headers)
        assert result.status_code==200,result.text
        assert result.headers.get('access-control-allow-origin')=='http://localhost:5173'
        exposed=result.headers.get('access-control-allow-headers','').lower()
        assert 'idempotency-key' in exposed,exposed
        blocked=http.options('/api/v1/erp/internal-staff',headers={**headers,'Origin':'https://unknown-qa.invalid'})
        assert 'access-control-allow-origin' not in blocked.headers
