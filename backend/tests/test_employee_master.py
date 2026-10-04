"""Exercise joining transitions against an isolated database, never production records."""
import io,json,re,sqlite3
from datetime import date,timedelta
from types import SimpleNamespace
from uuid import uuid4
from zipfile import ZipFile
import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from starlette.requests import Request
from app.api.deps import _request_permission
from app.api.v1.endpoints import employee_workflow as workflow,employees
from app.models.company import CompanySettings
from app.models.user import User
from app.services import employee_workflow as rules
from app.services.employee_reports import export_report,safe_cell

OWNER=SimpleNamespace(id=1,role=SimpleNamespace(value='OWNER'),is_active=True)
HR=SimpleNamespace(id=2,role=SimpleNamespace(value='HR'),is_active=True)
OTHER=SimpleNamespace(id=3,role=SimpleNamespace(value='ADMIN'),is_active=True)

class Result:
    def __init__(self,rows): self.rows=rows
    def mappings(self): return self
    def all(self): return self.rows
    def first(self): return self.rows[0] if self.rows else None
    def one(self): assert len(self.rows)==1;return self.rows[0]
    def __iter__(self): return iter(self.rows)

class Row(dict):
    def __getitem__(self,key): return list(self.values())[key] if isinstance(key,int) else super().__getitem__(key)

class Database:
    """Adapt only dialect syntax; execute real DML/unique constraints in SQLite."""
    def __init__(self):
        self.conn=sqlite3.connect(':memory:');self.conn.row_factory=sqlite3.Row
        self.counter=69
        self.conn.create_function('uuid',0,lambda:str(uuid4()))
        self.conn.create_function('employee_code',0,self.code)
        self.conn.create_function('intimation_code',0,lambda:'INT-DAS-'+uuid4().hex[:10])
        self.conn.create_function('now',0,lambda:date.today().isoformat())
        basic=','.join(k+(' integer' if k in {'client_id','site_id'} else ' text') for k in sorted(rules.BASIC))
        self.conn.executescript(f"""
          create table employees(id text primary key default(uuid()),employee_code text unique default(employee_code()),{basic},intimation_id text unique,status text,profile text default '{{}}',version integer default 1,created_at text default(now()),updated_at text default(now()),status_reason text,unique(phone),unique(aadhaar_no));
          create table employee_intimations(id text primary key default(uuid()),intimation_id text default(intimation_code()),name text,father_name text,aadhaar_no text,phone text,client_id integer,branch text,created_by integer,status text default 'INTIMATED',created_at text default(now()),updated_at text default(now()));
          create table employee_joining_drafts(id text default(uuid()),intimation_id text,employee_id text unique,status text default 'DRAFT',created_by integer,last_saved_at text default(now()),updated_at text default(now()));
          create table employee_bank_accounts(id text default(uuid()),employee_id text unique,account_number text,bank_name text,branch text,ifsc_code text,ifsc_verified boolean,updated_at text);
          create table employee_approval_requests(id text default(uuid()),employee_id text,category_id integer,assigned_to integer,submitted_by integer,status text,workflow_snapshot text,step_index integer,remarks text,decided_by integer,submitted_at text default(now()),decided_at text);
          create unique index one_pending on employee_approval_requests(employee_id) where status='PENDING';
          create table employee_approval_categories(id integer primary key,category_name text,task_type text,is_active boolean,approver_user_id integer,is_final_approver boolean,sequence_order integer,updated_at text);
          create table employee_history(id integer primary key,employee_id text,changed_by integer,action text,version integer,details text,created_at text default(now()));
          create table clients(id integer primary key,is_active boolean,company_name text);
          create table sites(id integer primary key,is_active boolean,client_id integer,branch text,site_name text);
          create table ifsc_master(ifsc_code text,bank_name text,branch_name text,approved boolean);
          create table employee_documents(id text default(uuid()),employee_id text,document_type text,storage_path text,sha256 text,verification_status text,issue_date text,expiry_date text,verified_at text default(now()),created_at text default(now()));
          create table guard_profiles(id integer primary key,employee_id text unique,badge_number text,daily_rate numeric,status text,joining_date text,emergency_contact text);
          create table staff_profiles(employee_id text unique,staff_code text,intimation_id text,vertical text,category text,status text,is_bench_locked boolean,aadhaar_number text,pan_number text,bank_account_no text,bank_name text,bank_ifsc text,nominee_name text,nominee_relation text,nominee_aadhaar text,arms_license_no text,arms_caliber text,arms_expiry_date text,gun_license_expiry text,ammunition_count integer,uniform_total_cost numeric,uniform_monthly_emi numeric,uniform_balance_due numeric,police_verification_expiry text,medical_fitness_expiry text,bench_lock_reason text,updated_at text);
          insert into clients values(1,1,'Local test client');insert into sites values(1,1,1,'BR-1','Local test site');
          insert into ifsc_master values('TEST0000001','Test Bank','Test Branch',1);
          insert into employee_approval_categories values(1,'Owner final','EMPLOYEE_JOINING',1,1,1,1,null);
        """)
        self.conn.commit()
    def code(self): self.counter+=1;return f'E-DAS-{self.counter:04d}'
    def get(self,model,id):
        if model is CompanySettings:return SimpleNamespace(profile={'branches':[{'code':'BR-1','name':'Local test branch'}]})
        if model is User:return {1:OWNER,2:HR,3:OTHER}.get(id)
    def execute(self,sql,params=None):
        sql=str(sql).replace(' for update','').replace('public.','')
        sql=re.sub(r'cast\((:[a-z_]+) as (jsonb|guard_status_enum)\)',r'\1',sql)
        sql=sql.replace('select distinct on (document_type)','select')
        try: cursor=self.conn.execute(sql,{k:(v.isoformat() if isinstance(v,date) else v) for k,v in (params or {}).items()})
        except sqlite3.IntegrityError as e: raise IntegrityError(sql,params,e)
        rows=[]
        if cursor.description:
            for record in cursor.fetchall():
                row=Row(record)
                for k in {'profile','workflow_snapshot','details'}&row.keys():row[k]=json.loads(row[k])
                for k in {'issue_date','expiry_date'}&row.keys():row[k]=date.fromisoformat(row[k]) if row[k] else None
                rows.append(row)
        return Result(rows)
    def commit(self):self.conn.commit()
    def rollback(self):self.conn.rollback()

@pytest.fixture
def db(monkeypatch):
    monkeypatch.setattr(workflow,'has_permission',lambda *args:True)
    return Database()


def intake(db,user=HR):return workflow.create_intimation({'name':'Local test worker','father_name':'Local father','aadhaar_no':'234567890124','phone':'9876543210','client_id':1,'branch':'BR-1'},db,user)


def complete(db,record):
    p={'dob':'1990-01-01','gender':'MALE','designation':'Security guard','site_id':1,'joining_date':date.today().isoformat(),'category':'GUARD','vertical':'SECURITY','pan_no':'ABCDE1234F','permanent_address':'Test address','present_address':'Test address','emergency_contact':'9876543211','marital_status':'SINGLE','bank_account_no':'1234567890','bank_ifsc':'TEST0000001','bank_name':'Test Bank','bank_branch':'Test Branch','nominee_name':'Test nominee','nominee_relation':'Father'}
    return workflow.save_joining(record['id'],{'version':record['version'],'profile':p},db,HR)


def add_docs(db,eid,status='VERIFIED'):
    for kind in rules.DOCUMENTS:
        expiry=(date.today()+timedelta(days=100)).isoformat() if kind in rules.CRITICAL else None
        db.execute('insert into employee_documents(employee_id,document_type,storage_path,sha256,verification_status,expiry_date) values (:id,:type,:path,:sha,:status,:expiry)',{'id':eid,'type':kind,'path':'private/file','sha':'a'*64,'status':status,'expiry':expiry})
    db.commit()


def test_intimation_issues_permanent_code_in_joining_bucket(db):
    record=intake(db);assert record['employee_code']=='E-DAS-0070';assert record['status']=='DRAFT';assert record['joining_status']=='DRAFT'
    iid=db.execute('select id from employee_intimations').one()['id']
    assert workflow.resume_intimation(iid,db,HR)['id']==record['id']
    assert not db.execute('select * from guard_profiles').all()


def test_duplicate_intimation_is_atomic(db):
    intake(db)
    with pytest.raises(HTTPException) as error:intake(db)
    assert error.value.status_code==409
    assert len(db.execute('select * from employees').all())==1
    assert len(db.execute('select * from employee_intimations').all())==1


def test_partial_draft_survives_and_requires_current_version(db):
    r=intake(db);saved=workflow.save_joining(r['id'],{'version':1,'profile':{'bank_ifsc':'TEST0000001'}},db,HR)
    assert saved['profile']['bank_ifsc']=='TEST0000001';assert saved['version']==2
    with pytest.raises(HTTPException) as error:workflow.save_joining(r['id'],{'version':1,'profile':{'notes':'stale'}},db,HR)
    assert error.value.status_code==409


def test_staff_submission_locks_file_and_requires_actual_assignment(db):
    r=complete(db,intake(db));add_docs(db,r['id'])
    req=workflow.submit_joining(r['id'],{'version':r['version']},db,HR)
    assert req['assigned_to']==OWNER.id
    with pytest.raises(HTTPException) as error:workflow.decide(req['id'],{'decision':'APPROVE'},db,OTHER)
    assert error.value.status_code==403
    with pytest.raises(HTTPException):workflow.save_joining(r['id'],{'version':r['version']+1,'profile':{'notes':'bypass'}},db,HR)
    assert rules.employee(db,r['id'])['status']=='PENDING_APPROVAL'


def test_owner_direct_submission_activates_without_portal_account(db):
    r=complete(db,intake(db));add_docs(db,r['id'])
    assert workflow.submit_joining(r['id'],{'version':r['version']},db,OWNER)['final']
    assert rules.employee(db,r['id'])['status']=='ACTIVE'
    assert db.execute('select * from guard_profiles').one()['badge_number']=='E-DAS-0070'
    assert db.execute('select * from staff_profiles').one()['bank_ifsc']=='TEST0000001'


def test_return_requires_remarks_and_resubmits_same_id(db):
    r=complete(db,intake(db));add_docs(db,r['id']);req=workflow.submit_joining(r['id'],{'version':r['version']},db,HR)
    with pytest.raises(HTTPException):workflow.decide(req['id'],{'decision':'REJECT'},db,OWNER)
    workflow.decide(req['id'],{'decision':'REJECT','remarks':'Correct the address'},db,OWNER)
    returned=workflow.get_joining(r['id'],db,HR)
    saved=workflow.save_joining(r['id'],{'version':returned['version'],'profile':{'present_address':'Corrected address'}},db,HR)
    assert saved['employee_code']==r['employee_code']
    req2=workflow.submit_joining(r['id'],{'version':saved['version']},db,HR)
    assert req2['id']!=req['id'];assert req2['employee_id']==r['id']


def test_approval_snapshot_survives_configuration_change(db):
    r=complete(db,intake(db));add_docs(db,r['id']);req=workflow.submit_joining(r['id'],{'version':r['version']},db,HR)
    db.execute('update employee_approval_categories set approver_user_id=3,is_final_approver=false');db.commit()
    assert workflow.decide(req['id'],{'decision':'APPROVE'},db,OWNER)['final']
    with pytest.raises(HTTPException):workflow.decide(req['id'],{'decision':'APPROVE'},db,OWNER)


def test_unverified_documents_block_owner_activation_and_final_approval(db):
    r=complete(db,intake(db));add_docs(db,r['id'],'PENDING_REVIEW')
    with pytest.raises(HTTPException):workflow.submit_joining(r['id'],{'version':r['version']},db,OWNER)
    req=workflow.submit_joining(r['id'],{'version':r['version']},db,HR)
    with pytest.raises(HTTPException):workflow.decide(req['id'],{'decision':'APPROVE'},db,OWNER)
    assert rules.employee(db,r['id'])['status']=='PENDING_APPROVAL'


def test_approved_ifsc_database_cannot_be_spoofed(db):
    r=complete(db,intake(db));add_docs(db,r['id']);db.execute('update ifsc_master set approved=false');db.commit()
    with pytest.raises(HTTPException) as error:workflow.submit_joining(r['id'],{'version':r['version']},db,OWNER)
    assert 'approved IFSC' in str(error.value.detail)
    with pytest.raises(HTTPException):rules.clean_profile({'ifsc_verified':True})


def test_expired_compliance_benches_approved_employee_only(db):
    r=complete(db,intake(db));add_docs(db,r['id']);workflow.submit_joining(r['id'],{'version':r['version']},db,OWNER)
    db.execute("update employee_documents set expiry_date=:date where document_type='MEDICAL_FITNESS'",{'date':(date.today()-timedelta(days=1)).isoformat()});db.commit()
    result=rules.refresh_compliance(db,r['id']);assert result['locked'];assert rules.employee(db,r['id'])['status']=='BENCH'


@pytest.mark.parametrize('value',['123456789012','234567890123','abcdefgh1234','000000000000'])
def test_invalid_aadhaar_rejected(value):assert not rules.aadhaar_valid(value)


@pytest.mark.parametrize('payload',[{'bank_ifsc':'fake'},{'phone':'1234567890'},{'dob':'2099-01-01'},{'uniform_total_cost':'NaN'},{'ammunition_count':-1},{'nominee_percentage':101},{'employee_code':'E-DAS-0099'}])
def test_invalid_or_immutable_fields_rejected(payload):
    with pytest.raises(HTTPException):rules.clean_profile(payload)


@pytest.mark.parametrize('suffix,method,permission',[('/workflow/joining/id/submit','POST','employees.edit'),('/workflow/approvals/id/decision','POST','employees.approve'),('/id/documents/id/verify','PATCH','employees.approve'),('/id/documents/id/sign','POST','employees.view'),('/reports/export','GET','employees.export')])
def test_permission_routing(suffix,method,permission):
    req=Request({'type':'http','method':method,'path':'/api/v1/erp/employees'+suffix,'headers':[]})
    assert _request_permission(req)==permission


def test_exports_mask_identity_and_neutralize_formulas():
    rows=[{'employee_code':'E-DAS-0070','name':'=HYPERLINK("bad")','aadhaar_no':'234567890124','aadhaar_masked':'XXXXXXXX0124'}]
    response=export_report(rows,'master','xlsx')
    with ZipFile(io.BytesIO(response.body)) as z:
        xml=z.read('xl/worksheets/sheet1.xml').decode();assert '234567890124' not in xml;assert "'=HYPERLINK" in xml
    assert export_report(rows,'master','pdf').body.startswith(b'%PDF-')
    assert safe_cell(' +SUM(1,2)').startswith("'")


def test_draft_compliance_never_activates(db):
    r=intake(db);add_docs(db,r['id']);assert rules.refresh_compliance(db,r['id'])['locked'];assert rules.employee(db,r['id'])['status']=='DRAFT'


def test_manual_bench_and_inactive_status_are_preserved(db):
    r=complete(db,intake(db));add_docs(db,r['id']);workflow.submit_joining(r['id'],{'version':r['version']},db,OWNER)
    db.execute("update employees set status='BENCH',status_reason='Awaiting client allocation'");db.commit()
    rules.refresh_compliance(db,r['id']);assert rules.employee(db,r['id'])['status']=='BENCH'
    db.execute("update employees set status='INACTIVE'");db.commit()
    rules.refresh_compliance(db,r['id']);assert rules.employee(db,r['id'])['status']=='INACTIVE'


def test_multistep_chain_activates_only_at_final_step(db):
    db.execute('update employee_approval_categories set is_final_approver=false,approver_user_id=2')
    db.execute("insert into employee_approval_categories values(2,'Owner final','EMPLOYEE_JOINING',1,1,1,2,null)");db.commit()
    r=complete(db,intake(db));add_docs(db,r['id']);first=workflow.submit_joining(r['id'],{'version':r['version']},db,HR)
    result=workflow.decide(first['id'],{'decision':'APPROVE'},db,HR);assert not result['final']
    assert rules.employee(db,r['id'])['status']=='PENDING_APPROVAL';assert not db.execute('select * from guard_profiles').all()
    final=db.execute("select * from employee_approval_requests where status='PENDING'").one()
    assert workflow.decide(final['id'],{'decision':'APPROVE'},db,OWNER)['final']


def test_valid_adult_and_bank_information_still_requires_uploads(db):
    r=complete(db,intake(db))
    with pytest.raises(HTTPException) as error:workflow.submit_joining(r['id'],{'version':r['version']},db,HR)
    assert set(error.value.detail['missing_documents'])==rules.DOCUMENTS


def test_underage_and_expired_gun_licence_block_submission(db):
    r=complete(db,intake(db));add_docs(db,r['id'])
    p={'dob':(date.today()-timedelta(days=365*17)).isoformat(),'category':'GUNMAN','gun_license_no':'Local licence','gun_license_expiry':(date.today()-timedelta(days=1)).isoformat(),'arms_caliber':'12 bore','weapon_serial_no':'Local serial','arms_issuing_authority':'Local authority'}
    r=workflow.save_joining(r['id'],{'version':r['version'],'profile':p},db,HR)
    with pytest.raises(HTTPException) as error:workflow.submit_joining(r['id'],{'version':r['version']},db,HR)
    assert 'minimum age 18' in error.value.detail['missing_fields'];assert 'GUN_LICENSE' in error.value.detail['missing_documents']


def test_document_validity_requires_private_integrity_and_current_dates():
    valid={'document_type':'MEDICAL_FITNESS','storage_path':'private/file','sha256':'a'*64,'verification_status':'VERIFIED','expiry_date':date.today()+timedelta(days=1)}
    assert rules.doc_valid(valid,True)
    assert not rules.doc_valid({**valid,'storage_path':None},True)
    assert not rules.doc_valid({**valid,'expiry_date':date.today()-timedelta(days=1)},True)
    assert not rules.doc_valid({**valid,'verification_status':'REJECTED'},True)
    assert not rules.doc_valid({**valid,'expiry_date':None},True)


def test_operations_can_receive_employee_permissions_without_default_access():
    from app.api.permissions import permission_supported,role_allows
    assert permission_supported('OPERATIONS','employees.create')
    assert permission_supported('ACCOUNTS','employees.approve')
    assert not role_allows('OPERATIONS','employees.create')
    assert not permission_supported('STAFF','employees.view')
    assert not permission_supported('CLIENT','employees.view')
