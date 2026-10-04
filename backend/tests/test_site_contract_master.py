from datetime import date,timedelta
from decimal import Decimal
import pytest
from sqlalchemy import text
from test_authentication import client
from app.models.client import Client,ClientCodeCounter,ClientStaffAssignment
from app.models.company import CompanySettings
from app.models.internal_staff import InternalStaff
from app.models.commercial import SiteCodeCounter,ClientContract,SiteRateCard,CommercialHistory
from app.models.site import Site
from app.models.user import User
from app.models.enums import UserRole

SITES='/api/v1/erp/sites'
CONTRACTS='/api/v1/erp/contracts'
TODAY=date.today()
def day(offset):return (TODAY+timedelta(days=offset)).isoformat()
SITE={'client_id':1,'site_name':'Test Site','address':'Test deployment address','city':'Dehradun','state':'Uttarakhand','postal_code':'248001','branch':'DDN'}
CONTRACT={'client_id':1,'contract_number':'DAS-TEST-1','contract_start_date':day(-30),'contract_end_date':day(365),'status':'ACTIVE','service_verticals':['SECURITY','HEALTHCARE']}
RATE={'contract_id':1,'vertical':'SECURITY','category':'Guard','daily_rate':'650.50','hourly_rate':'90.00','effective_from':day(1),'effective_to':day(90)}

@pytest.fixture
def masters(client):
    http,sessions=client
    with sessions() as db:
        db.execute(text("ATTACH DATABASE ':memory:' AS public"))
        db.execute(text('CREATE TABLE public.user_permissions(user_id INTEGER,permission_key TEXT,allowed BOOLEAN)'))
        db.add(Client(company_name='Test Client',client_code='C-DAS-0001',gstin='05ABCDE1234F1Z5',contact_person='Test Contact',contact_email='contact@example.in',contact_phone='9876543210',billing_address='Test address',branch='DDN',branch_region='UTTARAKHAND',profile={}))
        db.add(CompanySettings(id=1,profile={'branches':[{'code':'DDN','name':'Dehradun','is_active':True}]}))
        db.add(SiteCodeCounter(id=1,next_number=1))
        db.add(InternalStaff(staff_code='S-DAS-0010',name='Test Coordinator',phone='9876543211',status='ACTIVE',profile={'management_level':'FIELD_OFFICER','region':'UTTARAKHAND','branch':'DDN','portal_role':'OPERATIONS'}))
        db.commit();db.add(ClientStaffAssignment(client_id=1,staff_id=1,is_active=True));db.commit()
    token=http.post('/api/v1/auth/login',json={'login_id':'ADMIN-001','password':'test-password-before'}).json()['access_token']
    return http,sessions,{'Authorization':'Bearer '+token}


def setup_rows(masters):
    http,_,headers=masters
    contract=http.post(CONTRACTS,headers=headers,json=CONTRACT);assert contract.status_code==201,contract.text
    site=http.post(SITES,headers=headers,json={**SITE,'contract_id':contract.json()['id'],'field_officer_ids':[1]});assert site.status_code==201,site.text
    return site.json(),contract.json()


def test_site_edit_codes_coordinates_history_and_no_commercial_leak(masters):
    http,sessions,h=masters
    made=http.post(SITES,headers=h,json={**SITE,'field_officer_ids':[1],'latitude':30.3165,'longitude':78.0322,'shift_requirements':{'day_shift_guards':3}})
    assert made.status_code==201,made.text
    row=made.json();assert row['site_code']=='SITE-DAS-0001' and row['assigned_staff'][0]['staff_code']=='S-DAS-0010'
    assert 'contractual_rate' not in row and row['branch_region']=='UTTARAKHAND'
    assert http.post(SITES,headers=h,json={**SITE,'site_name':'test site'}).status_code==409
    revised={**row['profile'],'site_name':'Test Site Revised','notes':'Updated GPS','geofence_radius_meters':150}
    updated=http.patch(SITES+'/1',headers=h,json={'version':1,'profile':revised});assert updated.status_code==200,updated.text
    assert updated.json()['version']==2 and updated.json()['site_code']==row['site_code']
    assert http.patch(SITES+'/1',headers=h,json={'version':1,'profile':revised}).status_code==409
    assert len(http.get(SITES+'/1/history',headers=h).json())==2
    assert http.patch(SITES+'/1',headers=h,json={'version':2,'profile':{**revised,'site_code':'BAD'}}).status_code==422
    with sessions() as db:assert db.query(SiteCodeCounter).first().next_number==2


@pytest.mark.parametrize('changes',[{'latitude':'bad'},{'latitude':91,'longitude':75},{'latitude':30},{'longitude':float('inf')},{'geofence_radius_meters':0},{'branch':'BAD'},{'postal_code':'000001'},{'field_officer_ids':[99]},{'shift_requirements':{'day_shift_guards':-1}}])
def test_bad_site_inputs_are_rejected_without_allocation(masters,changes):
    http,sessions,h=masters
    # JSON cannot serialize infinity; send its string representation to test Pydantic.
    if changes.get('longitude')==float('inf'):changes={'latitude':30,'longitude':'Infinity'}
    assert http.post(SITES,headers=h,json={**SITE,**changes}).status_code==422
    with sessions() as db:assert db.query(Site).count()==0 and db.query(SiteCodeCounter).first().next_number==1


def test_site_coordinator_must_remain_assigned_to_client(masters):
    http,sessions,h=masters
    with sessions() as db:db.query(ClientStaffAssignment).first().is_active=False;db.commit()
    assert http.post(SITES,headers=h,json={**SITE,'field_officer_ids':[1]}).status_code==422
    assert http.get(SITES+'/options',headers=h).json()['clients'][0]['staff']==[]


def test_contract_validation_versions_and_client_links(masters):
    http,sessions,h=masters
    site,contract=setup_rows(masters)
    assert http.post(CONTRACTS,headers=h,json={**CONTRACT,'contract_number':'das-test-1'}).status_code==409
    assert http.post(CONTRACTS,headers=h,json={**CONTRACT,'contract_number':'BAD-DATE','contract_end_date':day(-31)}).status_code==422
    assert http.post(CONTRACTS,headers=h,json={**CONTRACT,'contract_number':'BAD-SERVICE','service_verticals':[]}).status_code==422
    revised={**CONTRACT,'renewal_notes':'Review pending','credit_terms_days':45}
    updated=http.patch(CONTRACTS+'/1',headers=h,json={'version':1,'profile':revised});assert updated.status_code==200,updated.text
    assert updated.json()['site_count']==1 and updated.json()['version']==2
    assert http.patch(CONTRACTS+'/1',headers=h,json={'version':1,'profile':revised}).status_code==409
    assert len(http.get(CONTRACTS+'/1/history',headers=h).json())==2
    assert http.get(CONTRACTS+'/site/999/rates',headers=h).status_code==404


def test_rate_monthly_decimal_derivation_overlap_and_dates(masters):
    http,sessions,h=masters
    setup_rows(masters)
    path=CONTRACTS+'/site/1/rates'
    payload={**RATE,'rate_basis':'MONTHLY','monthly_rate':'16900.00','billable_days':26,'duty_hours':'8.00'}
    made=http.post(path,headers=h,json=payload);assert made.status_code==201,made.text
    r=made.json();assert r['daily_rate']=='650.00' and r['hourly_rate']=='81.25'
    assert http.post(path,headers=h,json={**RATE,'effective_from':day(90),'effective_to':day(100)}).status_code==409
    successor=http.post(path,headers=h,json={**RATE,'effective_from':day(91),'effective_to':day(100)});assert successor.status_code==201,successor.text
    assert http.post(path,headers=h,json={**RATE,'category':'OTHER','effective_to':day(366)}).status_code==422
    assert http.post(path,headers=h,json={**RATE,'category':'OTHER','daily_rate':'-1'}).status_code==422
    assert http.post(path,headers=h,json={**RATE,'category':'OTHER','daily_rate':'1.001'}).status_code==422
    assert http.post(path,headers=h,json={**RATE,'vertical':'HOUSEKEEPING'}).status_code==422
    revised={**r['profile'],'monthly_rate':'18200.00','notes':'Revised before start'}
    updated=http.patch(path+'/1',headers=h,json={'version':1,'profile':revised});assert updated.status_code==200,updated.text
    assert updated.json()['daily_rate']=='700.00'
    assert http.patch(path+'/1',headers=h,json={'version':1,'profile':revised}).status_code==409
    with sessions() as db:assert db.query(SiteRateCard).first().daily_rate==Decimal('700.00')


def test_started_rate_requires_successor_and_retains_historical_period(masters):
    http,sessions,h=masters
    setup_rows(masters);path=CONTRACTS+'/site/1/rates'
    r=http.post(path,headers=h,json={**RATE,'effective_from':day(-10)}).json()
    assert http.patch(path+'/1',headers=h,json={'version':1,'profile':{**r['profile'],'daily_rate':'700.00'}}).status_code==409
    assert http.patch(path+'/1',headers=h,json={'version':1,'profile':{**r['profile'],'is_active':False,'notes':'Cancelled'}}).status_code==409
    result=http.patch(path+'/1',headers=h,json={'version':1,'profile':{**r['profile'],'effective_to':day(0),'notes':'Replaced from tomorrow'}})
    assert result.status_code==200,result.text
    assert http.post(path,headers=h,json={**RATE,'effective_from':day(1)}).status_code==201
    assert http.patch(CONTRACTS+'/1',headers=h,json={'version':1,'profile':{**CONTRACT,'contract_end_date':day(20)}}).status_code==409
    with sessions() as db:assert db.query(CommercialHistory).count()==5


def test_healthcare_storage_mapping_and_contract_scope(masters):
    http,sessions,h=masters
    setup_rows(masters)
    made=http.post(CONTRACTS+'/site/1/rates',headers=h,json={**RATE,'vertical':'HEALTHCARE','category':'GDA'})
    assert made.status_code==201 and made.json()['vertical']=='HEALTHCARE'
    with sessions() as db:assert db.query(SiteRateCard).first().vertical=='NURSING'
    assert http.patch(CONTRACTS+'/1',headers=h,json={'version':1,'profile':{**CONTRACT,'service_verticals':['SECURITY']}}).status_code==409


@pytest.mark.parametrize('role',['STAFF','CLIENT','SUPERVISOR','OPERATIONS','HR','ACCOUNTS'])
def test_commercial_and_site_permissions(masters,role):
    http,sessions,h=masters
    setup_rows(masters)
    with sessions() as db:
        u=db.query(User).first();u.role=UserRole(role);u.is_superuser=False;db.commit()
    assert http.post(CONTRACTS,headers=h,json=CONTRACT).status_code==403
    expected=200 if role=='ACCOUNTS' else 403
    assert http.get(CONTRACTS,headers=h).status_code==expected
    site_expected=200 if role in {'SUPERVISOR','OPERATIONS'} else 403
    assert http.get(SITES,headers=h).status_code==site_expected
    assert http.post(SITES,headers=h,json={**SITE,'site_name':'Other'}).status_code==403
    assert http.get(CONTRACTS+'/site/1/rates',headers=h).status_code==expected


def test_ops_explicit_site_permissions_do_not_grant_commercial_changes(masters):
    http,sessions,h=masters
    with sessions() as db:
        u=db.query(User).first();u.role=UserRole.OPERATIONS;u.is_superuser=False
        for key in ['sites.create','sites.edit']:db.execute(text('insert into public.user_permissions values(1,:key,true)'),{'key':key})
        db.commit()
    assert http.post(SITES,headers=h,json=SITE).status_code==201
    assert http.post(CONTRACTS,headers=h,json=CONTRACT).status_code==403
    assert http.get(SITES).status_code==401
    assert http.get(CONTRACTS).status_code==401


def test_rate_requires_linked_site_contract_and_cross_client_link_is_rejected(masters):
    http,sessions,h=masters
    c=http.post(CONTRACTS,headers=h,json=CONTRACT).json()
    s=http.post(SITES,headers=h,json=SITE).json()
    assert http.post(CONTRACTS+f"/site/{s['id']}/rates",headers=h,json=RATE).status_code==422
    with sessions() as db:
        db.add(Client(company_name='Other Client',contact_person='Other',contact_email='other@example.in',contact_phone='9876543213',billing_address='Other address',branch_region='DELHI_NCR',profile={}))
        db.commit()
    other=http.post(CONTRACTS,headers=h,json={**CONTRACT,'client_id':2,'contract_number':'OTHER-1'}).json()
    assert http.patch(SITES+'/1',headers=h,json={'version':1,'profile':{**SITE,'contract_id':other['id']}}).status_code==422
    good=http.patch(SITES+'/1',headers=h,json={'version':1,'profile':{**SITE,'contract_id':c['id']}})
    assert good.status_code==200
    assert http.post(CONTRACTS+'/site/1/rates',headers=h,json=RATE).status_code==201


def test_closed_contract_site_can_be_inactivated_without_losing_reference(masters):
    http,sessions,h=masters
    site,c=setup_rows(masters)
    closed=http.patch(CONTRACTS+'/1',headers=h,json={'version':1,'profile':{**CONTRACT,'status':'TERMINATED','renewal_notes':'Site service ended'}})
    assert closed.status_code==200
    inactive=http.patch(SITES+'/1',headers=h,json={'version':1,'profile':{**site['profile'],'is_active':False}})
    assert inactive.status_code==200 and inactive.json()['contract_id']==c['id']
    assert http.patch(CONTRACTS+'/1',headers=h,json={'version':2,'profile':CONTRACT}).status_code==409


def test_explicit_read_grant_for_operations_does_not_allow_rate_writes(masters):
    http,sessions,h=masters
    setup_rows(masters)
    with sessions() as db:
        u=db.query(User).first();u.role=UserRole.OPERATIONS;u.is_superuser=False
        db.execute(text("insert into public.user_permissions values(1,'contracts.view',true)"));db.commit()
    assert http.get(CONTRACTS,headers=h).status_code==200
    assert http.get(CONTRACTS+'/site/1/rates',headers=h).status_code==200
    assert http.post(CONTRACTS+'/site/1/rates',headers=h,json=RATE).status_code==403
