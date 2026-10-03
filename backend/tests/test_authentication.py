"""Exercise the real login/recovery routes against an isolated test database."""
import os
import secrets
import sys
from pathlib import Path

os.environ.setdefault('SECRET_KEY', secrets.token_urlsafe(32))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from app.main import app
from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.models.enums import UserRole
from app.api.deps import _request_permission


@pytest.fixture
def client(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as db:
        db.add(User(login_id='ADMIN-001', email='admin@destinlane.in', full_name='Administrator',
                    role=UserRole.OWNER, is_active=True, is_superuser=True,
                    hashed_password=get_password_hash('test-password-before')))
        db.commit()
    def test_db():
        with session_factory() as db:
            yield db
    app.dependency_overrides[get_db] = test_db
    monkeypatch.setattr(settings, 'ADMIN_SETUP_TOKEN', 'test-recovery-token-only')
    with TestClient(app) as test_client:
        yield test_client, session_factory
    app.dependency_overrides.clear()
    engine.dispose()


def test_login_me_and_invalid_credentials(client):
    http, _ = client
    assert http.post('/api/v1/auth/login', json={'login_id': 'missing', 'password': 'invalid'}).status_code == 401
    response = http.post('/api/v1/auth/login', json={'login_id': 'ADMIN-001', 'password': 'test-password-before'})
    assert response.status_code == 200
    token = response.json()['access_token']
    me = http.get('/api/v1/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert me.status_code == 200
    assert me.json()['login_id'] == 'ADMIN-001'
    assert 'hashed_password' not in me.json()
    assert http.get('/api/v1/auth/me').status_code == 401


def test_disabled_account_cannot_login(client):
    http, sessions = client
    with sessions() as db:
        account = db.query(User).first()
        account.is_active = False
        db.commit()
    assert http.post('/api/v1/auth/login', json={'login_id': 'ADMIN-001', 'password': 'test-password-before'}).status_code == 401


def test_admin_recovery_changes_login_password(client):
    http, _ = client
    payload = {'login_id': 'ADMIN-001', 'recovery_token': 'incorrect-token', 'new_password': 'test-password-after'}
    assert http.post('/api/v1/auth/admin-recover-password', json=payload).status_code == 403
    payload['recovery_token'] = 'test-recovery-token-only'
    assert http.post('/api/v1/auth/admin-recover-password', json=payload).status_code == 200
    assert http.post('/api/v1/auth/login', json={'login_id': 'ADMIN-001', 'password': 'test-password-before'}).status_code == 401
    response = http.post('/api/v1/auth/login', json={'login_id': 'ADMIN-001', 'password': 'test-password-after'})
    assert response.status_code == 200
    assert response.json()['user']['password_initialized_at'] is not None


def test_malformed_password_hash_is_rejected():
    assert verify_password('test-password', 'invalid-hash') is False
    assert verify_password('test-password', None) is False


@pytest.mark.parametrize('identity,active,expected', [
    (None, True, 401),
    ({'email': 'different@example.com', 'email_confirmed_at': 'confirmed'}, True, 403),
    ({'email': 'admin@destinlane.in'}, True, 401),
    ({'email': 'admin@destinlane.in', 'email_confirmed_at': 'confirmed'}, False, 403),
    ({'email': 'ADMIN@DESTINLANE.IN', 'email_confirmed_at': 'confirmed'}, True, 200),
])
def test_email_recovery_binds_verified_identity_to_active_account(client, monkeypatch, identity, active, expected):
    from app.api.v1.endpoints import auth
    http, sessions = client
    monkeypatch.setattr(settings, 'SUPABASE_URL', 'https://example.supabase.co')
    monkeypatch.setattr(settings, 'SUPABASE_SERVICE_ROLE_KEY', 'test-service-key')
    monkeypatch.setattr(auth, 'get_recovery_user', lambda token: identity)
    updates = []
    monkeypatch.setattr(auth, 'update_recovery_password', lambda **kw: updates.append(kw) or True)
    with sessions() as db:
        db.query(User).first().is_active = active
        db.commit()
    response = http.post('/api/v1/auth/reset-password', json={'access_token': 'test-recovery-access-token', 'new_password': 'test-recovered-password'})
    assert response.status_code == expected
    assert bool(updates) == (expected == 200)
    with sessions() as db:
        account = db.query(User).first()
        assert verify_password('test-recovered-password', account.hashed_password) == (expected == 200)
    if expected == 200:
        assert http.post('/api/v1/auth/login', json={'login_id': 'ADMIN-001', 'password': 'test-recovered-password'}).status_code == 200
        assert http.post('/api/v1/auth/login', json={'login_id': 'ADMIN-001', 'password': 'test-password-before'}).status_code == 401


def test_email_recovery_does_not_change_erp_password_when_provider_fails(client, monkeypatch):
    from app.api.v1.endpoints import auth
    http, _ = client
    monkeypatch.setattr(settings, 'SUPABASE_URL', 'https://example.supabase.co')
    monkeypatch.setattr(settings, 'SUPABASE_SERVICE_ROLE_KEY', 'test-service-key')
    monkeypatch.setattr(auth, 'get_recovery_user', lambda token: {'email': 'admin@destinlane.in', 'email_confirmed_at': 'confirmed'})
    monkeypatch.setattr(auth, 'update_recovery_password', lambda **kw: False)
    response = http.post('/api/v1/auth/reset-password', json={'access_token': 'test-recovery-access-token', 'new_password': 'test-recovered-password'})
    assert response.status_code == 502
    assert http.post('/api/v1/auth/login', json={'login_id': 'ADMIN-001', 'password': 'test-password-before'}).status_code == 200


@pytest.mark.parametrize('path,method,expected', [
    ('/api/v1/auth/me', 'GET', None),
    ('/api/v1/erp/employees', 'GET', 'employees.view'),
    ('/api/v1/erp/employees/12', 'PATCH', 'employees.edit'),
    ('/api/v1/erp/summary', 'GET', 'dashboard.view'),
    ('/api/v1/erp/contracts', 'POST', 'contracts.create'),
    ('/api/v1/erp/risk-flags', 'GET', 'risks.view'),
    ('/api/v1/erp/employee-documents', 'GET', 'employees.view'),
    ('/api/v1/erp/employees-unrecognized', 'GET', '__unknown__'),
])
def test_deployed_route_permissions(path, method, expected):
    request = Request({'type': 'http', 'path': path, 'method': method, 'headers': []})
    assert _request_permission(request) == expected


def test_database_failure_returns_safe_diagnostic(client, monkeypatch):
    from sqlalchemy.exc import OperationalError
    from app.crud.crud_user import user as crud_user
    http, _ = client
    def unavailable(*args, **kwargs):
        raise OperationalError('select private_data', {}, Exception('connection refused: private-db-host'))
    monkeypatch.setattr(crud_user, 'authenticate', unavailable)
    response = http.post('/api/v1/auth/login', json={'login_id': 'ADMIN-001', 'password': 'test-password-before'})
    assert response.status_code == 503
    assert response.json()['error_code'] == 'DATABASE_CONNECTION_REFUSED'
    assert response.json()['error_id']
    assert 'private-db-host' not in response.text
    assert 'private_data' not in response.text


def test_database_diagnostics_redact_connection_secrets(monkeypatch):
    from app.main import _safe_database_reason
    monkeypatch.setattr(settings, 'DATABASE_URL', 'postgresql://user:private-test-password@host/db')
    monkeypatch.setattr(settings, 'POSTGRES_PASSWORD', 'private-test-password')
    monkeypatch.setattr(settings, 'SUPABASE_SERVICE_ROLE_KEY', 'private-test-service-key')
    reason = _safe_database_reason(Exception('failed postgresql://user:private-test-password@host/db private-test-service-key'))
    assert 'private-test-password' not in reason
    assert 'private-test-service-key' not in reason
    assert 'postgresql://' not in reason


@pytest.mark.parametrize('raw', [
    'postgresql://postgres.project:test@8927@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres?sslmode=require',
    'postgres://postgres.project:test%408927@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres?sslmode=require',
    'postgresql+psycopg://postgres.project:test%408927@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres?sslmode=require',
])
def test_database_url_password_separator_preserves_target(raw, monkeypatch):
    from sqlalchemy.engine import make_url
    monkeypatch.setattr(settings, 'DATABASE_URL', raw)
    parsed = make_url(settings.sync_database_url)
    assert parsed.drivername == 'postgresql+psycopg'
    assert parsed.username == 'postgres.project'
    assert parsed.password == 'test@8927'
    assert parsed.host == 'aws-0-ap-southeast-1.pooler.supabase.com'
    assert parsed.port == 5432
    assert parsed.database == 'postgres'
    assert parsed.query['sslmode'] == 'require'
