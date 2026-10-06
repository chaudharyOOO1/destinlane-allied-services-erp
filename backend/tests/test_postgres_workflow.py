"""Real PostgreSQL bootstrap and HTTP workflow, in a disposable database.

Run with TEST_POSTGRES_ADMIN_URL pointing to a local role with CREATEDB.
The configured database is never modified; a unique test database is created
and removed. Private object storage is stubbed, not production Supabase.
"""
import os
import secrets
import subprocess
import sys
from datetime import datetime, time, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("SECRET_KEY", secrets.token_urlsafe(32))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app
from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import get_password_hash
from app.models.user import User
from app.models.client import Client
from app.models.site import Site
from app.models.enums import UserRole
from app.api.v1.endpoints import employee_documents
from app.services import attendance, employee_workflow, roster_deployment


@pytest.fixture
def postgres_workflow(monkeypatch):
    admin_url = os.environ.get("TEST_POSTGRES_ADMIN_URL")
    if not admin_url:
        pytest.skip("Set TEST_POSTGRES_ADMIN_URL to run disposable PostgreSQL integration tests")
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    name = "erp_test_" + uuid4().hex
    with admin.connect() as conn:
        conn.exec_driver_sql(f'CREATE DATABASE "{name}"')
    database_url = make_url(admin_url).set(database=name)
    engine = create_engine(database_url)
    backend = Path(__file__).resolve().parents[1]
    env = {**os.environ, "DATABASE_URL": database_url.render_as_string(hide_password=False)}
    try:
        for _ in range(2):
            result = subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                cwd=backend, env=env, capture_output=True, text=True,
            )
            assert result.returncode == 0, result.stderr
        sessions = sessionmaker(bind=engine)
        monkeypatch.setattr(settings, "ALLOW_LOCAL_PASSWORD_FALLBACK", True)
        monkeypatch.setattr(settings, "SUPABASE_URL", None)
        monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", None)
        # Use a deterministic business day and server clock; PostgreSQL remains real.
        today = attendance.business_date()
        start = datetime.combine(today, time(8), attendance.IST)
        monkeypatch.setattr(attendance, "now", lambda: start + timedelta(hours=10))
        monkeypatch.setattr(attendance, "business_date", lambda: today)
        monkeypatch.setattr(roster_deployment, "business_date", lambda: today)

        objects = {}
        def storage(method, path, body=None, content_type=None):
            assert method == "POST" and path.startswith("object/")
            objects[path] = body
            return 200, {}
        monkeypatch.setattr(employee_documents, "_storage_request", storage)

        def get_test_db():
            with sessions() as db:
                yield db
        app.dependency_overrides[get_db] = get_test_db
        with sessions() as db:
            owner = User(email="owner@example.test", login_id="TEST-OWNER", full_name="Test owner",
                         role=UserRole.OWNER, hashed_password=get_password_hash("local-test-password"),
                         is_active=True, is_superuser=True)
            hr = User(email="hr@example.test", login_id="TEST-HR", full_name="Test HR",
                      role=UserRole.HR, hashed_password=get_password_hash("local-test-password"),
                      is_active=True)
            db.add_all([owner, hr]); db.flush()
            owner_id, hr_id = owner.id, hr.id
            for permission in ("employees.view", "employees.create", "employees.edit"):
                db.execute(text("insert into user_permissions(user_id,permission_key,allowed) values(:user,:permission,true)"),
                           {"user": hr_id, "permission": permission})
            db.execute(text("update company_settings set profile=cast(:profile as jsonb) where id=1"),
                       {"profile": '{"legal_name":"Local test company","branches":[{"code":"BR-1","name":"Test branch"}]}'})
            client = Client(company_name="Local test client", client_code="C-DAS-0001", contact_person="Test contact",
                            contact_email="contact@example.test", contact_phone="9876543212", billing_address="Test address",
                            branch="BR-1", branch_region="DELHI_NCR", is_active=True)
            db.add(client); db.flush()
            site = Site(client_id=client.id, site_name="Local test site", site_code="SITE-DAS-0001",
                        address="Test address", city="Delhi", state="Delhi", postal_code="110001",
                        branch="BR-1", branch_region="DELHI_NCR", latitude=28.6, longitude=77.2,
                        shift_requirements={"general_shift_guards": 1}, is_active=True)
            db.add(site); db.flush()
            client_id, site_id = client.id, site.id
            db.execute(text("insert into ifsc_master(ifsc_code,bank_name,branch_name,approved) values('TEST0000001','Test Bank','Test Branch',true)"))
            db.execute(text("insert into employee_approval_categories(category_name,approver_user_id,is_final_approver) values('Owner final',:owner,true)"), {"owner": owner_id})
            db.execute(text("insert into site_rate_cards(site_id,vertical,category,daily_rate,hourly_rate,effective_from) values(:site,'SECURITY','GUARD',1000,125,:day)"), {"site": site_id, "day": today})
            db.commit()
        with TestClient(app) as http:
            yield http, sessions, engine, today, start, owner_id, hr_id, client_id, site_id, objects
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
        with admin.connect() as conn:
            conn.exec_driver_sql(f'DROP DATABASE "{name}" WITH (FORCE)')
        admin.dispose()


def test_bootstrap_and_employee_to_invoice(postgres_workflow):
    http, sessions, engine, today, start, owner_id, hr_id, client_id, site_id, objects = postgres_workflow
    inspector = inspect(engine)
    for table in Base.metadata.sorted_tables:
        assert set(table.columns.keys()) <= {c["name"] for c in inspector.get_columns(table.name)}, table.name
    with engine.connect() as conn:
        assert conn.execute(text("select version_num from alembic_version")).scalar_one() == "0007_compact_personnel_ids"
        assert conn.execute(text("select count(*) from employees")).scalar_one() == 0

    def login(login_id):
        response = http.post("/api/v1/auth/login", json={"login_id": login_id, "password": "local-test-password"})
        assert response.status_code == 200, response.text
        return {"Authorization": "Bearer " + response.json()["access_token"]}
    owner, hr = login("TEST-OWNER"), login("TEST-HR")
    def call(method, path, expected=200, **kwargs):
        response = http.request(method, "/api/v1" + path, headers=kwargs.pop("headers", owner), **kwargs)
        assert response.status_code == expected, f"{method} {path}: {response.text}"
        return response.json()

    record = call("POST", "/erp/employees/workflow/intimations", 201, headers=hr, json={
        "name": "Local test worker", "father_name": "Local father", "aadhaar_no": "234567890124",
        "phone": "9876543210", "client_id": client_id, "branch": "BR-1"})
    employee_id = record["id"]
    assert record["employee_code"] == "DASE0070"
    joining = f"/erp/employees/workflow/joining/{employee_id}"
    record = call("PATCH", joining, headers=hr, json={"version": record["version"], "profile": {
        "dob": "1990-01-01", "gender": "MALE", "designation": "Security guard", "site_id": site_id,
        "joining_date": today.isoformat(), "category": "GUARD", "vertical": "SECURITY", "pan_no": "ABCDE1234F",
        "permanent_address": "Test address", "present_address": "Test address", "emergency_contact": "9876543211",
        "marital_status": "SINGLE", "bank_account_no": "1234567890", "bank_ifsc": "TEST0000001",
        "bank_name": "Test Bank", "bank_branch": "Test Branch", "nominee_name": "Test nominee", "nominee_relation": "Father"}})
    for kind in sorted(employee_workflow.DOCUMENTS):
        form = {"document_type": kind, "issue_date": today.isoformat()}
        if kind in employee_workflow.CRITICAL:
            form["expiry_date"] = (today + timedelta(days=100)).isoformat()
        doc = call("POST", f"/erp/employees/{employee_id}/documents", 201, headers=hr,
                   data=form, files={"file": (kind + ".pdf", b"%PDF-1.4\nLocal integration proof " + kind.encode(), "application/pdf")})
        call("PATCH", f"/erp/employees/{employee_id}/documents/{doc['id']}/verify",
             json={"status": "VERIFIED", "notes": "Reviewed local fixture"})
    assert len(objects) == len(employee_workflow.DOCUMENTS)
    request = call("POST", joining + "/submit", headers=hr, json={"version": record["version"]})
    result = call("POST", f"/erp/employees/workflow/approvals/{request['id']}/decision", json={"decision": "APPROVE"})
    assert result["final"] is True
    with sessions() as db:
        guard_id = db.execute(text("select id from guard_profiles where employee_id=:id"), {"id": employee_id}).scalar_one()
        db.execute(text("update guard_profiles set daily_rate=800 where id=:id"), {"id": guard_id}); db.commit()
    roster = call("POST", "/erp/rosters", 201, json={"site_id": site_id, "guard_id": guard_id, "date": today.isoformat(), "shift_type": "GENERAL"})
    call("PUT", "/erp/attendance/rules", json={"site_id": site_id, "shift_type": "GENERAL", "start_time": "08:00:00", "duty_hours": 8, "reason": "Local test shift"})
    # Approved manual attendance uses the same payroll/billing gate as reviewed punches.
    request = call("POST", "/erp/attendance/corrections", json={"roster_id": roster["id"], "version": 0,
        "assigned_to": owner_id, "reason": "Local test missing punch", "status": "present",
        "check_in_time": start.isoformat(), "check_out_time": (start + timedelta(hours=10)).isoformat()})
    month = today.strftime("%Y-%m")
    assert call("POST", "/erp/billing/generate", json={"month": month, "client_id": client_id})["invoices_created"] == 0
    call("POST", f"/erp/attendance/corrections/{request['id']}/decision", json={"decision": "APPROVE", "reason": "Verified local times"})
    register = call("GET", "/erp/attendance")
    assert len(register) == 1 and register[0]["verification_status"] == "VERIFIED"
    assert register[0]["source"] == "MANUAL_CORRECTION" and not register[0]["is_geofence_verified"]
    assert float(register[0]["shift_hours"]) == 8 and float(register[0]["overtime_hours"]) == 2
    assert call("POST", "/erp/payroll/calculate", json={"month": month})["employees_processed"] == 1
    slips = call("GET", "/erp/payroll?month=" + month)
    assert len(slips) == 1 and slips[0]["employee_id"] == employee_id
    assert float(slips[0]["basic"]) == 800 and float(slips[0]["overtime_pay"]) == 300
    assert float(slips[0]["net_pay"]) == 1064.85
    pdf = http.get(f"/api/v1/erp/payroll/slips/{slips[0]['id']}/pdf", headers=owner)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")
    assert call("POST", "/erp/payroll/calculate", json={"month": month})["employees_processed"] == 1
    assert len(call("GET", "/erp/payroll?month=" + month)) == 1
    invoices = call("POST", "/erp/billing/generate", json={"month": month, "client_id": client_id})
    assert invoices["invoices_created"] == 1
    invoice = invoices["invoices"][0]
    assert float(invoice["subtotal"]) == 1375 and float(invoice["tax_amount"]) == 247.5
    assert float(invoice["total_amount"]) == 1622.5
    assert call("POST", "/erp/billing/generate", json={"month": month, "client_id": client_id})["invoices_created"] == 0
    for path in ["/erp/company", "/erp/internal-staff", "/erp/clients", "/erp/sites", "/erp/contracts",
                 "/erp/employees", "/erp/rosters", "/erp/attendance/options", "/erp/accounts", "/erp/summary", "/owner/executive-summary"]:
        call("GET", path)
    assert float(call("GET", "/owner/executive-summary")["kpis"]["payroll"]) == 1064.85
    assert len(call("GET", "/erp/rosters?status=COMPLETED")) == 1
    assert call("GET", "/erp/rosters?status=SCHEDULED") == []
    for table in ("employees", "employee_documents", "attendance", "salary_slips"):
        with engine.connect() as conn:
            assert conn.execute(text("select relrowsecurity from pg_class where oid=cast(:name as regclass)"), {"name": table}).scalar_one()
            for role in ("anon", "authenticated"):
                assert not conn.execute(text("select has_table_privilege(:role,:table,'SELECT')"), {"role": role, "table": table}).scalar_one()
    with sessions() as db:
        assert db.execute(text("select count(*) from employee_history")).scalar_one() >= 3
        assert db.execute(text("select count(*) from roster_history")).scalar_one() >= 1
        assert db.execute(text("select count(*) from attendance_history")).scalar_one() >= 2


def test_payroll_list_has_one_canonical_handler():
    routes = [route for route in app.routes if getattr(route, "path", None) == "/api/v1/erp/payroll"
              and "GET" in getattr(route, "methods", set())]
    assert len(routes) == 1
    assert routes[0].endpoint.__module__ == "app.api.v1.endpoints.payroll"


def test_documented_development_seed_is_repeatable(postgres_workflow):
    _, _, engine, *_ = postgres_workflow
    backend = Path(__file__).resolve().parents[1]
    env = {**os.environ, "DATABASE_URL": engine.url.render_as_string(hide_password=False)}
    counts = []
    for _ in range(2):
        result = subprocess.run([sys.executable, "scripts/seed_db.py"], cwd=backend,
                                env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        with engine.connect() as conn:
            counts.append(tuple(conn.execute(text(f"select count(*) from {table}")).scalar_one()
                                for table in ("users", "clients", "guard_profiles", "shift_rosters", "invoices")))
    assert counts[0] == counts[1]
    assert all(count > 0 for count in counts[0])


def test_staff_creation_first_login_and_working_permissions(postgres_workflow):
    http,sessions,engine,today,start,owner_id,hr_id,client_id,site_id,objects=postgres_workflow
    base='/api/v1/erp/internal-staff'
    def login(identifier,password):
        response=http.post('/api/v1/auth/login',json={'login_id':identifier,'password':password})
        assert response.status_code==200,response.text
        return {'Authorization':'Bearer '+response.json()['access_token']}
    hr=login('TEST-HR','local-test-password')
    payload={'profile':{'name':'Office operator','email':'operator@example.in','phone':'9876543220','department':'Operations','designation':'Coordinator','branch':'BR-1'},
             'account':{'role':'OPERATIONS','temporary_password':'temporary-local-password','permissions':{'employees.view':True,'employees.create':True,'staff.view':True}}}
    result=http.post(base,headers=hr,json=payload)
    assert result.status_code==201,result.text
    record=result.json();assert record['staff_code']=='DASS0010'
    assert record['account']['must_change_password']
    assert 'temporary-local-password' not in result.text
    temporary=login('DASS0010','temporary-local-password')
    assert http.get('/api/v1/erp/employees',headers=temporary).status_code==403
    changed=http.post('/api/v1/auth/change-password',headers=temporary,json={'current_password':'temporary-local-password','new_password':'personal-local-password'})
    assert changed.status_code==200,changed.text
    assert http.get('/api/v1/auth/me',headers=temporary).status_code==401
    operator=login('DASS0010','personal-local-password')
    rights=http.get(f"/api/v1/users/{record['user_id']}/permissions",headers=operator).json()['permissions']
    assert rights['employees.create'] and not rights['staff.create']
    assert http.post(base,headers=operator,json=payload).status_code==403
    employee=http.post('/api/v1/erp/employees/workflow/intimations',headers=operator,json={
        'name':'Worker created by office staff','father_name':'Test father','aadhaar_no':'234567890124',
        'phone':'9876543221','client_id':client_id,'branch':'BR-1'})
    assert employee.status_code==201,employee.text
    assert employee.json()['employee_code']=='DASE0070'
    access={'version':record['version'],'role':'OPERATIONS','is_active':True,'permissions':{'employees.create':False}}
    saved=http.put(base+f"/{record['id']}/login",headers=hr,json=access)
    assert saved.status_code==200,saved.text
    assert http.get('/api/v1/auth/me',headers=operator).status_code==401
    operator=login('DASS0010','personal-local-password')
    assert http.post('/api/v1/erp/employees/workflow/intimations',headers=operator,json={}).status_code==403
    disabled=http.post(base+f"/{record['id']}/status",headers=hr,json={'version':saved.json()['version'],'status':'INACTIVE','reason':'Leave'})
    assert disabled.status_code==200,disabled.text
    assert http.get('/api/v1/auth/me',headers=operator).status_code==401
    with sessions() as db:
        assert not db.get(User,record['user_id']).is_active
        assert db.execute(text('select next_number from internal_staff_code_counter')).scalar_one()==11
        with pytest.raises(Exception):
            db.execute(text('update internal_staff set staff_code=\'DASS9999\' where id=:id'),{'id':record['id']})
        db.rollback()
