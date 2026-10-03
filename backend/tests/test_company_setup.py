import pytest
from sqlalchemy import text
from test_authentication import client
from app.models.user import User
from app.models.company import CompanySettingsHistory, CompanyDocument
from app.models.enums import UserRole
from app.schemas.company import CompanyProfile


@pytest.fixture
def company_client(client):
    http, sessions = client
    with sessions() as db:
        db.execute(text("ATTACH DATABASE ':memory:' AS public"))
        db.execute(text('CREATE TABLE public.user_permissions (user_id INTEGER, permission_key TEXT, allowed BOOLEAN)'))
        db.commit()
    response = http.post('/api/v1/auth/login', json={'login_id': 'ADMIN-001', 'password': 'test-password-before'})
    headers = {'Authorization': 'Bearer ' + response.json()['access_token']}
    return http, sessions, headers


def set_role(sessions, role):
    with sessions() as db:
        user = db.query(User).first()
        user.role = role
        user.is_superuser = role == UserRole.OWNER
        db.commit()


def test_company_persistence_dates_public_profile_and_version_conflict(company_client):
    http, sessions, headers = company_client
    original = http.get('/api/v1/erp/company', headers=headers).json()
    profile = original['profile']
    profile.update({'contact_email': 'office@destinlane.in', 'registration_date': '2025-03-01', 'gstin': '05ABCDE1234F1Z5', 'pan': 'ABCDE1234F', 'cin': 'U74999UT2025PTC123456', 'tan': 'ABCD12345E', 'branches': [{'code': 'DDN', 'name': 'Dehradun', 'state': 'Uttarakhand'}]})
    saved = http.put('/api/v1/erp/company', headers=headers, json={'version': 0, 'profile': profile})
    assert saved.status_code == 200
    assert saved.json()['version'] == 1
    assert saved.json()['financial_year']['start'] == '2026-04-01'
    assert saved.json()['financial_year']['end'] == '2027-03-31'
    assert http.get('/api/v1/erp/company', headers=headers).json()['profile']['tan'] == 'ABCD12345E'
    public = http.get('/api/v1/erp/company/profile', headers=headers).json()
    assert public['legal_name'] == profile['legal_name']
    assert not {'pan', 'tan', 'cin', 'registration_date'} & public.keys()
    assert http.put('/api/v1/erp/company', headers=headers, json={'version': 0, 'profile': profile}).status_code == 409
    removed = {**profile, 'branches': []}
    assert http.put('/api/v1/erp/company', headers=headers, json={'version': 1, 'profile': removed}).status_code == 422
    with sessions() as db:
        assert db.query(CompanySettingsHistory).count() == 1


@pytest.mark.parametrize('field,value', [('gstin','FAKE'), ('pan','INVALID'), ('tan','INVALID'), ('cin','INVALID'), ('registration_date','2099-01-01'), ('website','javascript:alert(1)'), ('contact_email','not-an-email')])
def test_bad_company_details_do_not_save(company_client, field, value):
    http, _, headers = company_client
    profile = http.get('/api/v1/erp/company', headers=headers).json()['profile']
    profile[field] = value
    assert http.put('/api/v1/erp/company', headers=headers, json={'version': 0, 'profile': profile}).status_code == 422
    assert http.get('/api/v1/erp/company', headers=headers).json()['version'] == 0


def test_duplicate_branch_codes_are_rejected():
    with pytest.raises(ValueError):
        CompanyProfile(branches=[{'code':'ddn','name':'One'}, {'code':'DDN','name':'Two'}])


def test_submitted_profile_is_owner_only_even_for_super_admin(company_client):
    http, sessions, headers = company_client
    set_role(sessions, UserRole.ADMIN)
    profile = http.get('/api/v1/erp/company', headers=headers).json()['profile']
    assert http.put('/api/v1/erp/company', headers=headers, json={'version':0,'profile':profile,'submit':True}).status_code == 422
    profile['registration_date'] = '2025-03-01'
    result = http.put('/api/v1/erp/company', headers=headers, json={'version':0,'profile':profile,'submit':True})
    assert result.status_code == 200
    assert result.json()['status'] == 'SUBMITTED'
    for role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        set_role(sessions, role)
        assert http.put('/api/v1/erp/company', headers=headers, json={'version':1,'profile':profile}).status_code == 403
        assert http.post('/api/v1/erp/company/documents', headers=headers, data={'document_type':'COI'}, files={'file':('test.pdf',b'%PDF-1.4\nverified-test','application/pdf')}).status_code == 403
    set_role(sessions, UserRole.OWNER)
    profile['city'] = 'Dehradun'
    assert http.put('/api/v1/erp/company', headers=headers, json={'version':1,'profile':profile}).status_code == 200
    with sessions() as db:
        assert [row.action for row in db.query(CompanySettingsHistory).order_by(CompanySettingsHistory.version)] == ['SUBMIT','UPDATE']


@pytest.mark.parametrize('role,expected', [(UserRole.HR,200),(UserRole.OPERATIONS,200),(UserRole.ACCOUNTS,200),(UserRole.STAFF,403),(UserRole.CLIENT,403),(UserRole.SUPERVISOR,403)])
def test_company_legal_records_internal_staff_boundary(company_client, role, expected):
    http, sessions, headers = company_client
    set_role(sessions, role)
    assert http.get('/api/v1/erp/company', headers=headers).status_code == expected
    assert http.get('/api/v1/erp/company/documents', headers=headers).status_code == expected
    assert http.get('/api/v1/erp/company').status_code == 401


def test_legal_document_upload_integrity_duplicate_access_and_owner_archive(company_client, monkeypatch):
    from app.api.v1.endpoints import company_documents as docs
    http, sessions, headers = company_client
    uploaded = []
    monkeypatch.setattr(docs, 'upload_company_file', lambda *args: uploaded.append(args))
    monkeypatch.setattr(docs, 'signed_company_url', lambda path: 'https://example.com/short-lived-private-file')
    bad = http.post('/api/v1/erp/company/documents', headers=headers, data={'document_type':'COI'}, files={'file':('bad.pdf',b'not-a-pdf','application/pdf')})
    assert bad.status_code == 422
    assert not uploaded
    content = b'%PDF-1.4\ncompany-test-not-a-legal-record'
    response = http.post('/api/v1/erp/company/documents', headers=headers, data={'document_type':'COI'}, files={'file':('test.pdf',content,'application/pdf')})
    assert response.status_code == 201
    doc_id = response.json()['id']
    assert 'storage_path' not in response.json()
    duplicate = http.post('/api/v1/erp/company/documents', headers=headers, data={'document_type':'COI'}, files={'file':('copy.pdf',content,'application/pdf')})
    assert duplicate.status_code == 409
    set_role(sessions, UserRole.HR)
    assert http.get(f'/api/v1/erp/company/documents/{doc_id}/download', headers=headers).status_code == 200
    assert http.post(f'/api/v1/erp/company/documents/{doc_id}/archive', headers=headers).status_code == 403
    set_role(sessions, UserRole.STAFF)
    assert http.get(f'/api/v1/erp/company/documents/{doc_id}/download', headers=headers).status_code == 403
    set_role(sessions, UserRole.OWNER)
    assert http.post(f'/api/v1/erp/company/documents/{doc_id}/archive', headers=headers).status_code == 200
    set_role(sessions, UserRole.HR)
    assert http.get('/api/v1/erp/company/documents', headers=headers).json()['documents'] == []
    assert http.get(f'/api/v1/erp/company/documents/{doc_id}/download', headers=headers).status_code == 404
    with sessions() as db:
        assert db.query(CompanyDocument).count() == 1


def test_explicit_staff_access_denial_is_enforced(company_client):
    http, sessions, headers = company_client
    set_role(sessions, UserRole.HR)
    with sessions() as db:
        user = db.query(User).first()
        db.execute(text("insert into public.user_permissions values (:id, 'company.view', false)"), {'id': user.id})
        db.commit()
    assert http.get('/api/v1/erp/company', headers=headers).status_code == 403
    assert http.get('/api/v1/erp/company/documents', headers=headers).status_code == 403


def test_inflight_staff_upload_is_rejected_if_owner_submits_profile(company_client, monkeypatch):
    from datetime import datetime, timezone
    from app.models.company import CompanySettings
    from app.api.v1.endpoints import company_documents as docs
    http, sessions, headers = company_client
    set_role(sessions, UserRole.ADMIN)
    cleaned = []
    def submit_during_upload(*args):
        with sessions() as db:
            db.add(CompanySettings(id=1, profile={}, version=1, submitted_at=datetime.now(timezone.utc)))
            db.commit()
    monkeypatch.setattr(docs, 'upload_company_file', submit_during_upload)
    monkeypatch.setattr(docs, 'remove_failed_upload', lambda path: cleaned.append(path))
    result = http.post('/api/v1/erp/company/documents', headers=headers, data={'document_type':'COI'}, files={'file':('test.pdf',b'%PDF-1.4\ncompany-test','application/pdf')})
    assert result.status_code == 403
    assert len(cleaned) == 1
    with sessions() as db:
        assert db.query(CompanyDocument).count() == 0
