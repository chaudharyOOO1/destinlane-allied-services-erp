"""Attendance state transitions use isolated SQL tables, never production employees."""
import json,re
from datetime import datetime,time,timedelta,timezone
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request
from app.services import attendance as service
from app.api.v1.endpoints import attendance_master as api,mobile_sync,employee_workflow,roster_master
from app.api.deps import _request_permission
from test_roster_deployment import RosterDatabase,TODAY
from test_employee_master import OWNER,HR,OTHER,intake,complete,add_docs

CLOCK=datetime.combine(TODAY,time(8),timezone.utc)
class AttendanceDatabase(RosterDatabase):
    def __init__(self):
        super().__init__()
        self.conn.create_function('regexp_replace',4,lambda value,pattern,repl,flags:re.sub(pattern,repl,value))
        self.conn.executescript('''
          alter table sites add column latitude real default 28.6;
          alter table sites add column longitude real default 77.2;
          alter table sites add column geofence_radius_meters integer default 100;
          alter table sites add column address text;
          alter table guard_profiles add column user_id integer;
          drop table attendance;
          create table attendance(id text primary key default(uuid()),employee_id text,roster_id integer unique,attendance_date text,status text,check_in_time text,check_out_time text,check_in_selfie_url text,check_out_selfie_url text,check_in_latitude real,check_in_longitude real,check_out_latitude real,check_out_longitude real,check_in_accuracy real,check_out_accuracy real,check_in_lat real,check_in_lng real,check_out_lat real,check_out_lng real,check_in_distance_m real,check_out_distance_m real,device_id_hash text,is_geofence_verified boolean,verification_status text,is_late_punch boolean,late_minutes integer,night_shift boolean,shift_hours real,overtime_hours real,duty_hours real default 8,policy_snapshot text default '{}',version integer default 1,source text,submitted_at text,verified_at text,created_at text default(now()),updated_at text default(now()),unique(employee_id,attendance_date));
          create table attendance_shift_rules(site_id integer,shift_type text,start_time text,duty_hours real,grace_minutes integer,version integer default 1,updated_by integer,updated_at text,primary key(site_id,shift_type));
          create table attendance_selfies(id text primary key default(uuid()),employee_id text,kind text,storage_path text unique,mime_type text,sha256 text,created_at text,used_at text);
          create table employee_device_bindings(employee_id text primary key,device_hash text,bound_at text);
          create table employee_attendance_access(employee_id text primary key,pin_hash text,session_version integer default 1,failed_attempts integer default 0,locked_until text,updated_by integer,updated_at text);
          create table attendance_corrections(id text primary key default(uuid()),roster_id integer,base_version integer,proposed text,reason text,assigned_to integer,submitted_by integer,status text default 'PENDING',remarks text,decided_by integer,created_at text,decided_at text);
          create unique index one_correction on attendance_corrections(roster_id) where status='PENDING';
          create table attendance_history(id integer primary key,attendance_id text,employee_id text,changed_by integer,action text,details text,created_at text default(now()));
          create table payroll_runs(id integer primary key,payroll_month text,status text);
          create table salary_slips(id integer primary key,payroll_run_id integer,employee_id text);
        ''');self.conn.commit()
    def execute(self,sql,params=None):
        sql=str(sql).replace("right(regexp_replace(coalesce(e.phone,''),'[^0-9]','','g'),10)","substr(regexp_replace(coalesce(e.phone,''),'[^0-9]','','g'),-10)");sql=re.sub(r'cast\((:[a-z_]+) as (uuid|date|integer)\)',r'\1',sql)
        result=super().execute(sql,{k:(v.isoformat() if isinstance(v,time) else v) for k,v in (params or {}).items()})
        for r in result.rows:
            for k in ['proposed','policy_snapshot']:
                if k in r and isinstance(r[k],str):r[k]=json.loads(r[k])
        return result

@pytest.fixture
def db(monkeypatch):
    monkeypatch.setattr(employee_workflow,'has_permission',lambda *a:True)
    monkeypatch.setattr(service,'now',lambda:CLOCK)
    monkeypatch.setattr(service,'business_date',lambda:TODAY)
    db=AttendanceDatabase();record=complete(db,intake(db));add_docs(db,record['id']);employee_workflow.submit_joining(record['id'],{'version':record['version']},db,OWNER)
    db.eid=record['id'];db.rid=roster_master.create_roster(service_roster(),db,OWNER)['id']
    db.execute("update guard_profiles set user_id=4")
    db.execute("insert into attendance_shift_rules(site_id,shift_type,start_time,duty_hours,grace_minutes) values(1,'GENERAL','08:00:00',8,15)");db.commit();return db

def service_roster():
    from app.services.roster_deployment import Assignment
    return Assignment(site_id=1,guard_id=1,date=TODAY,shift_type='GENERAL')
def proof(db,kind='check-in',at=CLOCK,path=None):
    path=path or f'{db.eid}/{kind}-{at.isoformat()}'
    db.execute('insert into attendance_selfies(employee_id,kind,storage_path,mime_type,sha256,created_at) values(:employee,:kind,:path,\'image/jpeg\',:hash,:at)',{'employee':db.eid,'kind':kind,'path':path,'hash':'a'*64,'at':at});db.commit();return path

def payload(db,action='CHECK_IN',path=None,**extra):
    return service.Punch(roster_id=db.rid,action=action,latitude=28.6,longitude=77.2,accuracy=5,device_id='local-device-001',**{'check_in_selfie_path' if action=='CHECK_IN' else 'check_out_selfie_path':path or proof(db,'check-in' if action=='CHECK_IN' else 'check-out')},**extra)
def checkout(db,monkeypatch,elapsed=10):
    later=CLOCK+timedelta(hours=elapsed);monkeypatch.setattr(service,'now',lambda:later)
    return service.punch(db,payload(db,'CHECK_OUT',proof(db,'check-out',later)),db.eid)

def test_complete_flow_pending_review_and_hours(db,monkeypatch):
    first=service.punch(db,payload(db),db.eid);db.commit()
    assert first['verification_status']=='OPEN' and first['late_minutes']==315
    second=checkout(db,monkeypatch);db.commit()
    assert second['shift_hours']==8 and second['overtime_hours']==2
    assert second['verification_status']=='PENDING_REVIEW' and second['version']==2
    assert service.row(db,'select status from shift_rosters')['status']=='COMPLETED'
    assert len(db.execute('select * from attendance_history').all())==2
    assert 'device_id_hash' not in second and 'check_in_selfie_url' not in second

def test_duplicate_checkin_cannot_toggle_to_checkout(db):
    p=payload(db);service.punch(db,p,db.eid);db.commit()
    with pytest.raises(HTTPException) as e:service.punch(db,p,db.eid)
    assert e.value.status_code==409
    assert not service.row(db,'select * from attendance')['check_out_time']

@pytest.mark.parametrize('value,field',[(float('nan'),'latitude'),(float('inf'),'longitude'),(91,'latitude'),(181,'longitude'),(0,'accuracy'),(101,'accuracy')])
def test_gps_numeric_validation(db,value,field):
    with pytest.raises(ValidationError):service.Punch(**{**payload(db).model_dump(),field:value})

def test_out_of_geofence_never_creates_attendance_or_device(db):
    p=payload(db).model_copy(update={'latitude':29.6})
    with pytest.raises(HTTPException) as e:service.punch(db,p,db.eid)
    assert e.value.status_code==400
    assert not db.execute('select * from attendance').all()
    assert not db.execute('select * from employee_device_bindings').all()

@pytest.mark.parametrize('change',["date='2099-01-01'","date='2000-01-01'","status='CANCELLED'"])
def test_wrong_date_or_cancelled_roster_blocked(db,change):
    db.execute('update shift_rosters set '+change);db.commit()
    with pytest.raises(HTTPException):service.punch(db,payload(db),db.eid)

def test_roster_employee_impersonation_blocked(db):
    with pytest.raises(HTTPException) as e:service.punch(db,payload(db),'other-employee')
    assert e.value.status_code==403

def test_compliance_required_for_checkin(db):
    db.execute("update employee_documents set verification_status='REJECTED'");db.commit()
    with pytest.raises(HTTPException):service.punch(db,payload(db),db.eid)

def test_missing_shift_rule_blocks_checkin(db):
    db.execute('delete from attendance_shift_rules');db.commit()
    with pytest.raises(HTTPException):service.punch(db,payload(db),db.eid)

@pytest.mark.parametrize('issue',['stale','wrong-kind','other-person','used','future'])
def test_selfie_ownership_freshness_and_reuse(db,issue):
    at=CLOCK-timedelta(minutes=11) if issue=='stale' else CLOCK+timedelta(minutes=1) if issue=='future' else CLOCK
    path=proof(db,'check-out' if issue=='wrong-kind' else 'check-in',at)
    if issue=='other-person':db.execute("update attendance_selfies set employee_id='other'")
    if issue=='used':db.execute('update attendance_selfies set used_at=:now',{'now':CLOCK})
    db.commit()
    with pytest.raises(HTTPException) as e:service.punch(db,payload(db,path=path),db.eid)
    assert e.value.status_code==422
    assert not db.execute('select * from attendance').all()

def test_persistent_device_binding_blocks_different_device(db):
    service.punch(db,payload(db),db.eid);db.commit()
    p=payload(db,'CHECK_OUT').model_copy(update={'device_id':'different-device'})
    with pytest.raises(HTTPException) as e:service.punch(db,p,db.eid)
    assert e.value.status_code==409

def test_overnight_checkout_uses_starting_roster_date(db,monkeypatch):
    start=datetime.combine(TODAY,time(15),timezone.utc);monkeypatch.setattr(service,'now',lambda:start)
    service.punch(db,payload(db,path=proof(db,at=start)),db.eid);db.commit()
    end=start+timedelta(hours=10);monkeypatch.setattr(service,'now',lambda:end)
    p=payload(db,'CHECK_OUT',proof(db,'check-out',end)).model_copy(update={'roster_id':None})
    result=service.punch(db,p,db.eid)
    assert result['attendance_date']==TODAY.isoformat() and result['overtime_hours']==2

def test_checkout_after_24_hours_requires_correction(db,monkeypatch):
    service.punch(db,payload(db),db.eid);db.commit()
    with pytest.raises(HTTPException):checkout(db,monkeypatch,25)
    db.rollback();assert not service.row(db,'select * from attendance')['check_out_time']

def test_shift_rule_snapshot_preserves_hours(db,monkeypatch):
    service.punch(db,payload(db),db.eid);db.commit()
    db.execute('update attendance_shift_rules set duty_hours=12');db.commit()
    assert checkout(db,monkeypatch)['overtime_hours']==2

def test_correction_keeps_record_until_approval_and_manual_flag(db,monkeypatch):
    service.punch(db,payload(db),db.eid);db.commit();checkout(db,monkeypatch);db.commit()
    record=service.row(db,'select * from attendance')
    request=service.request_correction(db,service.Correction(roster_id=db.rid,version=record['version'],assigned_to=1,reason='Verified supervisor register',status='present',check_in_time=CLOCK,check_out_time=CLOCK+timedelta(hours=9)),OTHER,OWNER);db.commit()
    assert service.row(db,'select * from attendance')['overtime_hours']==2
    service.decide_correction(db,request['id'],service.Decision(decision='APPROVE',reason='Register reviewed'),OWNER);db.commit()
    after=service.row(db,'select * from attendance')
    assert after['overtime_hours']==1 and not after['is_geofence_verified'] and after['verification_status']=='VERIFIED'
    assert after['source']=='MANUAL_CORRECTION'
    assert after['check_in_selfie_url']==record['check_in_selfie_url']

@pytest.mark.parametrize('status',['absent','leave'])
def test_missing_punch_manual_status_can_be_approved(db,status):
    request=service.request_correction(db,service.Correction(roster_id=db.rid,version=0,assigned_to=1,reason='Supervisor daily return',status=status),OTHER,OWNER);db.commit()
    service.decide_correction(db,request['id'],service.Decision(decision='APPROVE',reason='Return verified'),OWNER);db.commit()
    a=service.row(db,'select * from attendance');assert a['status']==status and a['shift_hours']==0 and not a['is_geofence_verified']

def test_correction_rejection_does_not_mutate_attendance(db):
    r=service.request_correction(db,service.Correction(roster_id=db.rid,version=0,assigned_to=1,reason='Manual entry',status='absent'),OTHER,OWNER);db.commit()
    service.decide_correction(db,r['id'],service.Decision(decision='REJECT',reason='Wrong register'),OWNER);db.commit()
    assert not db.execute('select * from attendance').all()

def test_only_assigned_approver_and_no_self_approval(db):
    r=service.request_correction(db,service.Correction(roster_id=db.rid,version=0,assigned_to=3,reason='Manual entry',status='absent'),OTHER,OTHER);db.commit()
    for user in [HR,OTHER]:
        with pytest.raises(HTTPException) as e:service.decide_correction(db,r['id'],service.Decision(decision='APPROVE',reason='Reviewed'),user)
        assert e.value.status_code==403

def test_stale_correction_cannot_overwrite_new_punch(db):
    r=service.request_correction(db,service.Correction(roster_id=db.rid,version=0,assigned_to=1,reason='Manual entry',status='absent'),OTHER,OWNER);db.commit()
    service.punch(db,payload(db),db.eid);db.commit()
    with pytest.raises(HTTPException):service.decide_correction(db,r['id'],service.Decision(decision='APPROVE',reason='Reviewed'),OWNER)

def test_payroll_lock_blocks_changes(db):
    db.execute("insert into payroll_runs values(1,:month,'CALCULATED')",{'month':TODAY.replace(day=1)})
    db.execute('insert into salary_slips values(1,1,:id)',{'id':db.eid});db.commit()
    with pytest.raises(HTTPException) as e:service.punch(db,payload(db),db.eid)
    assert e.value.status_code==409

def test_direct_edit_bypass_closed(db):
    with pytest.raises(HTTPException) as e:api.update_attendance('id',{'verification_status':'VERIFIED'},db,OWNER)
    assert e.value.status_code==409

@pytest.mark.parametrize('suffix,method,permission',[('corrections','POST','edit'),('corrections/id/decision','POST','approve'),('id/review','POST','approve'),('id/selfie/check-in/sign','POST','view'),('reports/export','GET','export')])
def test_attendance_action_permission_mapping(suffix,method,permission):
    assert _request_permission(Request({'type':'http','method':method,'path':'/api/v1/erp/attendance/'+suffix,'headers':[]}))=='attendance.'+permission

def test_mobile_login_requires_pin_and_session_version():
    with pytest.raises(ValidationError):mobile_sync.MobileLoginRequest(phone='9876543210')
    assert mobile_sync._mobile_employee_id(mobile_sync._mobile_token('11111111-1111-1111-1111-111111111111',2))[1]==2
    assert mobile_sync._clean_phone('+919876543210')=='9876543210'
    assert mobile_sync._clean_phone('1234567890123')==''

def test_selfie_mime_and_size_boundaries(db):
    import asyncio,io
    from starlette.datastructures import UploadFile,Headers
    for data,mime,code in [(b'fake photo','image/jpeg',415),(b'','image/png',415),(b'x'*(3*1024*1024+1),'image/jpeg',413)]:
        file=UploadFile(io.BytesIO(data),filename='local.jpg',headers=Headers({'content-type':mime}))
        with pytest.raises(HTTPException) as e:asyncio.run(mobile_sync.mobile_selfie({'id':db.eid},file,'check-in',db))
        assert e.value.status_code==code

def test_pin_enable_login_and_session_revocation(db):
    from uuid import UUID
    api.set_access(UUID(db.eid),service.Access(pin='85729364',reason='Initial staff verified'),db,OWNER)
    result=mobile_sync.mobile_login(mobile_sync.MobileLoginRequest(phone='9876543210',pin='85729364'),db)
    assert 'pin_hash' not in result['employee'] and 'session_version' not in result['employee']
    assert 'profile' not in result['employee'] and 'aadhaar_no' not in result['employee']
    assert mobile_sync.get_mobile_employee(result['access_token'],db)['id']==db.eid
    api.set_access(UUID(db.eid),service.Access(pin='59374628',reason='Employee forgot PIN'),db,OWNER)
    with pytest.raises(HTTPException) as e:mobile_sync.get_mobile_employee(result['access_token'],db)
    assert e.value.status_code==401

def test_five_wrong_pin_attempts_lock_login(db):
    from uuid import UUID
    api.set_access(UUID(db.eid),service.Access(pin='85729364',reason='Initial access'),db,OWNER)
    for _ in range(5):
        with pytest.raises(HTTPException) as e:mobile_sync.mobile_login(mobile_sync.MobileLoginRequest(phone='9876543210',pin='55555555'),db)
        assert e.value.status_code==401
    with pytest.raises(HTTPException) as e:mobile_sync.mobile_login(mobile_sync.MobileLoginRequest(phone='9876543210',pin='85729364'),db)
    assert e.value.status_code==429

def test_phone_only_legacy_token_is_rejected(db):
    from jose import jwt
    from app.core.config import settings
    from uuid import UUID
    api.set_access(UUID(db.eid),service.Access(pin='85729364',reason='Initial access'),db,OWNER)
    token=jwt.encode({'sub':'employee:'+db.eid,'mobile':True,'exp':datetime.now(timezone.utc)+timedelta(hours=1)},settings.SECRET_KEY,algorithm=settings.ALGORITHM)
    with pytest.raises(HTTPException) as e:mobile_sync.get_mobile_employee(token,db)
    assert e.value.status_code==401

def test_punch_review_changes_verification_not_gps(db,monkeypatch):
    from uuid import UUID
    service.punch(db,payload(db),db.eid);db.commit();a=checkout(db,monkeypatch);db.commit()
    result=api.review(UUID(a['id']),service.Review(version=2,decision='APPROVE',reason='Checked selfies and shift'),db,OWNER)
    assert result['verification_status']=='VERIFIED' and result['is_geofence_verified'] and result['version']==3
    with pytest.raises(HTTPException):api.review(UUID(a['id']),service.Review(version=2,decision='APPROVE',reason='Stale decision'),db,OWNER)

def test_device_reset_cannot_strand_open_shift(db):
    from uuid import UUID
    service.punch(db,payload(db),db.eid);db.commit()
    with pytest.raises(HTTPException) as e:api.reset_device(UUID(db.eid),service.Reason(reason='New employee phone'),db,OWNER)
    assert e.value.status_code==409

def test_shift_rule_edits_require_current_version(db):
    rule=service.Rule(site_id=1,shift_type='GENERAL',start_time=time(9),duty_hours=9,grace_minutes=10,version=1,reason='Client updated duty')
    result=api.save_rule(rule,db,OWNER)
    assert result['version']==2
    with pytest.raises(HTTPException):api.save_rule(rule,db,OWNER)

def test_correction_snapshot_unchanged_when_shift_rule_changes(db,monkeypatch):
    service.punch(db,payload(db),db.eid);db.commit();checkout(db,monkeypatch);db.commit()
    a=service.row(db,'select * from attendance')
    request=service.request_correction(db,service.Correction(roster_id=db.rid,version=a['version'],assigned_to=1,reason='Signed register',status='present',check_in_time=CLOCK,check_out_time=CLOCK+timedelta(hours=9)),OTHER,OWNER);db.commit()
    db.execute('update attendance_shift_rules set duty_hours=12');db.commit()
    service.decide_correction(db,request['id'],service.Decision(decision='APPROVE',reason='Supervisor confirmed'),OWNER);db.commit()
    assert service.row(db,'select overtime_hours from attendance')['overtime_hours']==1
