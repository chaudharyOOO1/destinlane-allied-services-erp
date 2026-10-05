"""One server-clock attendance flow for the office portal and employee application."""
import hashlib,json
from datetime import date,datetime,time,timedelta,timezone
from typing import Literal
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field,model_validator
from sqlalchemy import text
from app.core.business_time import business_date
from app.core.geofence import validate_geofence
from app.services.roster_deployment import deployable,site_for,row

IST=ZoneInfo('Asia/Kolkata')
class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True,allow_inf_nan=False)
class Punch(Strict):
    roster_id:int|None=Field(default=None,gt=0)
    action:Literal['CHECK_IN','CHECK_OUT']
    latitude:float=Field(ge=-90,le=90)
    longitude:float=Field(ge=-180,le=180)
    accuracy:float=Field(gt=0,le=100)
    device_id:str=Field(min_length=8,max_length=255)
    check_in_selfie_path:str|None=Field(default=None,max_length=500)
    check_out_selfie_path:str|None=Field(default=None,max_length=500)
    @model_validator(mode='after')
    def proof(self):
        if self.action=='CHECK_IN' and (not self.check_in_selfie_path or self.check_out_selfie_path): raise ValueError('Check-in requires its own selfie.')
        if self.action=='CHECK_OUT' and (not self.check_out_selfie_path or self.check_in_selfie_path): raise ValueError('Check-out requires its own selfie.')
        return self
class Rule(Strict):
    site_id:int=Field(gt=0)
    shift_type:Literal['DAY','NIGHT','GENERAL']
    start_time:time
    duty_hours:float=Field(gt=0,le=16)
    grace_minutes:int=Field(default=15,ge=0,le=120)
    version:int=Field(default=0,ge=0)
    reason:str=Field(min_length=3,max_length=1000)
class Review(Strict):
    version:int=Field(gt=0)
    decision:Literal['APPROVE','REJECT']
    reason:str=Field(min_length=3,max_length=1000)
class Correction(Strict):
    roster_id:int=Field(gt=0)
    version:int=Field(ge=0)
    assigned_to:int=Field(gt=0)
    reason:str=Field(min_length=3,max_length=1000)
    status:Literal['present','late','absent','leave']
    check_in_time:datetime|None=None
    check_out_time:datetime|None=None
    @model_validator(mode='after')
    def valid_times(self):
        if self.status in {'absent','leave'}:
            if self.check_in_time or self.check_out_time: raise ValueError('Absent/leave records cannot have worked hours.')
        else:
            if not self.check_in_time or not self.check_out_time: raise ValueError('Present/late corrections require both punch times.')
            if not self.check_in_time.tzinfo or not self.check_out_time.tzinfo: raise ValueError('Punch times must include their timezone.')
            if not 0<(self.check_out_time-self.check_in_time).total_seconds()<=86400: raise ValueError('Worked time must be greater than zero and at most 24 hours.')
        return self
class Decision(Strict):
    decision:Literal['APPROVE','REJECT']
    reason:str=Field(min_length=3,max_length=1000)
class Reason(Strict):
    reason:str=Field(min_length=3,max_length=1000)
class Access(Reason):
    pin:str=Field(pattern=r'^\d{8,12}$')


def now():return datetime.now(timezone.utc)
def stamp(value):
    if isinstance(value,str):value=datetime.fromisoformat(value)
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
def day(value):return date.fromisoformat(value) if isinstance(value,str) else value

def public(record):
    item=dict(record)
    for key in ['device_id_hash','check_in_selfie_url','check_out_selfie_url','policy_snapshot']:
        item.pop(key,None)
    item['has_check_in_selfie']=bool(record.get('check_in_selfie_url'))
    item['has_check_out_selfie']=bool(record.get('check_out_selfie_url'))
    return item

def audit(db,action,employee_id=None,attendance_id=None,user=None,**details):
    db.execute(text('insert into attendance_history(attendance_id,employee_id,changed_by,action,details) values (:attendance,:employee,:user,:action,cast(:details as jsonb))'),{'attendance':attendance_id,'employee':employee_id,'user':user.id if user else None,'action':action,'details':json.dumps(details,default=str)})

def roster(db,rid):
    r=row(db,"select r.*,g.employee_id,g.user_id,s.latitude site_lat,s.longitude site_lng,coalesce(s.geofence_radius_meters,100) radius_m from shift_rosters r join guard_profiles g on g.id=r.guard_id join sites s on s.id=r.site_id where r.id=:id for update of r",{'id':rid})
    if not r:raise HTTPException(404,'Roster not found.')
    return r

def rule_for(db,r):
    rule=row(db,'select * from attendance_shift_rules where site_id=:site and shift_type=:shift',{'site':r['site_id'],'shift':r['shift_type']})
    if not rule:raise HTTPException(409,'Configure the attendance start time and duty hours for this site and shift first.')
    return rule

def record_for(db,rid):return row(db,'select * from attendance where roster_id=:id for update',{'id':rid})
def unlocked(db,r):
    # Once a month has been calculated, changing attendance would silently invalidate payroll.
    if row(db,"select pr.id from payroll_runs pr join salary_slips ss on ss.payroll_run_id=pr.id where ss.employee_id=:employee and pr.payroll_month=:month and pr.status not in ('DRAFT','CANCELLED')",{'employee':str(r['employee_id']),'month':day(r['date']).replace(day=1)}):raise HTTPException(409,'Attendance is locked by a payroll run. Resolve that run before changing attendance.')

def hours(start,end,duty):
    elapsed=(stamp(end)-stamp(start)).total_seconds()/3600
    if not 0<elapsed<=24:raise HTTPException(422,'Worked time must be greater than zero and at most 24 hours; request a correction for an overdue shift.')
    regular=round(min(elapsed,float(duty)),2)
    return regular,round(max(round(elapsed,2)-regular,0),2)

def punch(db,payload,employee_id,user=None):
    clock=now();today=clock.astimezone(IST).date()
    if payload.roster_id is None:
        if payload.action=='CHECK_OUT':
            found=row(db,"select r.id from shift_rosters r join attendance a on a.roster_id=r.id where a.employee_id=:employee and a.check_in_time is not null and a.check_out_time is null and r.status='SCHEDULED' order by r.date limit 1",{'employee':str(employee_id)})
        else:
            found=row(db,"select r.id from shift_rosters r join guard_profiles g on g.id=r.guard_id where g.employee_id=:employee and r.date=:today and r.status='SCHEDULED'",{'employee':str(employee_id),'today':today})
        if not found:raise HTTPException(409,'No eligible roster found for this punch.')
        rid=found['id']
    else:rid=payload.roster_id
    r=roster(db,rid)
    if str(r['employee_id'])!=str(employee_id):raise HTTPException(403,'Only the assigned employee can punch this roster.')
    if r['status']!='SCHEDULED':raise HTTPException(409,'This roster is no longer scheduled.')
    unlocked(db,r)
    existing=record_for(db,rid)
    if payload.action=='CHECK_IN':
        if existing:raise HTTPException(409,'Attendance already exists. Check out or request a correction.')
        if day(r['date'])!=today:raise HTTPException(409,'Check-in is allowed only on the roster date in India.')
        person=deployable(db,r['guard_id'],today,True);site_for(db,r['site_id'],person,today,True)
        if row(db,'select id from attendance where employee_id=:employee and check_in_time is not null and check_out_time is null',{'employee':str(employee_id)}):raise HTTPException(409,'Close the previous open shift before checking in again.')
        policy=rule_for(db,r)
    else:
        if not existing or not existing['check_in_time'] or existing['check_out_time']:raise HTTPException(409,'An open check-in is required before checking out.')
        policy=existing['policy_snapshot']
        if isinstance(policy,str):policy=json.loads(policy)
    if r['site_lat'] is None or r['site_lng'] is None:raise HTTPException(409,'Site GPS coordinates are not configured.')
    within,distance=validate_geofence(float(r['site_lat']),float(r['site_lng']),payload.latitude,payload.longitude,float(r['radius_m']))
    if not within or payload.accuracy>float(r['radius_m']):raise HTTPException(400,'GPS location or accuracy is outside the site geofence. Move closer and retry.')
    digest=hashlib.sha256(payload.device_id.encode()).hexdigest()
    # The employee row serializes the first device binding across different roster days.
    row(db,'select id from employees where id=:id for update',{'id':str(employee_id)})
    binding=row(db,'select * from employee_device_bindings where employee_id=:id',{'id':str(employee_id)})
    if binding and binding['device_hash']!=digest:raise HTTPException(409,'Device mismatch. Ask the owner to reset your registered device.')
    path=payload.check_in_selfie_path if payload.action=='CHECK_IN' else payload.check_out_selfie_path
    proof=row(db,'select * from attendance_selfies where storage_path=:path and employee_id=:employee for update',{'path':path,'employee':str(employee_id)})
    kind='check-in' if payload.action=='CHECK_IN' else 'check-out'
    if not proof or proof['kind']!=kind or proof['used_at'] or not timedelta(0)<=clock-stamp(proof['created_at'])<=timedelta(minutes=10):raise HTTPException(422,'Upload a fresh selfie for this punch. Selfies cannot be reused.')
    if not binding:db.execute(text('insert into employee_device_bindings(employee_id,device_hash) values (:id,:hash)'),{'id':str(employee_id),'hash':digest})
    common={'roster':rid,'employee':str(employee_id),'date':day(r['date']),'now':clock,'lat':payload.latitude,'lng':payload.longitude,'accuracy':payload.accuracy,'distance':distance,'hash':digest,'selfie':path}
    if payload.action=='CHECK_IN':
        start=policy['start_time'];start=time.fromisoformat(start) if isinstance(start,str) else start
        expected=datetime.combine(today,start,IST)
        # A shift cannot be opened many hours before its configured start.
        if clock<expected-timedelta(hours=2):raise HTTPException(409,'Check-in opens two hours before the configured shift start.')
        late=max(0,int((clock-expected-timedelta(minutes=policy['grace_minutes'])).total_seconds()//60))
        record=dict(db.execute(text("""insert into attendance(roster_id,employee_id,attendance_date,status,check_in_time,check_in_selfie_url,check_in_latitude,check_in_longitude,check_in_accuracy,check_in_lat,check_in_lng,check_in_distance_m,device_id_hash,is_geofence_verified,verification_status,is_late_punch,late_minutes,night_shift,source,duty_hours,policy_snapshot,shift_hours,overtime_hours) values (:roster,:employee,:date,:status,:now,:selfie,:lat,:lng,:accuracy,:lat,:lng,:distance,:hash,true,'OPEN',:is_late,:late,:night,'MOBILE',:duty,cast(:policy as jsonb),0,0) returning *"""),{**common,'status':'late' if late else 'present','late':late,'is_late':late>0,'night':r['shift_type']=='NIGHT','duty':policy['duty_hours'],'policy':json.dumps(dict(policy),default=str)}).mappings().one())
    else:
        regular,ot=hours(existing['check_in_time'],clock,existing['duty_hours'])
        record=dict(db.execute(text("""update attendance set check_out_time=:now,check_out_selfie_url=:selfie,check_out_latitude=:lat,check_out_longitude=:lng,check_out_accuracy=:accuracy,check_out_lat=:lat,check_out_lng=:lng,check_out_distance_m=:distance,shift_hours=:regular,overtime_hours=:ot,verification_status='PENDING_REVIEW',submitted_at=:now,updated_at=:now,version=version+1 where id=:id returning *"""),{**common,'id':existing['id'],'regular':regular,'ot':ot}).mappings().one())
        db.execute(text("update shift_rosters set status='COMPLETED',version=version+1,updated_at=:now where id=:id"),{'now':clock,'id':rid})
    db.execute(text('update attendance_selfies set used_at=:now where id=:id'),{'now':clock,'id':proof['id']})
    audit(db,payload.action,employee_id,record['id'],user,roster_id=rid,version=record['version'],distance_m=distance)
    return {**public(record),'action':payload.action,'distance_m':distance}


def request_correction(db,data,user,approver):
    r=roster(db,data.roster_id);unlocked(db,r)
    if r['status']=='CANCELLED' or day(r['date'])>business_date():raise HTTPException(409,'Corrections require a current or past, non-cancelled roster.')
    existing=record_for(db,r['id'])
    if (existing['version'] if existing else 0)!=data.version:raise HTTPException(409,'Attendance changed. Refresh before submitting.')
    if row(db,"select id from attendance_corrections where roster_id=:id and status='PENDING'",{'id':r['id']}):raise HTTPException(409,'This roster already has a pending correction.')
    if data.status in {'present','late'}:
        if data.check_in_time.astimezone(IST).date()!=day(r['date']) or data.check_out_time>now():raise HTTPException(422,'Times must start on the roster date and cannot be in the future.')
        rule_for(db,r)
    proposed=data.model_dump(mode='json',exclude={'reason','assigned_to','version','roster_id'})
    if data.status in {'present','late'}:
        policy=existing.get('policy_snapshot') if existing else None
        if isinstance(policy,str):policy=json.loads(policy)
        proposed['shift_policy']=dict(policy or rule_for(db,r))
    result=dict(db.execute(text('insert into attendance_corrections(roster_id,base_version,proposed,reason,assigned_to,submitted_by) values (:roster,:version,cast(:proposed as jsonb),:reason,:assigned,:user) returning *'),{'roster':r['id'],'version':data.version,'proposed':json.dumps(proposed,default=str),'reason':data.reason,'assigned':approver.id,'user':user.id}).mappings().one())
    audit(db,'CORRECTION_REQUEST',r['employee_id'],existing['id'] if existing else None,user,request_id=result['id'],reason=data.reason,proposed=proposed)
    return result


def decide_correction(db,rid,data,user):
    request=row(db,'select * from attendance_corrections where id=:id for update',{'id':rid})
    if not request:raise HTTPException(404,'Correction request not found.')
    if request['status']!='PENDING':raise HTTPException(409,'This request was already decided.')
    owner=user.role.value=='OWNER'
    if not owner and (request['assigned_to']!=user.id or request['submitted_by']==user.id):raise HTTPException(403,'Only the assigned reviewer can decide this request; submitters cannot approve their own correction.')
    r=roster(db,request['roster_id']);unlocked(db,r);existing=record_for(db,r['id'])
    if data.decision=='APPROVE':
        if (existing['version'] if existing else 0)!=request['base_version']:raise HTTPException(409,'Attendance changed since this request. Reject it and submit a fresh request.')
        p=request['proposed'];p=json.loads(p) if isinstance(p,str) else p
        regular=ot=0;duty=8;late=0
        if p['status'] in {'present','late'}:
            policy=p.get('shift_policy') or rule_for(db,r);duty=policy['duty_hours'];regular,ot=hours(p['check_in_time'],p['check_out_time'],duty)
            start=policy['start_time'];start=time.fromisoformat(start) if isinstance(start,str) else start
            late=max(0,int((stamp(p['check_in_time'])-datetime.combine(day(r['date']),start,IST)-timedelta(minutes=policy['grace_minutes'])).total_seconds()//60))
            if stamp(p['check_out_time'])>now():raise HTTPException(422,'Future attendance is not permitted.')
        if p['status'] in {'present','late'}:p['status']='late' if late else 'present'
        params={**p,'regular':regular,'ot':ot,'duty':duty,'now':now(),'roster':r['id'],'employee':str(r['employee_id']),'date':day(r['date']),'night':r['shift_type']=='NIGHT','late':late}
        before=public(existing) if existing else None
        if existing:
            after=dict(db.execute(text("update attendance set status=:status,check_in_time=:check_in_time,check_out_time=:check_out_time,shift_hours=:regular,overtime_hours=:ot,duty_hours=:duty,source='MANUAL_CORRECTION',is_geofence_verified=false,verification_status='VERIFIED',verified_at=:now,updated_at=:now,version=version+1,late_minutes=:late,is_late_punch=:is_late where id=:id returning *"),{**params,'id':existing['id'],'is_late':late>0}).mappings().one())
        else:
            after=dict(db.execute(text("insert into attendance(roster_id,employee_id,attendance_date,status,check_in_time,check_out_time,shift_hours,overtime_hours,duty_hours,source,is_geofence_verified,verification_status,verified_at,night_shift,is_late_punch,late_minutes) values (:roster,:employee,:date,:status,:check_in_time,:check_out_time,:regular,:ot,:duty,'MANUAL_CORRECTION',false,'VERIFIED',:now,:night,:is_late,:late) returning *"),{**params,'is_late':late>0}).mappings().one())
        db.execute(text("update shift_rosters set status='COMPLETED',version=version+1,updated_at=:now where id=:id"),{'now':now(),'id':r['id']})
        audit(db,'CORRECTION_APPROVED',r['employee_id'],after['id'],user,before=before,after=public(after),request_id=rid,reason=data.reason)
    else:audit(db,'CORRECTION_REJECTED',r['employee_id'],existing['id'] if existing else None,user,request_id=rid,reason=data.reason)
    result=db.execute(text('update attendance_corrections set status=:status,remarks=:reason,decided_by=:user,decided_at=:now where id=:id returning *'),{'status':'APPROVED' if data.decision=='APPROVE' else 'REJECTED','reason':data.reason,'user':user.id,'now':now(),'id':rid}).mappings().one()
    return dict(result)
