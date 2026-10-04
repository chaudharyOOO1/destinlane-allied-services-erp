from datetime import timedelta
import json,re
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from app.core.business_time import business_date
from app.services import roster_deployment as service
from app.api.v1.endpoints import roster_master as api
from test_employee_master import Database,HR,OWNER,intake,complete,add_docs
from app.api.v1.endpoints import employee_workflow

TODAY=business_date()
class RosterDatabase(Database):
    def __init__(self):
        super().__init__()
        self.conn.executescript("""
         alter table sites add column contract_id integer;
         alter table sites add column site_code text;
         alter table sites add column shift_requirements text default '{}';
         create table shift_rosters(id integer primary key,site_id integer,guard_id integer,date text,shift_type text,status text default 'SCHEDULED',notes text,version integer default 1,created_by integer,updated_by integer,created_at text default(now()),updated_at text default(now()));
         create unique index active_employee_day on shift_rosters(guard_id,date) where status in ('SCHEDULED','COMPLETED');
         create table roster_history(id integer primary key,roster_id integer,changed_by integer,action text,version integer,details text,created_at text default(now()));
         create table attendance(id integer primary key,roster_id integer);
         create table client_contracts(id integer primary key,status text,contract_start_date text,contract_end_date text,profile text);
        """)
        self.conn.commit()
    def execute(self,sql,params=None):
        sql=re.sub(r' for update(?: of [a-z,]+)?','',str(sql))
        result=super().execute(sql,params)
        for r in result.rows:
            for k in ['shift_requirements']:
                if k in r:r[k]=json.loads(r[k])
            for k in ['contract_start_date','contract_end_date']:
                if k in r:
                    from datetime import date
                    r[k]=date.fromisoformat(r[k])
        return result

@pytest.fixture
def db(monkeypatch):
    monkeypatch.setattr(employee_workflow,'has_permission',lambda *a:True)
    db=RosterDatabase();r=complete(db,intake(db));add_docs(db,r['id']);employee_workflow.submit_joining(r['id'],{'version':r['version']},db,OWNER)
    return db


def assignment(**kwargs):return service.Assignment(site_id=1,guard_id=1,date=TODAY,shift_type='GENERAL',**kwargs)


def test_general_assignment_and_audit(db):
    r=api.create_roster(assignment(),db,OWNER)
    assert r['shift_type']=='GENERAL';assert r['status']=='SCHEDULED';assert r['version']==1
    assert db.execute('select * from roster_history').one()['action']=='SCHEDULE'


def test_different_site_or_shift_still_conflicts_same_day(db):
    api.create_roster(assignment(),db,OWNER)
    with pytest.raises(HTTPException) as error:api.create_roster(service.Assignment(site_id=1,guard_id=1,date=TODAY,shift_type='NIGHT'),db,OWNER)
    assert error.value.status_code==409


def test_cancel_preserves_history_and_frees_date(db):
    r=api.create_roster(assignment(),db,OWNER)
    cancelled=api.cancel_roster(r['id'],service.Cancel(version=1,reason='Client requirement cancelled'),db,OWNER)
    assert cancelled['status']=='CANCELLED'
    assert api.create_roster(assignment(),db,OWNER)['id']!=r['id']
    assert len(db.execute('select * from roster_history').all())==3


def test_stale_version_cannot_cancel(db):
    r=api.create_roster(assignment(),db,OWNER)
    update=service.Update(site_id=1,guard_id=1,date=TODAY+timedelta(days=1),shift_type='DAY',version=1,reason='Client date changed')
    api.update_roster(r['id'],update,db,OWNER)
    with pytest.raises(HTTPException) as error:api.cancel_roster(r['id'],service.Cancel(version=1,reason='Old record'),db,OWNER)
    assert error.value.status_code==409


def test_attendance_locks_cancellation_and_edit(db):
    r=api.create_roster(assignment(),db,OWNER);db.execute('insert into attendance values(1,:id)',{'id':r['id']});db.commit()
    with pytest.raises(HTTPException):api.cancel_roster(r['id'],service.Cancel(version=1,reason='Client cancelled'),db,OWNER)
    with pytest.raises(HTTPException):api.update_roster(r['id'],service.Update(site_id=1,guard_id=1,date=TODAY,shift_type='DAY',version=1,reason='Changed shift'),db,OWNER)


def test_repeat_date_range_respects_weekdays(db):
    dates=[TODAY+timedelta(days=i) for i in range(7)]
    repeat=service.Repeat(site_id=1,guard_id=1,start=TODAY,end=dates[-1],shift_type='DAY',weekdays=[0,2,4])
    result=api.repeat_roster(repeat,db,OWNER)
    assert result['created']==3
    assert len(db.execute('select * from roster_history').all())==3


def test_repeat_conflict_rolls_back_all_dates(db):
    api.create_roster(assignment(),db,OWNER)
    with pytest.raises(HTTPException):api.repeat_roster(service.Repeat(site_id=1,guard_id=1,start=TODAY,end=TODAY+timedelta(days=4),shift_type='DAY'),db,OWNER)
    assert len(db.execute('select * from shift_rosters').all())==1


def test_future_expiry_blocks_repeat_without_partial_schedules(db):
    db.execute("update employee_documents set expiry_date=:expiry where document_type='MEDICAL_FITNESS'",{'expiry':(TODAY+timedelta(days=2)).isoformat()});db.commit()
    with pytest.raises(HTTPException):api.repeat_roster(service.Repeat(site_id=1,guard_id=1,start=TODAY,end=TODAY+timedelta(days=4),shift_type='DAY'),db,OWNER)
    assert not db.execute('select * from shift_rosters').all()


@pytest.mark.parametrize('table,change',[('employees',"status='PENDING_APPROVAL'"),('employee_joining_drafts',"status='DRAFT'"),('guard_profiles',"status='BENCH'"),('clients','is_active=false'),('sites','is_active=false'),('sites',"branch='OTHER'"),('sites','client_id=2')])
def test_ineligible_employee_or_site_blocked(db,table,change):
    db.execute('insert into clients values(2,1,\'Other client\')');db.execute(f'update {table} set {change}');db.commit()
    with pytest.raises(HTTPException):api.create_roster(assignment(),db,OWNER)


def test_gunman_without_verified_current_licence_blocked(db):
    db.execute("update employees set category='GUNMAN'");db.commit()
    with pytest.raises(HTTPException) as error:api.create_roster(assignment(),db,OWNER)
    assert 'GUN_LICENSE' in error.value.detail


def test_linked_contract_must_cover_date(db):
    db.execute('insert into client_contracts values(1,\'ACTIVE\',:start,:end,:profile)',{'start':(TODAY-timedelta(days=10)).isoformat(),'end':(TODAY-timedelta(days=1)).isoformat(),'profile':json.dumps({'service_verticals':['SECURITY']})});db.execute('update sites set contract_id=1');db.commit()
    with pytest.raises(HTTPException):api.create_roster(assignment(),db,OWNER)


def test_shortfall_includes_general_and_blocked_rosters(db):
    db.execute('update sites set shift_requirements=:json',{'json':json.dumps({'general_shift_personnel':2})});db.commit()
    api.create_roster(assignment(),db,OWNER)
    rows=api.shortfall_analysis(TODAY,db,OWNER);general=next(r for r in rows if r['shift_type']=='GENERAL');assert general['vacancy']==1
    db.execute("update employee_documents set verification_status='REJECTED' where document_type='MEDICAL_FITNESS'");db.commit()
    general=next(r for r in api.shortfall_analysis(TODAY,db,OWNER) if r['shift_type']=='GENERAL');assert general['vacancy']==2;assert general['blocked_assignments']==1


def test_past_and_unknown_fields_rejected(db):
    with pytest.raises(HTTPException):api.create_roster(service.Assignment(site_id=1,guard_id=1,date=TODAY-timedelta(days=1),shift_type='DAY'),db,OWNER)
    with pytest.raises(ValidationError):service.Assignment(site_id=1,guard_id=1,date=TODAY,shift_type='DAY',status='COMPLETED')
    with pytest.raises(ValidationError):service.Repeat(site_id=1,guard_id=1,start=TODAY,end=TODAY+timedelta(days=40),shift_type='DAY')


def test_cancel_routes_require_edit_instead_of_create():
    from starlette.requests import Request
    from app.api.deps import _request_permission
    assert _request_permission(Request({'type':'http','method':'POST','path':'/api/v1/erp/rosters/1/cancel','headers':[]}))=='rosters.edit'
