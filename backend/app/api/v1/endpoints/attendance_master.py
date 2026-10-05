from uuid import UUID
from datetime import date
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.api.deps import require_ops_or_admin,require_admin_or_staff,require_owner
from app.api.permissions import has_permission
from app.core.database import get_db
from app.core.security import get_password_hash
from app.core.supabase_auth import create_supabase_signed_url
from app.models.user import User
from app.services import attendance as rules

router=APIRouter()

@router.get('')
def list_attendance(start:date|None=None,end:date|None=None,site_id:int|None=Query(default=None,gt=0),db:Session=Depends(get_db),current_user=Depends(require_ops_or_admin)):
    if start and end and end<start:raise HTTPException(422,'End date must follow start date.')
    sql='''select a.*,e.employee_code,e.name,r.shift_type,s.site_name from attendance a join employees e on e.id=a.employee_id left join shift_rosters r on r.id=a.roster_id left join sites s on s.id=r.site_id where (:start is null or a.attendance_date>=:start) and (:end is null or a.attendance_date<=:end) and (:site is null or r.site_id=:site) order by a.attendance_date desc,a.created_at desc limit 1000'''
    # Explicit casts avoid PostgreSQL's untyped NULL parameter ambiguity.
    sql=sql.replace(':start is null','cast(:start as date) is null').replace(':end is null','cast(:end as date) is null').replace(':site is null','cast(:site as integer) is null')
    return [rules.public(r) for r in db.execute(text(sql),{'start':start,'end':end,'site':site_id}).mappings().all()]

@router.get('/reports/export')
def export_attendance(start:date|None=None,end:date|None=None,site_id:int|None=Query(default=None,gt=0),db:Session=Depends(get_db),current_user=Depends(require_ops_or_admin)):
    import csv,io
    from fastapi.responses import Response
    from app.services.employee_reports import safe_cell
    records=list_attendance(start,end,site_id,db,current_user)
    fields=['attendance_date','employee_code','name','site_name','shift_type','status','check_in_time','check_out_time','shift_hours','overtime_hours','late_minutes','verification_status','source']
    output=io.StringIO();writer=csv.writer(output);writer.writerow(fields)
    for record in records:writer.writerow([safe_cell(record.get(k,'')) for k in fields])
    return Response(content='\ufeff'+output.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="DestinLane_Attendance.csv"'})

@router.get('/options')
def options(db:Session=Depends(get_db),current_user=Depends(require_ops_or_admin)):
    users=db.query(User).filter(User.is_active.is_(True)).all()
    return {'sites':[dict(r) for r in db.execute(text('select id,site_name,site_code from sites where is_active=true order by site_name')).mappings().all()],
      'rules':[dict(r) for r in db.execute(text('select * from attendance_shift_rules order by site_id,shift_type')).mappings().all()],
      'approvers':[{'id':u.id,'name':u.full_name or u.login_id} for u in users if has_permission(db,u,'attendance.approve')],
      'employees':[dict(r) for r in db.execute(text("select e.id,e.name,e.employee_code,(a.employee_id is not null) access_enabled,(d.employee_id is not null) device_bound from employees e left join employee_attendance_access a on a.employee_id=e.id left join employee_device_bindings d on d.employee_id=e.id where upper(e.status)='ACTIVE' order by e.name")).mappings().all()] if current_user.role.value=='OWNER' else []}

@router.put('/rules')
def save_rule(payload:rules.Rule,db:Session=Depends(get_db),current_user=Depends(require_owner)):
    # Serialize initial inserts as well as edits to a shift rule.
    if not rules.row(db,'select id from sites where id=:id and is_active=true for update',{'id':payload.site_id}):raise HTTPException(404,'Active site not found.')
    old=rules.row(db,'select * from attendance_shift_rules where site_id=:site and shift_type=:shift',{'site':payload.site_id,'shift':payload.shift_type})
    if (old['version'] if old else 0)!=payload.version:raise HTTPException(409,'Shift rule changed. Refresh first.')
    params={**payload.model_dump(exclude={'reason','version'}),'user':current_user.id}
    new=db.execute(text('''insert into attendance_shift_rules(site_id,shift_type,start_time,duty_hours,grace_minutes,updated_by) values(:site_id,:shift_type,:start_time,:duty_hours,:grace_minutes,:user) on conflict(site_id,shift_type) do update set start_time=:start_time,duty_hours=:duty_hours,grace_minutes=:grace_minutes,updated_by=:user,updated_at=now(),version=attendance_shift_rules.version+1 returning *'''),params).mappings().one()
    rules.audit(db,'SHIFT_RULE_CHANGED',user=current_user,before=dict(old) if old else None,after=dict(new),reason=payload.reason);db.commit();return dict(new)

@router.get('/correction-rosters')
def correction_rosters(roster_date:date,db:Session=Depends(get_db),current_user=Depends(require_ops_or_admin)):
    return [dict(r) for r in db.execute(text("select r.id,r.date,r.shift_type,r.status,e.name,e.employee_code,s.site_name,coalesce(a.version,0) attendance_version from shift_rosters r join guard_profiles g on g.id=r.guard_id join employees e on e.id=g.employee_id join sites s on s.id=r.site_id left join attendance a on a.roster_id=r.id where r.date=:date and r.status<>'CANCELLED' order by e.name"),{'date':roster_date}).mappings().all()]

@router.get('/corrections')
def corrections(db:Session=Depends(get_db),current_user=Depends(require_ops_or_admin)):
    return [dict(r) for r in db.execute(text('''select c.*,e.name,e.employee_code,r.date,s.site_name from attendance_corrections c join shift_rosters r on r.id=c.roster_id join guard_profiles g on g.id=r.guard_id join employees e on e.id=g.employee_id join sites s on s.id=r.site_id order by c.created_at desc limit 1000''')).mappings().all()]

@router.post('/corrections')
def request_correction(payload:rules.Correction,db:Session=Depends(get_db),current_user=Depends(require_ops_or_admin)):
    approver=db.get(User,payload.assigned_to)
    if not approver or not has_permission(db,approver,'attendance.approve'):raise HTTPException(422,'Select an active reviewer with attendance approval access.')
    if approver.id==current_user.id and current_user.role.value!='OWNER':raise HTTPException(422,'Select a different reviewer.')
    try:result=rules.request_correction(db,payload,current_user,approver);db.commit();return result
    except Exception:db.rollback();raise

@router.post('/corrections/{request_id}/decision')
def decide_correction(request_id:UUID,payload:rules.Decision,db:Session=Depends(get_db),current_user=Depends(require_ops_or_admin)):
    try:result=rules.decide_correction(db,str(request_id),payload,current_user);db.commit();return result
    except Exception:db.rollback();raise

@router.post('/employees/{employee_id}/access')
def set_access(employee_id:UUID,payload:rules.Access,db:Session=Depends(get_db),current_user=Depends(require_owner)):
    person=rules.row(db,"select id from employees where id=:id and upper(status)='ACTIVE' for update",{'id':str(employee_id)})
    if not person:raise HTTPException(404,'Active employee not found.')
    db.execute(text('''insert into employee_attendance_access(employee_id,pin_hash,updated_by) values(:id,:hash,:user) on conflict(employee_id) do update set pin_hash=:hash,session_version=employee_attendance_access.session_version+1,failed_attempts=0,locked_until=null,updated_by=:user,updated_at=now()'''),{'id':str(employee_id),'hash':get_password_hash(payload.pin),'user':current_user.id})
    rules.audit(db,'EMPLOYEE_ACCESS_RESET',str(employee_id),user=current_user,reason=payload.reason);db.commit();return {'message':'Employee PIN saved; previous sessions revoked.'}

@router.post('/employees/{employee_id}/reset-device')
def reset_device(employee_id:UUID,payload:rules.Reason,db:Session=Depends(get_db),current_user=Depends(require_owner)):
    if not rules.row(db,'select id from employees where id=:id for update',{'id':str(employee_id)}):raise HTTPException(404,'Employee not found.')
    if rules.row(db,'select id from attendance where employee_id=:id and check_in_time is not null and check_out_time is null',{'id':str(employee_id)}):raise HTTPException(409,'Resolve the open shift through a correction before changing devices.')
    db.execute(text('delete from employee_device_bindings where employee_id=:id'),{'id':str(employee_id)})
    db.execute(text('update employee_attendance_access set session_version=session_version+1 where employee_id=:id'),{'id':str(employee_id)})
    rules.audit(db,'DEVICE_RESET',str(employee_id),user=current_user,reason=payload.reason);db.commit();return {'message':'Device reset. Employee must sign in again.'}

@router.get('/my-rosters')
def my_rosters(db:Session=Depends(get_db),current_user=Depends(require_admin_or_staff)):
    return [dict(r) for r in db.execute(text("""select r.id,r.date,r.shift_type,s.site_name,a.id attendance_id,a.check_in_time,a.check_out_time,a.verification_status from shift_rosters r join guard_profiles g on g.id=r.guard_id join sites s on s.id=r.site_id left join attendance a on a.roster_id=r.id where g.user_id=:user and r.status='SCHEDULED' and (r.date>=:today or (a.check_in_time is not null and a.check_out_time is null)) order by r.date limit 31"""),{'user':current_user.id,'today':rules.business_date()}).mappings().all()]

@router.post('/punch')
def punch_attendance(payload:rules.Punch,db:Session=Depends(get_db),current_user=Depends(require_admin_or_staff)):
    # Administrators use audited correction requests, never impersonate a GPS punch.
    employee=rules.row(db,'select employee_id from guard_profiles where user_id=:user',{'user':current_user.id})
    if not employee:raise HTTPException(403,'An assigned workforce employee account is required to punch attendance.')
    try:result=rules.punch(db,payload,employee['employee_id'],current_user);db.commit();return result
    except Exception:db.rollback();raise

@router.get('/{attendance_id}/history')
def history(attendance_id:UUID,db:Session=Depends(get_db),current_user=Depends(require_ops_or_admin)):
    if not rules.row(db,'select id from attendance where id=:id',{'id':str(attendance_id)}):raise HTTPException(404,'Attendance not found.')
    return [dict(r) for r in db.execute(text('select * from attendance_history where attendance_id=:id order by id desc'),{'id':str(attendance_id)}).mappings().all()]

@router.post('/{attendance_id}/selfie/{kind}/sign')
def sign_selfie(attendance_id:UUID,kind:str,db:Session=Depends(get_db),current_user=Depends(require_ops_or_admin)):
    if kind not in {'check-in','check-out'}:raise HTTPException(422,'Select check-in or check-out.')
    record=rules.row(db,'select * from attendance where id=:id',{'id':str(attendance_id)})
    path=record.get('check_in_selfie_url' if kind=='check-in' else 'check_out_selfie_url') if record else None
    if not path or str(path).startswith('http'):raise HTTPException(404,'No private selfie is available for this punch.')
    url=create_supabase_signed_url(bucket='employee-selfies',path=path,expires_in=60)
    if not url:raise HTTPException(503,'Selfie storage is temporarily unavailable.')
    return {'url':url,'expires_in':60}

@router.post('/{attendance_id}/review')
def review(attendance_id:UUID,payload:rules.Review,db:Session=Depends(get_db),current_user=Depends(require_ops_or_admin)):
    record=rules.row(db,'select * from attendance where id=:id',{'id':str(attendance_id)})
    if not record:raise HTTPException(404,'Attendance not found.')
    r=rules.roster(db,record['roster_id']);rules.unlocked(db,r)
    record=rules.record_for(db,r['id'])
    if record['version']!=payload.version:raise HTTPException(409,'Attendance changed. Refresh before reviewing.')
    if record['verification_status']!='PENDING_REVIEW' or not record['check_out_time']:raise HTTPException(409,'Only completed punches awaiting review can be decided.')
    if r['user_id']==current_user.id and current_user.role.value!='OWNER':raise HTTPException(403,'Employees cannot review their own attendance.')
    after=db.execute(text("update attendance set verification_status=:status,verified_at=:now,updated_at=:now,version=version+1 where id=:id returning *"),{'status':'VERIFIED' if payload.decision=='APPROVE' else 'REJECTED','now':rules.now(),'id':str(attendance_id)}).mappings().one()
    rules.audit(db,'PUNCH_'+payload.decision,record['employee_id'],record['id'],current_user,reason=payload.reason,version=after['version']);db.commit();return rules.public(after)

@router.patch('/{attendance_id}')
def update_attendance(attendance_id:str,payload:dict,db:Session=Depends(get_db),current_user=Depends(require_ops_or_admin)):
    raise HTTPException(409,'Direct attendance edits are closed. Submit an assigned correction request.')
