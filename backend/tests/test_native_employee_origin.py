"""Native CORS permits requests, while authentication still denies data access."""
import os
os.environ.setdefault('SECRET_KEY','isolated-native-origin-test-secret')
from fastapi.testclient import TestClient
from app.main import app


def test_native_preflight_and_anonymous_ownership_gate():
    with TestClient(app) as http:
        for origin in ['https://localhost','capacitor://localhost']:
            response=http.options('/api/v1/mobile/login',headers={
                'Origin':origin,'Access-Control-Request-Method':'POST',
                'Access-Control-Request-Headers':'content-type,authorization'})
            assert response.status_code==200
            assert response.headers['access-control-allow-origin']==origin
            response=http.get('/api/v1/mobile/me/documents',headers={'Origin':origin})
            assert response.status_code==401
        blocked=http.options('/api/v1/mobile/login',headers={
            'Origin':'https://untrusted.example.test','Access-Control-Request-Method':'POST'})
        assert blocked.status_code==400
        assert 'access-control-allow-origin' not in blocked.headers
