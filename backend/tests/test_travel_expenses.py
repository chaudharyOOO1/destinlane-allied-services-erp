"""Travel boundaries/lifecycle; real accounting posting uses disposable PostgreSQL."""
from datetime import timedelta
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import text
from fastapi import HTTPException
from test_authentication import client
from test_postgres_workflow import postgres_workflow
from app.core.business_time import business_date
from app.models.user import User
from app.models.enums import UserRole
from app.models.travel_expense import TravelExpenseClaim, TravelExpenseHistory, TravelExpenseReceipt
from app.api.permissions import permission_supported
from app.services import travel_storage

BASE = '/api/v1/erp/travel-expenses'


def payload(**updates):
    day = business_date().isoformat()
    return {'purpose':'Client site inspection','origin':'Delhi','destination':'Noida','start_date':day,'end_date':day,
            'items':[{'date':day,'category':'TRANSPORT','description':'Return train ticket','amount':'250.25','bill_number':'TEST-001'}],
            'missing_receipt_reason':'Local test receipt unavailable', **updates}


@pytest.fixture
def travel_client(client):
    http, sessions = client
    with sessions() as db:
        db.execute(text("ATTACH DATABASE ':memory:' AS public"))
        db.execute(text('CREATE TABLE public.user_permissions(user_id INTEGER,permission_key TEXT,allowed BOOLEAN, UNIQUE(user_id,permission_key))'))
        db.commit()
    def actor(role, name=None):
        name = name or role
        with sessions() as db:
            existing = db.query(User).filter_by(login_id=name).first()
            if existing is None:
                original = db.query(User).filter_by(login_id='ADMIN-001').one()
                existing = User(login_id=name,email=name.lower()+'@example.invalid',full_name=name,role=UserRole[role],
                                hashed_password=original.hashed_password,is_active=True,is_superuser=False)
                db.add(existing); db.commit()
            uid = existing.id
        response = http.post('/api/v1/auth/login',json={'login_id':name,'password':'test-password-before'})
        assert response.status_code == 200, response.text
        return {'Authorization':'Bearer '+response.json()['access_token']}, uid
    return http, sessions, actor


def create(http, headers, data=None):
    response = http.post(BASE,headers=headers,json=data or payload())
    assert response.status_code == 201, response.text
    return response.json()


def action(http, row, headers, path, expected=200, **values):
    response = http.post(f"{BASE}/{row['id']}/{path}",headers=headers,json={'version':row['version'],**values})
    assert response.status_code == expected, response.text
    return response.json()


def test_ownership_rejection_correction_and_independent_hr_approval(travel_client):
    http,sessions,actor = travel_client
    staff,uid = actor('OPERATIONS'); other,_ = actor('OPERATIONS','OTHER'); hr,hr_id = actor('HR')
    row = create(http,staff)
    assert row['requester_id'] == uid and row['total_amount'] == '250.25' and row['status'] == 'DRAFT'
    assert http.get(f"{BASE}/{row['id']}",headers=other).status_code == 404
    assert http.get(BASE+'?scope=all',headers=staff).status_code == 403
    assert len(http.get(BASE,headers=staff).json()['claims']) == 1
    assert http.get(BASE,headers=other).json()['claims'] == []
    assert http.get(BASE).status_code == 401
    action(http,row,staff,'decision',403,decision='APPROVE')
    submitted = action(http,row,staff,'submit')
    assert http.put(f"{BASE}/{row['id']}",headers=staff,json={**payload(),'version':submitted['version']}).status_code == 409
    action(http,submitted,hr,'decision',422,decision='REJECT')
    rejected = action(http,submitted,hr,'decision',decision='REJECT',remarks='Provide trip detail')
    changed = http.put(f"{BASE}/{row['id']}",headers=staff,json={**payload(purpose='Detailed branch inspection'),'version':rejected['version']})
    assert changed.status_code == 200, changed.text
    resubmitted = action(http,changed.json(),staff,'submit')
    approved = action(http,resubmitted,hr,'decision',decision='APPROVE',remarks='Reviewed')
    assert approved['reviewed_by'] == hr_id
    assert [h['action'] for h in approved['history']] == ['CREATE','SUBMIT','REJECT','UPDATE','SUBMIT','APPROVE']
    action(http,approved,hr,'decision',409,decision='APPROVE')


def test_self_review_permission_denials_and_supported_roles(travel_client):
    http,sessions,actor = travel_client
    hr,uid = actor('HR')
    row = action(http,create(http,hr),hr,'submit')
    action(http,row,hr,'decision',403,decision='APPROVE')
    with sessions() as db:
        db.execute(text("insert into public.user_permissions values(:id,'travel_expenses.create',false)"),{'id':uid});db.commit()
    assert http.post(BASE,headers=hr,json=payload()).status_code == 403
    for role,key,allowed in [('HR','approve',True),('HR','pay',False),('ACCOUNTS','pay',True),('OWNER','pay',True),('ACCOUNTS','approve',False),('OPERATIONS','approve',False)]:
        assert permission_supported(role,'travel_expenses.'+key) == allowed
    assert not permission_supported('OWNER','finance.pay')
    for role in ['CLIENT','STAFF']:
        blocked,_ = actor(role)
        assert http.get(BASE,headers=blocked).status_code == 403
        assert http.post(BASE,headers=blocked,json=payload()).status_code == 403


@pytest.mark.parametrize('updates',[
    {'requester_id':99}, {'total_amount':'0.01'}, {'status':'APPROVED'}, {'end_date':'2000-01-01'}, {'items':[]},
    {'items':[{'date':'2000-01-01','category':'TRANSPORT','description':'Bad date','amount':'1'}]},
    {'items':[{'date':business_date().isoformat(),'category':'TRANSPORT','description':'Negative','amount':'-1'}]},
    {'items':[{'date':business_date().isoformat(),'category':'TRANSPORT','description':'Precision','amount':'1.001'}]},
])
def test_invalid_claims(travel_client,updates):
    http,_,actor = travel_client; staff,_ = actor('OPERATIONS')
    assert http.post(BASE,headers=staff,json=payload(**updates)).status_code == 422


def test_submission_readiness_and_stale_versions(travel_client):
    http,_,actor = travel_client; staff,_ = actor('OPERATIONS')
    row = create(http,staff,payload(missing_receipt_reason=''))
    action(http,row,staff,'submit',422)
    changed = http.put(f"{BASE}/{row['id']}",headers=staff,json={**payload(),'version':row['version']}).json()
    action(http,row,staff,'submit',409)
    assert changed['version'] == 2
    tomorrow = (business_date()+timedelta(days=1)).isoformat()
    future = create(http,staff,payload(start_date=tomorrow,end_date=tomorrow,items=[{'date':tomorrow,'category':'MEALS','description':'Future trip','amount':'100'}]))
    action(http,future,staff,'submit',422)
    assert http.post(BASE,headers=staff,json=payload(branch='UNKNOWN')).status_code == 422


def test_private_receipts_validation_duplicates_and_edit_lock(travel_client,monkeypatch):
    http,_,actor = travel_client; staff,_ = actor('OPERATIONS'); other,_ = actor('OPERATIONS','OTHER')
    uploaded=[]
    monkeypatch.setattr(travel_storage,'upload',lambda *args:uploaded.append(args))
    monkeypatch.setattr(travel_storage,'signed_url',lambda path:'https://example.invalid/private-receipt')
    row = create(http,staff,payload(missing_receipt_reason=''))
    path = f"{BASE}/{row['id']}/receipts"
    def upload(content=b'%PDF-1.4 test receipt',mime='application/pdf',version=None,headers=None):
        return http.post(path,headers=headers or staff,data={'version':version or row['version']},files={'file':('../../ticket.pdf',content,mime)})
    assert upload(b'not a PDF').status_code == 422
    assert upload(mime='text/html').status_code == 415
    assert upload(b'%PDF-'+b'x'*(3*1024*1024)).status_code == 413
    assert upload(headers=other).status_code == 404
    response=upload();assert response.status_code == 201,response.text
    saved=response.json();assert saved['receipts'][0]['filename'] == 'ticket.pdf'
    assert 'storage_path' not in str(saved['receipts']) and len(uploaded) == 1
    assert upload(version=saved['version']).status_code == 409
    sign=f"{BASE}/{row['id']}/receipts/{saved['receipts'][0]['id']}/sign"
    assert http.get(sign,headers=other).status_code == 404
    assert http.get(sign,headers=staff).json()['expires_in'] == 60
    submitted=action(http,saved,staff,'submit')
    assert upload(version=submitted['version']).status_code == 409


def test_storage_failure_does_not_mutate_claim(travel_client,monkeypatch):
    http,sessions,actor = travel_client;staff,_ = actor('OPERATIONS');row=create(http,staff)
    def fail(*args):raise HTTPException(503,'Storage unavailable')
    monkeypatch.setattr(travel_storage,'upload',fail)
    response=http.post(f"{BASE}/{row['id']}/receipts",headers=staff,data={'version':1},files={'file':('ticket.pdf',b'%PDF-test','application/pdf')})
    assert response.status_code == 503
    with sessions() as db:
        assert db.get(TravelExpenseClaim,row['id']).version == 1
        assert db.query(TravelExpenseReceipt).count() == 0


def test_postgres_payment_posts_once_and_browser_database_access_is_denied(postgres_workflow):
    http,sessions,engine,day,_,owner_id,hr_id,*_ = postgres_workflow
    def login(identifier):
        response=http.post('/api/v1/auth/login',json={'login_id':identifier,'password':'local-test-password'})
        assert response.status_code == 200,response.text
        return {'Authorization':'Bearer '+response.json()['access_token']}
    owner,hr=login('TEST-OWNER'),login('TEST-HR')
    row=action(http,create(http,owner),owner,'submit')
    row=action(http,row,hr,'decision',decision='APPROVE')
    action(http,row,owner,'pay',403,payment_date=day.isoformat(),payment_reference='SELF-PAY')
    with sessions() as db:
        template=db.get(User,owner_id)
        db.add(User(login_id='TEST-ACCOUNTS',email='account@example.invalid',full_name='Test accounts',role=UserRole.ACCOUNTS,
                    hashed_password=template.hashed_password,is_active=True,is_superuser=False));db.commit()
    accounts=login('TEST-ACCOUNTS')
    action(http,row,accounts,'pay',422,payment_date=(day-timedelta(days=1)).isoformat(),payment_reference='EARLY')
    def pay_once():
        return http.post(f"{BASE}/{row['id']}/pay",headers=accounts,json={'version':row['version'],'payment_date':day.isoformat(),'payment_reference':'BANK-TEST-001'})
    with ThreadPoolExecutor(max_workers=2) as executor:
        results=list(executor.map(lambda _:pay_once(),range(2)))
    assert sorted(result.status_code for result in results)==[200,409], [r.text for r in results]
    paid=next(result.json() for result in results if result.status_code==200)
    assert paid['status']=='PAID' and paid['expense_id'] and paid['total_amount']=='250.25'
    action(http,row,accounts,'pay',409,payment_date=day.isoformat(),payment_reference='BANK-TEST-001')
    action(http,paid,accounts,'pay',409,payment_date=day.isoformat(),payment_reference='BANK-TEST-001')
    other=action(http,create(http,hr),hr,'submit')
    other=action(http,other,owner,'decision',decision='APPROVE')
    paid_other=action(http,other,owner,'pay',payment_date=day.isoformat(),payment_reference='MANAGEMENT-001')
    assert paid_other['paid_by']==owner_id
    with sessions() as db:
        assert db.execute(text("select count(*) from expenses where category='TRAVEL'")).scalar_one()==2
        assert db.execute(text("select sum(amount) from expenses where category='TRAVEL'")).scalar_one()==Decimal('500.50')
        assert db.execute(text("select count(*) from travel_expense_history where action='PAY'")).scalar_one()==2
        for role in ['anon','authenticated']:
            for table in ['travel_expense_claims','travel_expense_receipts','travel_expense_history']:
                assert not db.execute(text('select has_table_privilege(:role,:table,\'select\')'),{'role':role,'table':table}).scalar_one()


def test_receipt_service_refuses_public_bucket(monkeypatch):
    calls=[]
    def public_bucket(method,path,*args):
        calls.append((method,path));return {'public':True}
    monkeypatch.setattr(travel_storage,'request',public_bucket)
    with pytest.raises(HTTPException) as error:
        travel_storage.upload('1/example.pdf',b'%PDF-test','application/pdf')
    assert error.value.status_code==503
    assert calls==[('GET','bucket/travel-expense-receipts')]
