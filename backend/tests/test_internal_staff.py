import pytest
from sqlalchemy import text
from test_authentication import client
from app.models.internal_staff import InternalStaff, StaffCodeCounter, StaffHistory, StaffApprovalSettings
from app.models.user import User
from app.models.enums import UserRole
from app.schemas.internal_staff import StaffProfile

BASE = '/api/v1/erp/internal-staff'
PROFILE = {'name':'Office test','phone':'9876543210','department':'Management','designation':'MD','region':'ALL_REGIONS','management_level':'UPPER_MANAGEMENT','joining_date':'2026-01-01'}


@pytest.fixture
def staff_client(client):
    http,sessions=client
    with sessions() as db:
        db.execute(text("ATTACH DATABASE ':memory:' AS public"))
        db.execute(text('CREATE TABLE public.user_permissions(user_id INTEGER,permission_key TEXT,allowed BOOLEAN)'))
        db.add(StaffCodeCounter(id=1,next_number=10))
        db.add(StaffApprovalSettings(id=1,version=1))
        db.commit()
    token=http.post('/api/v1/auth/login',json={'login_id':'ADMIN-001','password':'test-password-before'}).json()['access_token']
    return http,sessions,{'Authorization':'Bearer '+token}


def role(sessions,value):
    with sessions() as db:
        user=db.query(User).first();user.role=value;user.is_superuser=value==UserRole.OWNER;db.commit()


def test_staff_codes_separate_drafts_edits_and_audit(staff_client):
    http,sessions,headers=staff_client
    one=http.post(BASE,headers=headers,json={'profile':PROFILE}).json()
    assert one['staff_code']=='S-DAS-0010' and one['status']=='DRAFT'
    two=http.post(BASE,headers=headers,json={'profile':{**PROFILE,'phone':'9876543211'},'submit':True}).json()
    assert two['staff_code']=='S-DAS-0011' and two['status']=='ACTIVE'
    updated=http.put(BASE+f"/{one['id']}",headers=headers,json={'version':1,'profile':{**PROFILE,'designation':'Managing Director'}})
    assert updated.status_code==200 and updated.json()['version']==2
    assert http.put(BASE+f"/{one['id']}",headers=headers,json={'version':1,'profile':PROFILE}).status_code==409
    assert http.put(BASE+f"/{one['id']}",headers=headers,json={'version':2,'profile':PROFILE,'staff_code':'S-DAS-9999'}).status_code==422
    assert http.get(BASE+'/code-check?code=S-DAS-0010',headers=headers).json()['registered']
    assert not http.get(BASE+'/code-check?code=S-DAS-0009',headers=headers).json()['valid_format']
    assert not http.get(BASE+'/code-check?code=S-DAS-0012',headers=headers).json()['registered']
    assert 'profile' not in http.get(BASE,headers=headers).json()[0]
    with sessions() as db:
        assert db.query(StaffHistory).count()==3
        assert db.query(StaffCodeCounter).first().next_number==12


def test_duplicate_normalized_phone_does_not_allocate_code(staff_client):
    http,sessions,headers=staff_client
    assert http.post(BASE,headers=headers,json={'profile':PROFILE}).status_code==201
    assert http.post(BASE,headers=headers,json={'profile':{**PROFILE,'phone':'+91 98765 43210'}}).status_code==409
    with sessions() as db: assert db.query(StaffCodeCounter).first().next_number==11


def test_approval_return_resubmit_and_status(staff_client):
    http,sessions,headers=staff_client
    role(sessions,UserRole.ADMIN)
    row=http.post(BASE,headers=headers,json={'profile':PROFILE,'submit':True}).json()
    assert row['status']=='PENDING'
    assert http.post(BASE+f"/{row['id']}/decision",headers=headers,json={'version':1}).status_code==403
    assert http.post(BASE+f"/{row['id']}/status",headers=headers,json={'version':1,'status':'ACTIVE','reason':'bypass'}).status_code==409
    role(sessions,UserRole.OWNER)
    assert http.post(BASE+f"/{row['id']}/decision",headers=headers,json={'version':1,'decision':'RETURN'}).status_code==422
    result=http.post(BASE+f"/{row['id']}/decision",headers=headers,json={'version':1,'decision':'RETURN','reason':'Correct details'})
    assert result.status_code==200 and result.json()['status']=='DRAFT'
    role(sessions,UserRole.ADMIN)
    assert http.post(BASE+f"/{row['id']}/submit",headers=headers,json={'version':2}).json()['status']=='PENDING'
    role(sessions,UserRole.OWNER)
    assert http.post(BASE+f"/{row['id']}/decision",headers=headers,json={'version':3}).json()['status']=='ACTIVE'
    assert http.post(BASE+f"/{row['id']}/status",headers=headers,json={'version':4,'status':'INACTIVE'}).status_code==422
    assert http.post(BASE+f"/{row['id']}/status",headers=headers,json={'version':4,'status':'INACTIVE','reason':'Leave'}).json()['status']=='INACTIVE'
    assert http.post(BASE+f"/{row['id']}/status",headers=headers,json={'version':5,'status':'TERMINATED','reason':'Exit'}).json()['status']=='TERMINATED'
    assert http.put(BASE+f"/{row['id']}",headers=headers,json={'version':6,'profile':PROFILE}).status_code==409
    assert http.get(BASE+f"/{row['id']}",headers=headers).json()['version']==6


@pytest.mark.parametrize('value',[UserRole.STAFF,UserRole.CLIENT,UserRole.SUPERVISOR,UserRole.OPERATIONS,UserRole.ACCOUNTS])
def test_private_directory_permissions(staff_client,value):
    http,sessions,headers=staff_client
    role(sessions,value)
    assert http.get(BASE,headers=headers).status_code==403
    assert http.post(BASE,headers=headers,json={'profile':PROFILE}).status_code==403


def test_hr_view_and_explicit_create_and_denial(staff_client):
    http,sessions,headers=staff_client
    role(sessions,UserRole.HR)
    assert http.get(BASE,headers=headers).status_code==200
    assert http.get('/api/v1/users/1/permissions',headers=headers).json()['permissions']['staff.view']
    assert http.get('/api/v1/users/2/permissions',headers=headers).status_code==403
    assert http.post(BASE,headers=headers,json={'profile':PROFILE}).status_code==403
    with sessions() as db:
        db.execute(text("insert into public.user_permissions values(1,'staff.create',true)"));db.commit()
    assert http.post(BASE,headers=headers,json={'profile':PROFILE,'submit':True}).json()['status']=='PENDING'
    with sessions() as db:
        db.execute(text("insert into public.user_permissions values(1,'staff.view',false)"));db.commit()
    assert http.get(BASE,headers=headers).status_code==403


def test_configurable_approval_requires_authorized_active_approver(staff_client):
    http,sessions,headers=staff_client
    with sessions() as db:
        actor=db.query(User).first()
        db.add(User(email='approver@example.in',login_id='HEAD-1',full_name='Head',hashed_password=actor.hashed_password,role=UserRole.OPERATIONS,is_active=True,is_superuser=False))
        db.commit();target=db.query(User).filter_by(login_id='HEAD-1').one().id
    assert http.put(BASE+'/approval-settings',headers=headers,json={'version':1,'approver_id':target}).status_code==422
    with sessions() as db:
        db.execute(text("insert into public.user_permissions values(:id,'staff.approve',true),(:id,'staff.view',true)"),{'id':target});db.commit()
    assert http.put(BASE+'/approval-settings',headers=headers,json={'version':1,'approver_id':target}).status_code==200
    assert http.put(BASE+'/approval-settings',headers=headers,json={'version':1,'approver_id':target}).status_code==409
    role(sessions,UserRole.ADMIN)
    row=http.post(BASE,headers=headers,json={'profile':PROFILE,'submit':True}).json()
    assert row['approver_id']==target
    assert http.post(BASE+f"/{row['id']}/decision",headers=headers,json={'version':1}).status_code==403
    token=http.post('/api/v1/auth/login',json={'login_id':'HEAD-1','password':'test-password-before'}).json()['access_token']
    target_headers={'Authorization':'Bearer '+token}
    assert http.post(BASE+f"/{row['id']}/decision",headers=target_headers,json={'version':1}).json()['status']=='ACTIVE'
    assert http.put(BASE+'/approval-settings',headers=target_headers,json={'version':2,'approver_id':None}).status_code==403


@pytest.mark.parametrize('key,value',[('phone','123'),('pan','BAD'),('bank_ifsc','BAD'),('email','bad'),('uan','12'),('dob','2099-01-01'),('pincode','012345')])
def test_invalid_details_rejected(staff_client,key,value):
    http,_,headers=staff_client
    assert http.post(BASE,headers=headers,json={'profile':{**PROFILE,key:value}}).status_code==422


def test_submission_requires_employment_details(staff_client):
    http,_,headers=staff_client
    draft={'name':'Draft Person','phone':'9876543212'}
    row=http.post(BASE,headers=headers,json={'profile':draft}).json()
    assert row['status']=='DRAFT'
    assert http.post(BASE+f"/{row['id']}/submit",headers=headers,json={'version':1}).status_code==422
    assert http.get(BASE+f"/{row['id']}",headers=headers).json()['version']==1
    assert http.get(BASE).status_code==401


def test_branch_must_be_shared_active_company_branch(staff_client):
    from app.models.company import CompanySettings
    http,sessions,headers=staff_client
    assert http.post(BASE,headers=headers,json={'profile':{**PROFILE,'branch':'UNKNOWN'}}).status_code==422
    with sessions() as db:
        db.add(CompanySettings(id=1,profile={'branches':[{'code':'DDN','name':'Dehradun','is_active':True},{'code':'OLD','name':'Old office','is_active':False}]}))
        db.commit()
    assert http.get(BASE+'/office-options',headers=headers).json()['branches']==[{'code':'DDN','name':'Dehradun'}]
    assert http.post(BASE,headers=headers,json={'profile':{**PROFILE,'branch':'OLD'}}).status_code==422
    assert http.post(BASE,headers=headers,json={'profile':{**PROFILE,'branch':'DDN'}}).status_code==201


def test_staff_login_requires_approved_staff(staff_client,monkeypatch):
    from app.api.v1.endpoints import users
    http,_,headers=staff_client
    calls=[]
    monkeypatch.setattr(users,'provision_supabase_password_user',lambda **kw:calls.append(kw) or {'id':'test-only'})
    payload={'full_name':'Account test','email':'staff@example.in','login_id':'S-DAS-0010','password':'test-only-password','role':'OPERATIONS'}
    assert http.post('/api/v1/users/',headers=headers,json=payload).status_code==409
    row=http.post(BASE,headers=headers,json={'profile':PROFILE}).json()
    assert http.post('/api/v1/users/',headers=headers,json=payload).status_code==409
    assert not calls
    assert http.post(BASE+f"/{row['id']}/submit",headers=headers,json={'version':1}).status_code==200
    result=http.post('/api/v1/users/',headers=headers,json=payload)
    assert result.status_code==201 and result.json()['login_id']=='S-DAS-0010'
    assert http.get(BASE+f"/{row['id']}",headers=headers).json()['account']['role']=='OPERATIONS'
