"""Retry safety on disposable PostgreSQL: no live employee or staff identity used."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import text
from test_postgres_workflow import postgres_workflow
from app.main import app
from app.models.internal_staff import StaffCodeCounter, StaffApprovalSettings
from app.api.v1.endpoints import users

EMPLOYEE="/api/v1/erp/employees/workflow/intimations"
STAFF="/api/v1/erp/internal-staff"

def login(http, login_id="TEST-HR"):
    result=http.post("/api/v1/auth/login",json={"login_id":login_id,"password":"local-test-password"})
    assert result.status_code==200,result.text
    return {"Authorization":"Bearer "+result.json()["access_token"]}

def intake(client_id, number="0"):
    return {"name":"QA retry worker","father_name":"QA parent","aadhaar_no":"234567890124",
            "phone":"987654321"+number,"client_id":client_id,"branch":"BR-1"}

def staff_body(number="0"):
    return {"profile":{"name":"QA office worker","phone":"912345678"+number,
             "email":"qa-office-"+number+"@example.in","department":"Operations","designation":"Manager"},
            "account":{"role":"OPERATIONS","temporary_password":"temporary-password-only-for-fixtures",
                       "permissions":{"employees.view":True}}}

def staff_setup(sessions,monkeypatch):
    monkeypatch.setattr(users,"provision_supabase_password_user",lambda **kwargs:{"id":"test-only"})
    with sessions() as db:
        if db.get(StaffCodeCounter,1) is None: db.add(StaffCodeCounter(id=1,next_number=10))
        if db.get(StaffApprovalSettings,1) is None: db.add(StaffApprovalSettings(id=1,version=1))
        db.commit()

def test_employee_intimation_lost_response_retry_returns_same_record(postgres_workflow):
    http,sessions,engine,today,start,owner_id,hr_id,client_id,site_id,objects=postgres_workflow
    headers={**login(http),"Idempotency-Key":"QA-EMP-LOST-ACK-0001"}
    data=intake(client_id)
    first=http.post(EMPLOYEE,headers=headers,json=data)
    assert first.status_code==201,first.text
    second=http.post(EMPLOYEE,headers=headers,json=data)
    assert second.status_code==201,second.text
    assert second.json()==first.json()
    with sessions() as db:
        assert db.execute(text("select count(*) from employees")).scalar_one()==1
        assert db.execute(text("select count(*) from employee_intimations")).scalar_one()==1
        assert db.execute(text("select count(*) from api_idempotency_requests")).scalar_one()==1

def test_employee_intimation_conflicting_reuse_is_409(postgres_workflow):
    http,sessions,engine,today,start,owner_id,hr_id,client_id,site_id,objects=postgres_workflow
    headers={**login(http),"Idempotency-Key":"QA-EMP-CONFLICT-0001"}
    good=http.post(EMPLOYEE,headers=headers,json=intake(client_id))
    assert good.status_code==201,good.text
    bad=http.post(EMPLOYEE,headers=headers,json=intake(client_id,"1"))
    assert bad.status_code==409,bad.text
    with sessions() as db:
        assert db.execute(text("select count(*) from employees")).scalar_one()==1

def test_employee_intimation_rejects_invalid_header_and_legacy_duplicate(postgres_workflow):
    http,sessions,engine,today,start,owner_id,hr_id,client_id,site_id,objects=postgres_workflow
    headers=login(http)
    bad=http.post(EMPLOYEE,headers={**headers,"Idempotency-Key":"x"},json=intake(client_id))
    assert bad.status_code==422,bad.text
    first=http.post(EMPLOYEE,headers=headers,json=intake(client_id))
    assert first.status_code==201,first.text
    second=http.post(EMPLOYEE,headers=headers,json=intake(client_id))
    assert second.status_code==409,second.text
    with sessions() as db:
        assert db.execute(text("select count(*) from employees")).scalar_one()==1

def test_concurrent_employee_create_single_record(postgres_workflow):
    http,sessions,engine,today,start,owner_id,hr_id,client_id,site_id,objects=postgres_workflow
    headers={**login(http),"Idempotency-Key":"QA-EMP-CONCURRENT-0001"}
    barrier=Barrier(2)
    def create():
        barrier.wait(8)
        with TestClient(app) as c:
            r=c.post(EMPLOYEE,headers=headers,json=intake(client_id))
            return r.status_code,r.json()
    with ThreadPoolExecutor(max_workers=2) as executor:
        results=list(executor.map(lambda _:create(), range(2)))
    assert all(code==201 for code,_ in results),results
    assert results[0][1]==results[1][1]
    with sessions() as db:
        assert db.execute(text("select count(*) from employees")).scalar_one()==1

def test_staff_lost_response_retry_no_second_login_or_code(postgres_workflow,monkeypatch):
    http,sessions,engine,today,start,owner_id,hr_id,client_id,site_id,objects=postgres_workflow
    staff_setup(sessions,monkeypatch)
    headers={**login(http,"TEST-OWNER"),"Idempotency-Key":"QA-STAFF-LOST-ACK-0001"}
    data=staff_body()
    one=http.post(STAFF,headers=headers,json=data)
    assert one.status_code==201,one.text
    two=http.post(STAFF,headers=headers,json=data)
    assert two.status_code==201,two.text
    assert one.json()==two.json()
    with sessions() as db:
        assert db.execute(text("select count(*) from internal_staff")).scalar_one()==1
        assert db.execute(text("select count(*) from users")).scalar_one()==3
        assert db.execute(text("select count(*) from internal_staff_history")).scalar_one()==1
        assert db.get(StaffCodeCounter,1).next_number==11

def test_staff_retry_different_payload_is_blocked(postgres_workflow,monkeypatch):
    http,sessions,engine,today,start,owner_id,hr_id,client_id,site_id,objects=postgres_workflow
    staff_setup(sessions,monkeypatch)
    headers={**login(http,"TEST-OWNER"),"Idempotency-Key":"QA-STAFF-REUSE-0001"}
    one=http.post(STAFF,headers=headers,json=staff_body())
    assert one.status_code==201,one.text
    changed=staff_body()
    changed["account"]["temporary_password"]="different-temporary-fixture-password"
    two=http.post(STAFF,headers=headers,json=changed)
    assert two.status_code==409,two.text
    with sessions() as db:
        assert db.execute(text("select count(*) from internal_staff")).scalar_one()==1
        assert db.execute(text("select count(*) from users")).scalar_one()==3

def test_staff_concurrent_creation_replayed_once(postgres_workflow,monkeypatch):
    http,sessions,engine,today,start,owner_id,hr_id,client_id,site_id,objects=postgres_workflow
    staff_setup(sessions,monkeypatch)
    headers={**login(http,"TEST-OWNER"),"Idempotency-Key":"QA-STAFF-CONCURRENT-0001"}
    barrier=Barrier(2)
    def issue():
        barrier.wait(8)
        with TestClient(app) as c:
            response=c.post(STAFF,headers=headers,json=staff_body())
            return response.status_code,response.json()
    with ThreadPoolExecutor(max_workers=2) as executor:
        results=list(executor.map(lambda _:issue(),range(2)))
    assert all(code==201 for code,_ in results),results
    assert results[0][1]==results[1][1]
    with sessions() as db:
        assert db.execute(text("select count(*) from internal_staff")).scalar_one()==1
        assert db.execute(text("select count(*) from users")).scalar_one()==3

def test_employee_approval_decision_replay_no_second_audit(postgres_workflow):
    from test_postgres_workflow import test_bootstrap_and_employee_to_invoice as seed_flow
    import json
    seed_flow(postgres_workflow)
    http,sessions,engine,today,start,owner_id,hr_id,client_id,site_id,objects=postgres_workflow
    with sessions() as db:
        eid=str(db.execute(text("select id from employees limit 1")).scalar_one())
        category=db.execute(text("select id from employee_approval_categories order by id limit 1")).scalar_one()
        req_id=db.execute(text("""insert into employee_approval_requests
            (employee_id,category_id,assigned_to,submitted_by,status,workflow_snapshot,step_index)
            values (cast(:eid as uuid),:cat,:owner,:hr,'PENDING',cast(:snap as jsonb),0) returning id"""),
            {"eid":eid,"cat":category,"owner":owner_id,"hr":hr_id,
             "snap":json.dumps([{"category_id":category,"assigned_to":owner_id}])}).scalar_one()
        db.commit()
    headers={**login(http,"TEST-OWNER"),"Idempotency-Key":"QA-APPROVAL-ACK-REPLAY-0001"}
    url="/api/v1/erp/employees/workflow/approvals/"+str(req_id)+"/decision"
    first=http.post(url,headers=headers,json={"decision":"REJECT","remarks":"Verification review"})
    assert first.status_code==200,first.text
    second=http.post(url,headers=headers,json={"decision":"REJECT","remarks":"Verification review"})
    assert second.status_code==200,second.text
    assert first.json()==second.json()
    with sessions() as db:
        assert db.execute(text("select count(*) from employee_approval_requests where id=:id and status='REJECTED'"),{"id":str(req_id)}).scalar_one()==1
        assert db.execute(text("select count(*) from api_idempotency_requests where operation='employee.approval.decision'")).scalar_one()==1


def test_travel_payment_replays_exactly_once(postgres_workflow):
    from test_travel_expenses import create, action, BASE
    from app.models.user import User
    from app.models.enums import UserRole
    http,sessions,engine,today,start,owner_id,hr_id,client_id,site_id,objects=postgres_workflow
    owner=login(http,"TEST-OWNER")
    hr=login(http,"TEST-HR")
    row=action(http,create(http,owner),owner,"submit")
    row=action(http,row,hr,"decision",decision="APPROVE")
    with sessions() as db:
        template=db.get(User,owner_id)
        db.add(User(login_id="TEST-ACCOUNTS",email="account@example.invalid",full_name="Test accounts",
                    role=UserRole.ACCOUNTS,hashed_password=template.hashed_password,is_active=True,is_superuser=False))
        db.commit()
    accounts={**login(http,"TEST-ACCOUNTS"),"Idempotency-Key":"QA-TRAVEL-PAY-ACK-REPLAY-0001"}
    payload={"version":row["version"],"payment_date":today.isoformat(),"payment_reference":"BANK-QA-001"}
    url=f"{BASE}/{row['id']}/pay"
    first=http.post(url,headers=accounts,json=payload)
    assert first.status_code==200,first.text
    second=http.post(url,headers=accounts,json=payload)
    assert second.status_code==200,second.text
    assert second.json()==first.json()
    with sessions() as db:
        assert db.execute(text("select count(*) from expenses where category='TRAVEL'")).scalar_one()==1
        assert db.execute(text("select count(*) from api_idempotency_requests where operation='travel.reimbursement.pay'")).scalar_one()==1
    changed=http.post(url,headers=accounts,json={**payload,"payment_reference":"BANK-QA-002"})
    assert changed.status_code==409,changed.text

def test_staff_provisioning_error_rolls_back_idempotency_and_retries(postgres_workflow,monkeypatch):
    from fastapi import HTTPException
    http,sessions,engine,today,start,owner_id,hr_id,client_id,site_id,objects=postgres_workflow
    staff_setup(sessions,monkeypatch)
    header={**login(http,"TEST-OWNER"),"Idempotency-Key":"QA-STAFF-OUTAGE-RETRY-0001"}
    def outage(**kwargs):
        raise HTTPException(502,"QA simulated auth outage")
    monkeypatch.setattr(users,"provision_supabase_password_user",outage)
    failed=http.post(STAFF,headers=header,json=staff_body())
    assert failed.status_code==502,failed.text
    with sessions() as db:
        assert db.execute(text("select count(*) from internal_staff")).scalar_one()==0
        assert db.execute(text("select count(*) from api_idempotency_requests")).scalar_one()==0
        assert db.get(StaffCodeCounter,1).next_number==10
    monkeypatch.setattr(users,"provision_supabase_password_user",lambda **kwargs:{"id":"test-only"})
    recovered=http.post(STAFF,headers=header,json=staff_body())
    assert recovered.status_code==201,recovered.text
    repeated=http.post(STAFF,headers=header,json=staff_body())
    assert repeated.status_code==201 and repeated.json()==recovered.json()
    with sessions() as db:
        assert db.execute(text("select count(*) from internal_staff")).scalar_one()==1
        assert db.get(StaffCodeCounter,1).next_number==11

def test_idempotency_ledger_cannot_be_queried_by_public_db_role(postgres_workflow):
    http,sessions,engine,today,start,owner_id,hr_id,client_id,site_id,objects=postgres_workflow
    with engine.connect() as db:
        rls=db.execute(text("select relrowsecurity from pg_class where oid='public.api_idempotency_requests'::regclass")).scalar_one()
        can_select=db.execute(text("select has_table_privilege('anon','public.api_idempotency_requests','SELECT')")).scalar_one()
        can_insert=db.execute(text("select has_table_privilege('anon','public.api_idempotency_requests','INSERT')")).scalar_one()
        assert rls and not can_select and not can_insert
