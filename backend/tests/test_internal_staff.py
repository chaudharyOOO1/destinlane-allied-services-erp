import pytest
from sqlalchemy import text
from test_authentication import client
from app.models.internal_staff import StaffCodeCounter, StaffHistory, StaffApprovalSettings
from app.models.user import User
from app.models.enums import UserRole

BASE = '/api/v1/erp/internal-staff'
PROFILE = {'name':'Office test','phone':'9876543210','email':'office@example.in','department':'Operations','designation':'Manager'}
ACCOUNT = {'role':'OPERATIONS','temporary_password':'temporary-test-password','permissions':{'employees.view':True,'employees.create':True}}

@pytest.fixture
def staff_client(client,monkeypatch):
    from app.api.v1.endpoints import users
    http,sessions=client
    monkeypatch.setattr(users,'provision_supabase_password_user',lambda **kw:{'id':'test-only'})
    with sessions() as db:
        db.execute(text("ATTACH DATABASE ':memory:' AS public"))
        db.execute(text('CREATE TABLE public.user_permissions(user_id INTEGER,permission_key TEXT,allowed BOOLEAN, UNIQUE(user_id,permission_key))'))
        db.add(StaffCodeCounter(id=1,next_number=10));db.add(StaffApprovalSettings(id=1,version=1));db.commit()
    token=http.post('/api/v1/auth/login',json={'login_id':'ADMIN-001','password':'test-password-before'}).json()['access_token']
    return http,sessions,{'Authorization':'Bearer '+token}

def role(sessions,value):
    with sessions() as db:
        actor=db.query(User).filter_by(login_id='ADMIN-001').one();actor.role=value;actor.is_superuser=value==UserRole.OWNER;db.commit()

def create(http,headers,profile=None,account=None):
    return http.post(BASE,headers=headers,json={'profile':profile or PROFILE,'account':account or ACCOUNT})

def test_one_save_creates_staff_login_permissions_and_safe_audit(staff_client):
    http,sessions,headers=staff_client
    result=create(http,headers);assert result.status_code==201,result.text
    row=result.json();assert row['staff_code']=='DASS0010' and row['status']=='ACTIVE'
    assert row['account']['login_id']==row['staff_code'] and row['account']['must_change_password']
    assert 'temporary-test-password' not in result.text
    with sessions() as db:
        account=db.get(User,row['user_id']);assert account.hashed_password!='temporary-test-password'
        assert db.query(StaffHistory).count()==1
        assert 'temporary-test-password' not in str(db.query(StaffHistory).first().snapshot)
    assert http.get(BASE+'/code-check?code=DASS0010',headers=headers).json()['registered']
    assert not http.get(BASE+'/code-check?code=DASS0009',headers=headers).json()['valid_format']
    changed=http.put(BASE+f"/{row['id']}",headers=headers,json={'version':1,'profile':{**PROFILE,'name':'Updated name'}})
    assert changed.status_code==200 and changed.json()['version']==2
    with sessions() as db: assert db.get(User,row['user_id']).full_name=='Updated name'
    assert http.put(BASE+f"/{row['id']}",headers=headers,json={'version':1,'profile':PROFILE}).status_code==409
    assert http.post(BASE+f"/{row['id']}/login",headers=headers,json=ACCOUNT).status_code==409

@pytest.mark.parametrize('value',[UserRole.ADMIN,UserRole.SUPER_ADMIN,UserRole.STAFF,UserRole.CLIENT,UserRole.SUPERVISOR,UserRole.OPERATIONS,UserRole.ACCOUNTS])
def test_only_owner_and_hr_create_even_with_explicit_allow(staff_client,value):
    http,sessions,headers=staff_client;role(sessions,value)
    with sessions() as db:
        db.execute(text("insert into public.user_permissions values(1,'staff.create',true)"));db.commit()
    assert create(http,headers).status_code==403

def test_hr_creation_role_limits_and_access_changes(staff_client):
    http,sessions,headers=staff_client;role(sessions,UserRole.HR)
    assert create(http,headers,account={**ACCOUNT,'role':'ADMIN'}).status_code==403
    assert create(http,headers,account={**ACCOUNT,'permissions':{'staff.create':True}}).status_code==422
    result=create(http,headers);assert result.status_code==201,result.text
    row=result.json();assert row['staff_code']=='DASS0010'
    assert http.get(BASE+f"/{row['id']}",headers=headers).json()['permissions']['employees.create']
    result=http.put(BASE+f"/{row['id']}/login",headers=headers,json={'version':1,'role':'OPERATIONS','is_active':True,'permissions':{'employees.create':False}})
    assert result.status_code==200,result.text
    assert not result.json()['permissions']['employees.create']
    assert http.put(BASE+f"/{row['id']}/login",headers=headers,json={'version':2,'role':'OWNER','is_active':True}).status_code==403


def test_creation_failure_rolls_back_record_login_and_counter(staff_client,monkeypatch):
    from app.api.v1.endpoints import users
    from app.core.config import settings
    http,sessions,headers=staff_client
    monkeypatch.setattr(users,'provision_supabase_password_user',lambda **kw:None)
    monkeypatch.setattr(settings,'ALLOW_LOCAL_PASSWORD_FALLBACK',False)
    assert create(http,headers).status_code==502
    with sessions() as db:
        assert db.query(StaffCodeCounter).first().next_number==10
        assert db.query(StaffHistory).count()==0 and db.query(User).count()==1


def test_duplicate_phone_email_and_password_validation(staff_client):
    http,sessions,headers=staff_client;assert create(http,headers).status_code==201
    assert create(http,headers,profile={**PROFILE,'phone':'+91 98765 43210'}).status_code==409
    assert create(http,headers,profile={**PROFILE,'phone':'9876543211'}).status_code==409
    assert create(http,headers,account={**ACCOUNT,'temporary_password':'short'}).status_code==422
    assert http.post(BASE,headers=headers,json={'profile':PROFILE}).status_code==422
    with sessions() as db: assert db.query(StaffCodeCounter).first().next_number==11


def test_inactive_and_terminated_disable_login(staff_client):
    http,sessions,headers=staff_client;row=create(http,headers).json();path=BASE+f"/{row['id']}"
    assert http.post(path+'/status',headers=headers,json={'version':1,'status':'INACTIVE'}).status_code==422
    assert http.post(path+'/status',headers=headers,json={'version':1,'status':'INACTIVE','reason':'Leave'}).status_code==200
    with sessions() as db: assert not db.get(User,row['user_id']).is_active
    assert http.get(path,headers=headers).json()['permissions']['employees.create']
    assert http.post(path+'/status',headers=headers,json={'version':2,'status':'ACTIVE','reason':'Returned'}).status_code==200
    with sessions() as db: assert not db.get(User,row['user_id']).is_active
    assert http.put(path+'/login',headers=headers,json={'version':3,'role':'OPERATIONS','is_active':True}).status_code==200
    assert http.post(path+'/status',headers=headers,json={'version':4,'status':'TERMINATED','reason':'Exit'}).status_code==200
    assert http.put(path,headers=headers,json={'version':5,'profile':PROFILE}).status_code==409
    assert http.put(path+'/login',headers=headers,json={'version':5,'role':'OPERATIONS','is_active':True}).status_code==409

@pytest.mark.parametrize('key,value',[('phone','123'),('email','bad'),('dob','2099-01-01')])
def test_invalid_details_rejected(staff_client,key,value):
    http,_,headers=staff_client;assert create(http,headers,profile={**PROFILE,key:value}).status_code==422


def test_simple_details_no_joining_or_diligence_required(staff_client):
    http,_,headers=staff_client
    assert create(http,headers,profile={'name':'Simple staff','phone':'9876543210','email':'simple@example.in'}).status_code==201
    assert http.get(BASE).status_code==401


def test_existing_branch_assignment_only(staff_client):
    from app.models.company import CompanySettings
    http,sessions,headers=staff_client
    assert create(http,headers,profile={**PROFILE,'branch':'UNKNOWN'}).status_code==422
    with sessions() as db:
        db.add(CompanySettings(id=1,profile={'branches':[{'code':'DDN','name':'Dehradun','is_active':True},{'code':'OLD','name':'Old office','is_active':False}]}));db.commit()
    assert http.get(BASE+'/office-options',headers=headers).json()['branches']==[{'code':'DDN','name':'Dehradun'}]
    assert create(http,headers,profile={**PROFILE,'branch':'OLD'}).status_code==422
    assert create(http,headers,profile={**PROFILE,'branch':'DDN'}).status_code==201
