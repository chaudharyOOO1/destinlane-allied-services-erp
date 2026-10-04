import pytest
from sqlalchemy import text
from test_authentication import client
from app.models.client import Client,ClientCodeCounter,ClientStaffAssignment,ClientHistory
from app.models.internal_staff import InternalStaff
from app.models.company import CompanySettings
from app.models.user import User
from app.models.enums import UserRole

BASE='/api/v1/erp/clients'
PROFILE={'company_name':'Test Client','gstin':'05ABCDE1234F1Z5','billing_address':'Test address','branch_region':'UTTARAKHAND','contact_person':'Test Contact','contact_email':'contact@example.in','contact_phone':'9876543210'}


@pytest.fixture
def clients_client(client):
    http,sessions=client
    with sessions() as db:
        db.execute(text("ATTACH DATABASE ':memory:' AS public"))
        db.execute(text('CREATE TABLE public.user_permissions(user_id INTEGER,permission_key TEXT,allowed BOOLEAN)'))
        db.execute(text('CREATE TABLE IF NOT EXISTS client_contracts(id INTEGER PRIMARY KEY,client_id INTEGER,status TEXT,contract_end_date DATE)'))
        db.add(ClientCodeCounter(id=1,next_number=1));db.commit()
    token=http.post('/api/v1/auth/login',json={'login_id':'ADMIN-001','password':'test-password-before'}).json()['access_token']
    return http,sessions,{'Authorization':'Bearer '+token}


def test_client_codes_validation_persistence_and_version_history(clients_client):
    http,sessions,headers=clients_client
    made=http.post(BASE,headers=headers,json=PROFILE)
    assert made.status_code==201
    row=made.json();assert row['client_code']=='C-DAS-0001' and row['version']==1
    assert row['site_count']==0 and row['active_contract_count']==0
    assert http.post(BASE,headers=headers,json={**PROFILE,'company_name':'Duplicate GST'}).status_code==409
    revised={**PROFILE,'credit_terms_days':45,'notes':'Changed terms','billing_cycle':'WEEKLY'}
    result=http.patch(BASE+f"/{row['id']}",headers=headers,json={'version':1,'profile':revised})
    assert result.status_code==200 and result.json()['version']==2
    assert result.json()['profile']['credit_terms_days']==45
    assert http.patch(BASE+f"/{row['id']}",headers=headers,json={'version':1,'profile':PROFILE}).status_code==409
    assert http.patch(BASE+f"/{row['id']}",headers=headers,json={'version':2,'profile':revised,'client_code':'C-DAS-9999'}).status_code==422
    with sessions() as db:
        assert db.query(ClientHistory).count()==2
        assert db.query(Client).first().billing_cycle=='WEEKLY'
        assert db.query(ClientCodeCounter).first().next_number==2


def test_client_field_officers_are_staff_with_matching_responsibility(clients_client):
    http,sessions,headers=clients_client
    with sessions() as db:
        db.add(CompanySettings(id=1,profile={'branches':[{'code':'DDN','name':'Dehradun','is_active':True}]}))
        db.add(InternalStaff(staff_code='S-DAS-0010',name='Test Officer',phone='9876543211',status='ACTIVE',profile={'management_level':'FIELD_OFFICER','portal_role':'OPERATIONS','region':'UTTARAKHAND','branch':'DDN'}))
        db.commit();staff_id=db.query(InternalStaff).first().id
    assert http.get(BASE+'/options',headers=headers).json()['staff'][0]['staff_code']=='S-DAS-0010'
    assert http.post(BASE,headers=headers,json={**PROFILE,'branch':'MISSING'}).status_code==422
    assert http.post(BASE,headers=headers,json={**PROFILE,'branch_region':'DELHI_NCR','field_officer_ids':[staff_id]}).status_code==422
    made=http.post(BASE,headers=headers,json={**PROFILE,'branch':'DDN','field_officer_ids':[staff_id]}).json()
    assert made['field_officers']=='Test Officer'
    assert http.get(BASE+f"/{made['id']}/field-officers",headers=headers).json()[0]['staff_code']=='S-DAS-0010'
    changed=http.patch(BASE+f"/{made['id']}",headers=headers,json={'version':1,'profile':{**PROFILE,'branch':'DDN','field_officer_ids':[]}})
    assert changed.status_code==200 and not changed.json()['assigned_staff']
    with sessions() as db:assert not db.query(ClientStaffAssignment).first().is_active


def test_portal_account_can_only_view_assigned_client(clients_client):
    http,sessions,headers=clients_client
    with sessions() as db:
        owner=db.query(User).first()
        account=User(login_id='CLIENT-1',email='client@example.in',full_name='Client User',role=UserRole.CLIENT,is_active=True,is_superuser=False,hashed_password=owner.hashed_password)
        db.add(account);db.commit();uid=account.id
    own=http.post(BASE,headers=headers,json={**PROFILE,'portal_user_id':uid}).json()
    other=http.post(BASE,headers=headers,json={**PROFILE,'company_name':'Other Client','gstin':'07FGHIJ5678K1Z1'}).json()
    token=http.post('/api/v1/auth/login',json={'login_id':'CLIENT-1','password':'test-password-before'}).json()['access_token']
    client_headers={'Authorization':'Bearer '+token}
    assert [x['id'] for x in http.get(BASE,headers=client_headers).json()]==[own['id']]
    assert http.get(BASE+f"/{other['id']}",headers=client_headers).status_code==404
    assert http.get(BASE+f"/{other['id']}/field-officers",headers=client_headers).status_code==404
    assert http.get(BASE+'/options',headers=client_headers).status_code==403
    assert http.post(BASE,headers=client_headers,json=PROFILE).status_code==403
    assert http.post(BASE,headers=headers,json={**PROFILE,'company_name':'Portal Duplicate','gstin':'07KLMNO1234P1Z1','portal_user_id':uid}).status_code==409


@pytest.mark.parametrize('key,value',[('gstin','BAD'),('contact_phone','123'),('contact_email','bad'),('branch_region','OTHER'),('pan','ABCDE0000F'),('credit_terms_days',-1),('pincode','000001'),('contract_end_date','2025-01-01')])
def test_invalid_client_data_does_not_persist(clients_client,key,value):
    http,sessions,headers=clients_client
    assert http.post(BASE,headers=headers,json={**PROFILE,key:value}).status_code==422
    with sessions() as db:assert db.query(Client).count()==0 and db.query(ClientCodeCounter).first().next_number==1


def test_client_permission_denial_before_reads(clients_client):
    http,sessions,headers=clients_client
    with sessions() as db:
        user=db.query(User).first();user.role=UserRole.OPERATIONS;user.is_superuser=False
        db.execute(text("insert into public.user_permissions values(1,'clients.view',false)"));db.commit()
    assert http.get(BASE,headers=headers).status_code==403
    assert http.get(BASE).status_code==401
