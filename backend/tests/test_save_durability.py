"""Save regressions use fresh sessions in disposable PostgreSQL databases."""
from sqlalchemy import text
from test_postgres_workflow import postgres_workflow, test_bootstrap_and_employee_to_invoice as bootstrap
from test_billing_validation import auth


def test_saves_survive_request_session(postgres_workflow):
    http, sessions, _, today, _, _, _, client_id, *_ = postgres_workflow
    headers = auth(http)
    cases = [
        ('accounts/invoices', {'client_id': client_id, 'invoice_number': 'DURABLE-1', 'billing_month': today.strftime('%Y-%m'), 'due_date': today.isoformat(), 'subtotal': '100.03'}, 'invoices'),
        ('accounts/expenses', {'category': 'Travel', 'amount': '250', 'expense_date': today.isoformat()}, 'expenses'),
        ('accounts/bookkeeping', {'account_type': 'BANK', 'debit': '250', 'credit': '0', 'entry_date': today.isoformat()}, 'bookkeeping_ledger'),
        ('corporate-compliances', {'compliance_type': 'TEST', 'period': '2026'}, 'corporate_compliances'),
    ]
    for endpoint, payload, table in cases:
        response = http.post('/api/v1/erp/' + endpoint, json=payload, headers=headers)
        assert response.status_code == 200, response.text
        with sessions() as db:
            row = db.execute(text(f'select * from {table} where id=:id'), {'id': response.json()['id']}).mappings().one()
            if table == 'invoices':
                assert row['issue_date'] == today
                assert row['cgst'] + row['sgst'] == row['tax_amount']


def test_finalised_payroll_is_immutable(postgres_workflow):
    bootstrap(postgres_workflow)
    http, sessions, _, today, *_ = postgres_workflow
    headers = auth(http)
    with sessions() as db:
        slip_id = db.execute(text("update salary_slips set lifecycle_status='DISBURSED' returning id")).scalar_one()
        before = dict(db.execute(text('select * from salary_slips where id=:id'), {'id': slip_id}).mappings().one())
        db.commit()
    response = http.post('/api/v1/erp/payroll/calculate', json={'month': today.strftime('%Y-%m')}, headers=headers)
    assert response.status_code == 409, response.text
    response = http.post(f'/api/v1/erp/payroll/{slip_id}/hold', json={'reason': 'Manual Flag', 'audit_note': 'Refuse'}, headers=headers)
    assert response.status_code == 409, response.text
    with sessions() as db:
        assert before == dict(db.execute(text('select * from salary_slips where id=:id'), {'id': slip_id}).mappings().one())


def test_employee_salary_uses_canonical_rows_and_owned_pdf(postgres_workflow):
    from uuid import uuid4
    from app.main import app
    from app.api.v1.endpoints.mobile_sync import get_mobile_employee
    bootstrap(postgres_workflow)
    http, sessions, *_ = postgres_workflow
    with sessions() as db:
        row = db.execute(text('select id,employee_id from salary_slips')).mappings().one()
        slip_id, employee_id = row['id'], row['employee_id']
    app.dependency_overrides[get_mobile_employee] = lambda: {'id': employee_id}
    try:
        assert http.get('/api/v1/mobile/me/salary').json() == []
        assert http.get(f'/api/v1/mobile/me/salary/{slip_id}/pdf').status_code == 404
        with sessions() as db:
            db.execute(text("update salary_slips set lifecycle_status='APPROVED' where id=:id"), {'id': slip_id})
            db.commit()
        response = http.get('/api/v1/mobile/me/salary')
        assert response.status_code == 200, response.text
        assert response.json()[0]['id'] == slip_id
        assert 'amount' in response.json()[0]
        pdf = http.get(f'/api/v1/mobile/me/salary/{slip_id}/pdf')
        assert pdf.status_code == 200, pdf.text
        assert pdf.content.startswith(b'%PDF')
        app.dependency_overrides[get_mobile_employee] = lambda: {'id': uuid4()}
        assert http.get('/api/v1/mobile/me/salary').json() == []
        assert http.get(f'/api/v1/mobile/me/salary/{slip_id}/pdf').status_code == 404
    finally:
        app.dependency_overrides.pop(get_mobile_employee, None)


def test_access_batch_is_atomic_and_detects_stale_edits(postgres_workflow):
    http, sessions, _, _, _, _, hr_id, *_ = postgres_workflow
    headers = auth(http)
    url = f'/api/v1/users/{hr_id}'
    snapshot = http.get(url + '/permissions', headers=headers).json()
    payload = {'revision': snapshot['revision'], 'changes': {'employees.create': False, 'unknown.view': True}}
    response = http.put(url + '/access', json=payload, headers=headers)
    assert response.status_code == 422, response.text
    assert http.get(url + '/permissions', headers=headers).json()['revision'] == snapshot['revision']
    payload['changes'] = {'employees.create': False}
    saved = http.put(url + '/access', json=payload, headers=headers)
    assert saved.status_code == 200, saved.text
    assert saved.json()['configured_permissions']['employees.create'] is False
    assert http.put(url + '/access', json=payload, headers=headers).status_code == 409
    inherited = http.put(url + '/access', json={'revision': saved.json()['revision'], 'changes': {'employees.create': None}}, headers=headers)
    assert inherited.status_code == 200, inherited.text
    assert 'employees.create' not in inherited.json()['overrides']


def test_effective_wages_require_coverage_and_keep_history(postgres_workflow):
    from datetime import timedelta
    bootstrap(postgres_workflow)
    http, sessions, _, today, *_ = postgres_workflow
    headers = auth(http)
    with sessions() as db:
        employee = db.execute(text('select employee_id from salary_slips')).scalar_one()
        db.execute(text('delete from employee_wage_rates'))
        db.commit()
    calculate = lambda: http.post('/api/v1/erp/payroll/calculate', json={'month': today.strftime('%Y-%m')}, headers=headers)
    assert calculate().status_code == 409
    payload = {'employee_id': str(employee), 'effective_from': today.isoformat(), 'daily_rate': '750.00', 'reason': 'Reviewed employment wage'}
    assert http.post('/api/v1/erp/payroll/wages', json={**payload, 'daily_rate': 0}, headers=headers).status_code == 422
    saved = http.post('/api/v1/erp/payroll/wages', json=payload, headers=headers)
    assert saved.status_code == 201, saved.text
    assert http.post('/api/v1/erp/payroll/wages', json=payload, headers=headers).status_code == 409
    future = {**payload, 'effective_from': (today + timedelta(days=1)).isoformat(), 'daily_rate': '999.00'}
    assert http.post('/api/v1/erp/payroll/wages', json=future, headers=headers).status_code == 201
    result = calculate()
    assert result.status_code == 200, result.text
    with sessions() as db:
        assert float(db.execute(text('select basic from salary_slips')).scalar_one()) == 750


def test_mobile_profile_and_private_documents_are_owned(postgres_workflow, monkeypatch):
    from uuid import uuid4
    from app.main import app
    from app.api.v1.endpoints import mobile_sync
    bootstrap(postgres_workflow)
    http, sessions, *_ = postgres_workflow
    with sessions() as db:
        employee = db.execute(text('select id,employee_code,name,phone,status,designation,site_id from employees')).mappings().one()
        employee = dict(employee)
    paths = []
    def sign(**kwargs):
        paths.append(kwargs)
        return 'https://storage.example.test/private-short-lived'
    monkeypatch.setattr(mobile_sync, 'create_supabase_signed_url', sign)
    app.dependency_overrides[mobile_sync.get_mobile_employee] = lambda: employee
    try:
        profile = http.get('/api/v1/mobile/me')
        assert profile.status_code == 200, profile.text
        assert profile.json()['doj'] and profile.json()['father_name']
        docs = http.get('/api/v1/mobile/me/documents')
        assert docs.status_code == 200, docs.text
        assert docs.json() and all('storage_path' not in row for row in docs.json())
        assert all(row['expires_in'] == 300 for row in paths)
        app.dependency_overrides[mobile_sync.get_mobile_employee] = lambda: {'id': uuid4()}
        assert http.get('/api/v1/mobile/me/documents').json() == []
    finally:
        app.dependency_overrides.pop(mobile_sync.get_mobile_employee, None)


def test_office_login_lockout_is_shared_across_identifiers(postgres_workflow):
    from datetime import datetime, timezone, timedelta
    http, sessions, *_ = postgres_workflow
    for attempt in range(5):
        identifier = 'TEST-OWNER' if attempt % 2 == 0 else 'owner@example.test'
        response = http.post('/api/v1/auth/login', json={'login_id': identifier, 'password': 'wrong-password'})
        assert response.status_code == 401, response.text
    response = http.post('/api/v1/auth/login', json={'login_id': 'TEST-OWNER', 'password': 'local-test-password'})
    assert response.status_code == 429
    with sessions() as db:
        db.execute(text('update users set login_locked_until=:past where login_id=:id'),
                   {'past': datetime.now(timezone.utc) - timedelta(seconds=1), 'id': 'TEST-OWNER'})
        db.commit()
    assert http.post('/api/v1/auth/login', json={'login_id': 'TEST-OWNER', 'password': 'local-test-password'}).status_code == 200
    with sessions() as db:
        assert db.execute(text("select failed_login_attempts from users where login_id='TEST-OWNER'")).scalar_one() == 0


def test_verified_candidate_creates_one_linked_joining_draft(postgres_workflow):
    http, sessions, _, _, _, _, _, client_id, *_ = postgres_workflow
    headers = auth(http)
    response = http.post('/api/v1/erp/recruitment', json={'full_name':'Local candidate','phone':'9876543210','vertical':'SECURITY','category':'GUARD'}, headers=headers)
    assert response.status_code == 201, response.text
    candidate = response.json()['candidate_id']
    url = f'/api/v1/erp/recruitment/{candidate}'
    intake = {'name':'Local candidate','phone':'9876543210','father_name':'Local parent','aadhaar_no':'234567890124','client_id':client_id,'branch':'BR-1'}
    assert http.post(url+'/onboard',json=intake,headers=headers).status_code == 409
    assert http.patch(url,json={'status':'VERIFIED'},headers=headers).status_code == 200
    assert http.post(url+'/onboard',json={**intake,'aadhaar_no':'bad'},headers=headers).status_code == 422
    with sessions() as db:
        assert db.execute(text('select count(*) from employees')).scalar_one() == 0
    joined = http.post(url+'/onboard',json=intake,headers=headers)
    assert joined.status_code == 201, joined.text
    assert joined.json()['joining_status'] == 'DRAFT'
    retry = http.post(url+'/onboard',json=intake,headers=headers)
    assert retry.status_code == 201 and retry.json()['id'] == joined.json()['id']
    with sessions() as db:
        assert db.execute(text('select count(*) from employees')).scalar_one() == 1
        assert str(db.execute(text('select employee_id from recruitment_candidates')).scalar_one()) == joined.json()['id']
    assert http.patch(url,json={'status':'APPLIED'},headers=headers).status_code == 409


def test_staff_pay_requires_monthly_management_decision(postgres_workflow):
    import json
    http, sessions, _, today, _, owner_id, hr_id, *_ = postgres_workflow
    headers = auth(http)
    month = today.strftime('%Y-%m')
    with sessions() as db:
        staff_id = db.execute(text("""insert into internal_staff(staff_code,name,phone,profile,status,created_by)
            values('DASS0010','Local office staff','9876543219',cast(:profile as jsonb),'ACTIVE',:owner) returning id"""),
            {'profile':json.dumps({'branch':'BR-1','designation':'Operations'}),'owner':owner_id}).scalar_one()
        db.commit()
    base = '/api/v1/erp/payroll/staff-monthly'
    assert http.get(base, params={'month':month}, headers=headers).json()['proposals'] == []
    proposed = http.post(base, json={'staff_id':staff_id,'month':month,'gross_pay':'10000.00','deductions':'500.00','work_note':'Branch work reviewed for this month'},headers=headers)
    assert proposed.status_code == 201, proposed.text
    row = proposed.json(); assert float(row['net_pay']) == 9500 and row['status'] == 'DRAFT'
    pay = {'version':1,'paid_on':today.isoformat(),'reference':'LOCAL-PAY-001'}
    assert http.post(f'{base}/{row["id"]}/pay', json=pay,headers=headers).status_code == 409
    with sessions() as db:
        for permission in ['payroll.view','payroll.approve']:
            db.execute(text('insert into user_permissions(user_id,permission_key,allowed) values(:id,:key,true)'),{'id':hr_id,'key':permission})
        db.commit()
    hr = auth(http,'TEST-HR')
    decision = {'version':1,'decision':'APPROVE','note':'Management reviewed branch work and remuneration'}
    assert http.post(f'{base}/{row["id"]}/decision',json=decision,headers=hr).status_code == 403
    approved = http.post(f'{base}/{row["id"]}/decision',json=decision,headers=headers)
    assert approved.status_code == 200, approved.text
    assert approved.json()['status'] == 'APPROVED'
    assert http.post(f'{base}/{row["id"]}/decision',json=decision,headers=headers).status_code == 409
    paid = http.post(f'{base}/{row["id"]}/pay',json={**pay,'version':2},headers=headers)
    assert paid.status_code == 200 and paid.json()['status'] == 'PAID',paid.text
    assert http.post(f'{base}/{row["id"]}/pay',json={**pay,'version':3},headers=headers).status_code == 409
    with sessions() as db:
        assert db.execute(text('select count(*) from salary_slips')).scalar_one() == 0
        assert db.execute(text('select count(*) from staff_monthly_pay_audit')).scalar_one() == 3


def test_invalid_account_amounts_are_rejected_before_writes(postgres_workflow):
    http, sessions, _, today, _, _, _, client_id, *_ = postgres_workflow
    headers=auth(http)
    invoice={'client_id':client_id,'invoice_number':'INVALID-1','billing_month':today.strftime('%Y-%m'),'due_date':today.isoformat(),'subtotal':'100.03'}
    for change in [{'subtotal':'-1'},{'subtotal':'NaN'},{'subtotal':'1e100'},{'tax_rate':'Infinity'},{'tax_mode':'OTHER'},{'billing_month':'2026-13'}]:
        assert http.post('/api/v1/erp/accounts/invoices',json={**invoice,**change},headers=headers).status_code==422
    for amount in ['-1','NaN','Infinity','abc']:
        assert http.post('/api/v1/erp/accounts/expenses',json={'category':'Travel','amount':amount},headers=headers).status_code==422
    assert http.post('/api/v1/erp/accounts/bookkeeping',json={'account_type':'BANK','debit':100,'credit':100},headers=headers).status_code==422
    with sessions() as db:
        for table in ['invoices','expenses','bookkeeping_ledger']:
            assert db.execute(text(f'select count(*) from {table}')).scalar_one()==0
