from datetime import date,timedelta
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.api.deps import require_hr_or_admin,require_admin
from app.core.database import get_db
from app.core.business_time import business_date
from app.services.employee_workflow import employee,compliance_reasons,refresh_compliance,audit

router=APIRouter()


def directory(db,q='',status=None,branch=None,site_id=None,designation=None):
    rows=db.execute(text("""select e.id,e.employee_code,e.name,e.father_name,e.phone,e.status,e.designation,e.branch,e.site_id,e.client_id,e.category,e.joining_date,e.intimation_id,e.version,e.created_at,
      case when e.aadhaar_no is null then null else 'XXXXXXXX'||right(e.aadhaar_no,4) end aadhaar_masked,
      c.company_name as client_name,s.site_name,d.status as joining_status
      from employees e left join clients c on c.id=e.client_id left join sites s on s.id=e.site_id left join employee_joining_drafts d on d.employee_id=e.id
      where (cast(:status as text) is null or upper(e.status)=upper(:status)) and (cast(:branch as text) is null or e.branch=:branch)
      and (cast(:site as integer) is null or e.site_id=:site) and (cast(:designation as text) is null or e.designation=:designation)
      and (:q='' or e.name ilike :search or e.employee_code ilike :search or e.phone ilike :search)
      order by e.created_at desc"""),{'status':status,'branch':branch,'site':site_id,'designation':designation,'q':q,'search':'%'+q+'%'}).mappings().all()
    return [dict(x) for x in rows]


@router.get('')
def list_employees(q:str=Query('',max_length=100),status:str|None=None,branch:str|None=None,site_id:int|None=None,designation:str|None=None,db:Session=Depends(get_db),user=Depends(require_hr_or_admin)):
    return directory(db,q,status,branch,site_id,designation)


@router.get('/options')
def options(db:Session=Depends(get_db),user=Depends(require_hr_or_admin)):
    from app.models.company import CompanySettings
    company=db.get(CompanySettings,1)
    clients=[dict(x) for x in db.execute(text('select id,company_name from clients where is_active=true order by company_name')).mappings()]
    sites=[dict(x) for x in db.execute(text('select id,site_name,client_id,branch from sites where is_active=true order by site_name')).mappings()]
    branches=[{'code':x['code'],'name':x['name']} for x in (company.profile.get('branches',[]) if company else []) if x.get('is_active',True)]
    approvers=[]
    if user.role.value=='OWNER':
        from app.models.user import User
        from app.api.permissions import has_permission
        approvers=[{'id':u.id,'name':u.full_name,'role':u.role.value} for u in db.query(User).filter(User.is_active.is_(True)).all() if u.role.value in {'OWNER','SUPER_ADMIN','ADMIN','HR'} and has_permission(db,u,'employees.approve') and has_permission(db,u,'employees.view')]
    return {'clients':clients,'sites':sites,'branches':branches,'approvers':approvers}


@router.get('/code-check')
def check_code(code:str=Query(...,max_length=40),db:Session=Depends(get_db),user=Depends(require_hr_or_admin)):
    import re
    value=code.strip().upper();row=db.execute(text('select id,employee_code,name,status from employees where employee_code=:code'),{'code':value}).mappings().first()
    return {'valid_format':bool(re.fullmatch(r'E-DAS-\d{4,}',value)),'registered':bool(row),'employee':dict(row) if row else None}


@router.get('/ifsc-check')
def check_ifsc(code:str=Query(...,max_length=11),db:Session=Depends(get_db),user=Depends(require_hr_or_admin)):
    row=db.execute(text('select ifsc_code,bank_name,branch_name from ifsc_master where ifsc_code=:code and approved=true'),{'code':code.strip().upper()}).mappings().first()
    return {'approved':bool(row),'bank':dict(row) if row else None}


def compliance_rows(db,days=60):
    rows=directory(db);cutoff=business_date()+timedelta(days=days)
    docs=db.execute(text("with current_docs as (select distinct on (employee_id,document_type) id,employee_id,document_type,expiry_date,verification_status from employee_documents order by employee_id,document_type,(verification_status='VERIFIED') desc,verified_at desc nulls last,created_at desc) select * from current_docs where expiry_date is not null and expiry_date<=:cutoff order by expiry_date"),{'cutoff':cutoff}).mappings().all()
    by_employee={}
    for d in docs: by_employee.setdefault(str(d['employee_id']),[]).append(dict(d))
    result=[]
    for row in rows:
        reasons=compliance_reasons(db,row['id'])
        reminders=by_employee.get(str(row['id']),[])
        if reasons or reminders: result.append({**row,'compliance_missing':reasons,'reminders':reminders,'bench_locked':bool(reasons),'joining_incomplete':row['joining_status']!='APPROVED'})
    return result


@router.get('/compliance')
def compliance(days:int=Query(60,ge=1,le=365),db:Session=Depends(get_db),user=Depends(require_hr_or_admin)): return compliance_rows(db,days)


@router.post('/{employee_id}/compliance-refresh')
def refresh(employee_id:UUID,db:Session=Depends(get_db),user=Depends(require_hr_or_admin)):
    result=refresh_compliance(db,employee_id);db.commit();return result


@router.get('/reports')
def reports(kind:str=Query('master',pattern='^(master|attendance|compliance)$'),start:date|None=None,end:date|None=None,days:int=Query(60,ge=1,le=365),q:str=Query('',max_length=100),branch:str|None=None,site_id:int|None=None,status:str|None=None,designation:str|None=None,db:Session=Depends(get_db),user=Depends(require_hr_or_admin)):
    selected=directory(db,q,status,branch,site_id,designation)
    if kind=='master': return selected
    if kind=='compliance':
        ids={str(r['id']) for r in selected}
        return [{**{k:v for k,v in r.items() if k!='reminders'},'missing_documents':', '.join(r['compliance_missing']),'expiry_alerts':'; '.join(d['document_type']+': '+str(d['expiry_date']) for d in r['reminders'])} for r in compliance_rows(db,days) if str(r['id']) in ids]
    end=end or business_date();start=start or end.replace(day=1)
    if start>end or (end-start).days>366: raise HTTPException(422,'Choose a date range of up to 366 days, with start before end.')
    ids={str(r['id']) for r in selected}
    rows=db.execute(text("""select a.attendance_date,e.id,e.employee_code,e.name,e.branch,e.designation,s.site_name,upper(a.status) as status,a.shift_hours,a.overtime_hours,a.night_shift,a.late_minutes,a.violation_type,a.verification_status from attendance a join employees e on e.id=a.employee_id left join shift_rosters r on r.id=a.roster_id left join sites s on s.id=r.site_id where a.attendance_date between :start and :end order by a.attendance_date,e.name"""),{'start':start,'end':end}).mappings().all()
    return [dict(r) for r in rows if str(r['id']) in ids]


@router.get('/reports/export')
def export(kind:str=Query('master',pattern='^(master|attendance|compliance)$'),format:str=Query('xlsx',pattern='^(xlsx|pdf|csv)$'),start:date|None=None,end:date|None=None,days:int=Query(60,ge=1,le=365),q:str='',branch:str|None=None,site_id:int|None=None,status:str|None=None,designation:str|None=None,db:Session=Depends(get_db),user=Depends(require_hr_or_admin)):
    from app.services.employee_reports import export_report
    rows=reports(kind,start,end,days,q,branch,site_id,status,designation,db,user)
    return export_report(rows,kind,format)


@router.get('/{employee_id}/history')
def history(employee_id:UUID,db:Session=Depends(get_db),user=Depends(require_hr_or_admin)):
    employee(db,employee_id)
    return [dict(r) for r in db.execute(text('select h.*,u.full_name as changed_by_name from employee_history h left join users u on u.id=h.changed_by where employee_id=:id order by created_at desc,id desc'),{'id':str(employee_id)}).mappings()]


@router.post('',status_code=409)
def legacy_create(user=Depends(require_hr_or_admin)): raise HTTPException(409,'Create an intimation in Employee Creation. Permanent employee ID is issued there.')


@router.patch('/{employee_id}')
def legacy_edit(employee_id:UUID,user=Depends(require_hr_or_admin)): raise HTTPException(409,'Use the versioned joining draft. Submitted files must be returned by their approver before changes.')


@router.patch('/{employee_id}/status')
def status_change(employee_id:UUID,data:dict,db:Session=Depends(get_db),user=Depends(require_admin)):
    row=employee(db,employee_id,True)
    if data.get('version')!=row['version']: raise HTTPException(409,'Reopen the employee record before changing status.')
    state=data.get('status');reason=str(data.get('reason') or '').strip()
    if state not in {'ACTIVE','BENCH','INACTIVE','TERMINATED'} or not reason: raise HTTPException(422,'Choose a status and give a reason.')
    approved=db.execute(text("select 1 from employee_joining_drafts where employee_id=:id and status='APPROVED'"),{'id':str(employee_id)}).first()
    if not approved: raise HTTPException(409,'Complete joining approval before changing employment status.')
    if row['status']=='TERMINATED': raise HTTPException(409,'Terminated employee records cannot be reactivated.')
    if state=='ACTIVE' and compliance_reasons(db,employee_id): raise HTTPException(409,'Renew and verify mandatory compliance documents before activation.')
    db.execute(text('update employees set status=:status,status_reason=:reason,version=version+1,updated_at=now() where id=:id'),{'id':str(employee_id),'status':state,'reason':reason})
    db.execute(text('update guard_profiles set status=cast(:status as guard_status_enum) where employee_id=:id'),{'id':str(employee_id),'status':state})
    db.execute(text('update staff_profiles set status=:status,updated_at=now() where employee_id=:id'),{'id':str(employee_id),'status':state})
    audit(db,employee_id,user,'STATUS',row['version']+1,{'from':row['status'],'to':state,'reason':reason});db.commit();return {'status':state,'version':row['version']+1}
