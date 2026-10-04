import json
import pytest
from sqlalchemy import text
from test_authentication import client
from app.models.user import User
from app.models.account_audit import AccountAccessAudit
from app.models.enums import UserRole
from app.api.permissions import has_permission, effective_permissions, permission_supported


@pytest.fixture
def access_client(client,monkeypatch):
    from app.api.v1.endpoints import users
    from app.core.config import settings
    http,sessions=client
    with sessions() as db:
        db.execute(text("ATTACH DATABASE ':memory:' AS public"))
        db.execute(text('CREATE TABLE public.user_permissions(user_id INTEGER,permission_key TEXT,allowed BOOLEAN,updated_at TIMESTAMP,unique(user_id,permission_key))'))
        db.commit()
    monkeypatch.setattr(users,'provision_supabase_password_user',lambda **kw:{'id':'test-auth-only'})
    monkeypatch.setattr(settings,'SUPABASE_URL','')
    headers=login(http,'ADMIN-001','test-password-before')
    return http,sessions,headers


def login(http,name,password):
    response=http.post('/api/v1/auth/login',json={'login_id':name,'password':password})
    assert response.status_code==200
    return {'Authorization':'Bearer '+response.json()['access_token']}


def create(http,headers,role='OPERATIONS',name='OPS-1',phone='9876543210'):
    return http.post('/api/v1/users/',headers=headers,json={'login_id':name,'email':name.lower()+'@example.in','full_name':'Test Account','phone_number':phone,'password':'shared-temporary-password','role':role})


def test_account_creation_first_password_change_and_session_revocation(access_client):
    http,sessions,headers=access_client
    created=create(http,headers)
    assert created.status_code==201 and created.json()['must_change_password']
    uid=created.json()['id']
    temporary=login(http,'OPS-1','shared-temporary-password')
    assert http.get(f'/api/v1/users/{uid}/permissions',headers=temporary).status_code==403
    assert http.post('/api/v1/auth/change-password',headers=temporary,json={'current_password':'shared-temporary-password','new_password':'shared-temporary-password'}).status_code==400
    assert http.post('/api/v1/auth/change-password',headers=temporary,json={'current_password':'shared-temporary-password','new_password':'personal-new-password'}).status_code==200
    assert http.get('/api/v1/auth/me',headers=temporary).status_code==401
    fresh=login(http,'OPS-1','personal-new-password')
    assert not http.get('/api/v1/auth/me',headers=fresh).json()['must_change_password']
    own=http.get(f'/api/v1/users/{uid}/permissions',headers=fresh).json()
    assert own['permissions']['sites.view'] and not own['permissions']['user_management.view']
    assert http.get('/api/v1/users/1/permissions',headers=fresh).status_code==403
    assert http.post(f'/api/v1/users/{uid}/reset-password',headers=headers,json={'new_password':'another-temporary-password'}).status_code==200
    assert http.get('/api/v1/auth/me',headers=fresh).status_code==401
    with sessions() as db:
        audit=json.dumps([r.details for r in db.query(AccountAccessAudit).all()])
        assert 'shared-temporary-password' not in audit and 'another-temporary-password' not in audit


def test_permission_overrides_are_immediate_and_role_limits_hold(access_client):
    http,sessions,headers=access_client
    uid=create(http,headers).json()['id']
    for key,allowed in [('sites.view',False),('staff.view',True),('staff.create',True)]:
        assert http.put(f'/api/v1/users/{uid}/permissions',headers=headers,json={'permission_key':key,'allowed':allowed}).status_code==200
    permissions=http.get(f'/api/v1/users/{uid}/permissions',headers=headers).json()
    assert not permissions['permissions']['sites.view'] and permissions['permissions']['staff.view']
    assert http.put(f'/api/v1/users/{uid}/permissions',headers=headers,json={'permission_key':'user_management.create','allowed':True}).status_code==422
    assert http.put(f'/api/v1/users/{uid}/permissions',headers=headers,json={'permission_key':'unknown.view','allowed':True}).status_code==400
    assert http.put('/api/v1/users/1/permissions',headers=headers,json={'permission_key':'user_management.edit','allowed':False}).status_code==400
    with sessions() as db:
        account=db.get(User,uid)
        assert has_permission(db,account,'staff.view')
        assert not has_permission(db,account,'user_management.create')
        account.is_superuser=True;db.commit()
        assert not has_permission(db,account,'user_management.create')
    assert len(http.get(f'/api/v1/users/{uid}/audit',headers=headers).json())==4


def test_administrator_only_creation_and_upper_role_assignment(access_client):
    http,sessions,headers=access_client
    uid=create(http,headers).json()['id']
    with sessions() as db:
        account=db.get(User,uid);account.role=UserRole.ADMIN;account.must_change_password=False;db.commit()
    admin=login(http,'OPS-1','shared-temporary-password')
    assert create(http,admin,role='SUPER_ADMIN',name='UPPER-1',phone='9876543211').status_code==403
    assert http.put('/api/v1/users/1',headers=admin,json={'role':'STAFF'}).status_code==403
    assert http.put(f'/api/v1/users/{uid}',headers=headers,json={'role':'ACCOUNTS'}).status_code==200
    # JWT role is ignored in favor of the account's current database role.
    assert create(http,admin,name='BLOCKED',phone='9876543211').status_code==403
    assert http.put('/api/v1/users/1',headers=headers,json={'is_active':False}).status_code==400


def test_disabling_account_revokes_tokens_even_after_reenable(access_client):
    http,_,headers=access_client
    uid=create(http,headers).json()['id']
    token=login(http,'OPS-1','shared-temporary-password')
    assert http.put(f'/api/v1/users/{uid}',headers=headers,json={'is_active':False}).status_code==200
    assert http.get('/api/v1/auth/me',headers=token).status_code==401
    assert http.put(f'/api/v1/users/{uid}',headers=headers,json={'is_active':True}).status_code==200
    assert http.get('/api/v1/auth/me',headers=token).status_code==401


def test_case_insensitive_duplicate_identity_and_invalid_input(access_client):
    http,_,headers=access_client
    uid=create(http,headers,name='mixed-1').json()['id']
    assert create(http,headers,name='MIXED-1').status_code==409
    assert create(http,headers,name='OPS-2').status_code==409
    assert http.put(f'/api/v1/users/{uid}',headers=headers,json={'role':None}).status_code==422
    assert http.put(f'/api/v1/users/{uid}',headers=headers,json={'full_name':None}).status_code==422
    assert http.post(f'/api/v1/users/{uid}/reset-password',headers=headers,json={'new_password':'🙂'*30}).status_code==422


@pytest.mark.parametrize('role',[UserRole.STAFF,UserRole.CLIENT,UserRole.SUPERVISOR,UserRole.OPERATIONS,UserRole.HR])
def test_financial_dashboard_is_not_exposed_to_operational_or_employee_accounts(access_client,role):
    http,sessions,headers=access_client
    with sessions() as db:
        account=db.get(User,1);account.role=role;account.is_superuser=False;db.commit()
    assert http.get('/api/v1/erp/summary',headers=headers).status_code==403
    assert http.get('/api/v1/owner/executive-summary',headers=headers).status_code==403
