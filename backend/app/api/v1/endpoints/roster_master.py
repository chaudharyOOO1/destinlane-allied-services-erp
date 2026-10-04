from datetime import date
from fastapi import APIRouter,Depends,Query,HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import require_ops_or_admin
from app.core.database import get_db
from app.core.business_time import business_date
from app.services.roster_deployment import Assignment,Update,Cancel,Repeat,deployable,validate_assignment,insert,editable,audit,site_for,conflict

router=APIRouter()

@router.get('')
def list_rosters(start:date|None=None,end:date|None=None,site_id:int|None=None,status:str|None=None,db:Session=Depends(get_db),current_user=Depends(require_ops_or_admin)):
    sql="""select r.*,s.site_name,s.site_code,s.branch,c.company_name as client_name,e.id as employee_id,e.employee_code,e.name from shift_rosters r join sites s on s.id=r.site_id join clients c on c.id=s.client_id join guard_profiles g on g.id=r.guard_id join employees e on e.id=g.employee_id where (cast(:start as date) is null or r.date>=:start) and (cast(:end as date) is null or r.date<=:end) and (cast(:site as integer) is null or r.site_id=:site) and (cast(:status as text) is null or r.status=:status) order by r.date desc,r.id desc"""
    return [dict(r) for r in db.execute(text(sql),{'start':start,'end':end,'site':site_id,'status':status}).mappings()]

@router.get('/options')
def options(db:Session=Depends(get_db),current_user=Depends(require_ops_or_admin)):
    return {'sites':[dict(r) for r in db.execute(text('select s.id,s.site_name,s.site_code,s.branch,s.client_id,c.company_name as client_name from sites s join clients c on c.id=s.client_id where s.is_active=true and c.is_active=true order by s.site_name')).mappings()]}

@router.get('/employees')
def roster_employees(assignment_date:date|None=None,site_id:int|None=None,exclude_roster_id:int=0,db:Session=Depends(get_db),current_user=Depends(require_ops_or_admin)):
    target=assignment_date or business_date();result=[]
    ids=db.execute(text("select g.id from guard_profiles g join employees e on e.id=g.employee_id where cast(g.status as text)='ACTIVE' and upper(e.status)='ACTIVE' order by e.name")).mappings()
    for g in ids:
        try:
            person=deployable(db,g['id'],target)
            if site_id: site_for(db,site_id,person,target)
            conflict(db,g['id'],target,exclude_roster_id)
            result.append({'guard_id':g['id'],'employee_id':person['employee_id'],'employee_code':person['employee_code'],'name':person['name'],'category':person['category'],'branch':person['branch'],'client_id':person['client_id']})
        except HTTPException: continue
    return result

@router.get('/shortfall-analysis')
def shortfall_analysis(analysis_date:date|None=None,db:Session=Depends(get_db),current_user=Depends(require_ops_or_admin)):
    target=analysis_date or business_date();result=[]
    sites=db.execute(text('select s.id,s.site_name,s.site_code,s.shift_requirements from sites s join clients c on c.id=s.client_id where s.is_active=true and c.is_active=true order by s.site_name')).mappings().all()
    for s in sites:
        for shift,key in [('DAY','day_shift_guards'),('NIGHT','night_shift_guards'),('GENERAL','general_shift_personnel')]:
            required=int((s['shift_requirements'] or {}).get(key) or 0)
            roster=db.execute(text("select guard_id from shift_rosters where site_id=:site and date=:date and shift_type=:shift and status in ('SCHEDULED','COMPLETED')"),{'site':s['id'],'date':target,'shift':shift}).mappings().all()
            active=0
            for r in roster:
                try: person=deployable(db,r['guard_id'],target);site_for(db,s['id'],person,target);active+=1
                except HTTPException: pass
            result.append({'site_id':s['id'],'site_name':s['site_name'],'site_code':s['site_code'],'date':target,'shift_type':shift,'required':required,'active':active,'blocked_assignments':len(roster)-active,'vacancy':max(0,required-active),'surplus':max(0,active-required)})
    return result

# Shared attendance gate retains the existing call signature.
def _assert_deployable(db,guard_id:int,roster_id:int|None=None):return deployable(db,guard_id)

@router.post('',status_code=201)
def create_roster(data:Assignment,db:Session=Depends(get_db),current_user=Depends(require_ops_or_admin)):
    try: validate_assignment(db,data);record=insert(db,data,current_user);db.commit();return record
    except IntegrityError: db.rollback();raise HTTPException(409,'Employee already has an active deployment on this date.')

@router.post('/repeat',status_code=201)
def repeat_roster(data:Repeat,db:Session=Depends(get_db),current_user=Depends(require_ops_or_admin)):
    assignments=[Assignment(site_id=data.site_id,guard_id=data.guard_id,date=d,shift_type=data.shift_type,notes=data.notes) for d in data.dates()]
    try:
        for a in assignments: validate_assignment(db,a)
        records=[insert(db,a,current_user) for a in assignments];db.commit();return {'created':len(records),'assignments':records}
    except (HTTPException,IntegrityError) as exc:
        db.rollback()
        if isinstance(exc,HTTPException): raise
        raise HTTPException(409,'Repeat scheduling conflicts with an existing deployment. No assignments were added.')

@router.patch('/{roster_id}')
def update_roster(roster_id:int,data:Update,db:Session=Depends(get_db),current_user=Depends(require_ops_or_admin)):
    old=editable(db,roster_id,data.version)
    try:
        validate_assignment(db,data,roster_id)
        record=dict(db.execute(text('update shift_rosters set site_id=:site_id,guard_id=:guard_id,date=:date,shift_type=:shift_type,notes=:notes,version=version+1,updated_at=now(),updated_by=:user where id=:id returning *'),{**data.model_dump(exclude={'reason','version'}),'user':current_user.id,'id':roster_id}).mappings().one())
        audit(db,record,current_user,'CHANGE',data.reason,old);db.commit();return record
    except IntegrityError: db.rollback();raise HTTPException(409,'The changed deployment conflicts with an existing assignment.')

@router.post('/{roster_id}/cancel')
def cancel_roster(roster_id:int,data:Cancel,db:Session=Depends(get_db),current_user=Depends(require_ops_or_admin)):
    old=editable(db,roster_id,data.version)
    record=dict(db.execute(text("update shift_rosters set status='CANCELLED',version=version+1,updated_at=now(),updated_by=:user where id=:id returning *"),{'id':roster_id,'user':current_user.id}).mappings().one())
    audit(db,record,current_user,'CANCEL',data.reason,old);db.commit();return record

@router.get('/{roster_id}/history')
def history(roster_id:int,db:Session=Depends(get_db),current_user=Depends(require_ops_or_admin)):
    return [dict(r) for r in db.execute(text('select h.*,u.full_name as changed_by_name from roster_history h left join users u on u.id=h.changed_by where roster_id=:id order by h.id desc'),{'id':roster_id}).mappings()]
