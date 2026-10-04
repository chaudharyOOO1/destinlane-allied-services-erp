import json
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import require_hr_or_admin, get_current_owner
from app.api.permissions import has_permission
from app.core.database import get_db
from app.models.user import User
from app.services.employee_workflow import employee,profile,clean_profile,validate_links,readiness,audit,activate,BASIC,bank_match

router=APIRouter()


def payload(db,eid):
    row=employee(db,eid)
    draft=db.execute(text('select status,last_saved_at from employee_joining_drafts where employee_id=:id'),{'id':str(eid)}).mappings().first()
    return {**row,'profile':profile(row),'joining_status':draft['status'] if draft else None,'last_saved_at':draft['last_saved_at'] if draft else None,'readiness':readiness(db,row),'approval_readiness':readiness(db,row,True)}


@router.post('/intimations',status_code=201)
def create_intimation(data:dict,db:Session=Depends(get_db),user:User=Depends(require_hr_or_admin)):
    fields={'name','father_name','aadhaar_no','phone','client_id','branch'}
    if set(data)-fields: raise HTTPException(422,'Intimation accepts name, father name, Aadhaar, phone, client and company branch only.')
    p=clean_profile(data)
    missing=fields-{k for k,v in p.items() if v}
    if missing: raise HTTPException(422,'Complete intimation fields: '+', '.join(sorted(missing)))
    validate_links(db,p)
    try:
        info=db.execute(text('insert into employee_intimations(name,father_name,aadhaar_no,phone,client_id,branch,created_by) values (:name,:father_name,:aadhaar_no,:phone,:client_id,:branch,:user) returning *'),{**p,'user':user.id}).mappings().one()
        row=db.execute(text("insert into employees(name,father_name,aadhaar_no,phone,client_id,branch,intimation_id,status) values (:name,:father_name,:aadhaar_no,:phone,:client_id,:branch,:iid,'DRAFT') returning *"),{**p,'iid':info['intimation_id']}).mappings().one()
        db.execute(text("insert into employee_joining_drafts(intimation_id,employee_id,created_by) values (:iid,:eid,:user)"),{'iid':str(info['id']),'eid':str(row['id']),'user':user.id})
        audit(db,row['id'],user,'INTIMATION',1,{'intimation_id':info['intimation_id']})
        db.commit()
        return payload(db,row['id'])
    except IntegrityError:
        db.rollback();raise HTTPException(409,'An employee with this Aadhaar or mobile number already exists. Open the existing employee file.')


@router.get('/intimations')
@router.get('/joining')
def list_joining(db:Session=Depends(get_db),user=Depends(require_hr_or_admin)):
    rows=db.execute(text("select e.id,e.employee_code,e.name,e.phone,e.branch,e.designation,e.intimation_id,e.status as employee_status,e.client_id,d.intimation_id as intimation_uuid,d.status as joining_status,d.last_saved_at from employee_joining_drafts d join employees e on e.id=d.employee_id order by d.updated_at desc")).mappings().all()
    return [dict(x) for x in rows]


@router.post('/intimations/{intimation_id}/create')
def resume_intimation(intimation_id:UUID,db:Session=Depends(get_db),user=Depends(require_hr_or_admin)):
    row=db.execute(text('select employee_id from employee_joining_drafts where intimation_id=:id'),{'id':str(intimation_id)}).first()
    if not row: raise HTTPException(404,'Intimation joining file not found.')
    return payload(db,row[0])


@router.get('/joining/{employee_id}')
def get_joining(employee_id:UUID,db:Session=Depends(get_db),user=Depends(require_hr_or_admin)): return payload(db,employee_id)


@router.patch('/joining/{employee_id}')
def save_joining(employee_id:UUID,data:dict,db:Session=Depends(get_db),user=Depends(require_hr_or_admin)):
    if set(data)-{'version','profile'} or not isinstance(data.get('profile'),dict): raise HTTPException(422,'Provide version and profile.')
    row=employee(db,employee_id,True)
    if data.get('version')!=row['version']: raise HTTPException(409,'This employee file changed. Reopen it before saving.')
    draft=db.execute(text('select status from employee_joining_drafts where employee_id=:id'),{'id':str(employee_id)}).first()
    if not draft or draft[0] not in {'DRAFT','REJECTED'}: raise HTTPException(409,'The submitted employee file is locked. It must be returned before changes.')
    updates=clean_profile(data['profile']); p={**profile(row),**updates}
    if any(not p.get(k) for k in {'name','father_name','phone','aadhaar_no','branch','client_id'}): raise HTTPException(422,'Intimation identity, client and company branch remain required.')
    validate_links(db,p)
    extras={k:v for k,v in p.items() if k not in BASIC}
    basic={k:v for k,v in updates.items() if k in BASIC}
    sets=', '.join(f'{k}=:{k}' for k in basic)
    parameters={**basic,'id':str(employee_id),'profile':json.dumps(extras,default=str)}
    try:
        db.execute(text('update employees set '+(sets+', ' if sets else '')+"profile=cast(:profile as jsonb),version=version+1,updated_at=now(),status='DRAFT' where id=:id"),parameters)
        if all(p.get(k) for k in {'bank_account_no','bank_name','bank_branch','bank_ifsc'}):
            db.execute(text('insert into employee_bank_accounts(employee_id,account_number,bank_name,branch,ifsc_code,ifsc_verified) values (:id,:account,:bank,:branch,:ifsc,:verified) on conflict (employee_id) do update set account_number=excluded.account_number,bank_name=excluded.bank_name,branch=excluded.branch,ifsc_code=excluded.ifsc_code,ifsc_verified=excluded.ifsc_verified,updated_at=now()'),{'id':str(employee_id),'account':p['bank_account_no'],'bank':p['bank_name'],'branch':p['bank_branch'],'ifsc':p['bank_ifsc'],'verified':bank_match(db,p)})
        db.execute(text("update employee_joining_drafts set status='DRAFT',last_saved_at=now(),updated_at=now() where employee_id=:id"),{'id':str(employee_id)})
        db.execute(text("update employee_intimations set status='JOINING',updated_at=now() where intimation_id=:iid"),{'iid':row['intimation_id']})
        audit(db,employee_id,user,'SAVE_DRAFT',row['version']+1,{'changed_fields':sorted(updates)})
        db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'This Aadhaar or mobile belongs to another employee.')
    return payload(db,employee_id)


def approval_chain(db):
    rows=db.execute(text("select * from employee_approval_categories where task_type='EMPLOYEE_JOINING' and is_active=true and approver_user_id is not null order by sequence_order,id")).mappings().all()
    if not rows or not rows[-1]['is_final_approver'] or sum(bool(x['is_final_approver']) for x in rows)!=1: raise HTTPException(409,'Owner must configure the joining approval chain with its last step marked final.')
    result=[]
    for c in rows:
        target=db.get(User,c['approver_user_id'])
        if not target or not target.is_active or target.role.value not in {'OWNER','SUPER_ADMIN','ADMIN','HR'} or not has_permission(db,target,'employees.approve') or not has_permission(db,target,'employees.view'): raise HTTPException(409,'An assigned joining approver is unavailable. Owner must update the setup.')
        result.append({'category_id':c['id'],'assigned_to':target.id,'category_name':c['category_name']})
    return result


def add_request(db,eid,user,chain,index=0):
    c=chain[index]
    return dict(db.execute(text("insert into employee_approval_requests(employee_id,category_id,assigned_to,submitted_by,status,workflow_snapshot,step_index) values (:id,:category,:assigned,:user,'PENDING',cast(:chain as jsonb),:step) returning *"),{'id':str(eid),'category':c['category_id'],'assigned':c['assigned_to'],'user':user.id,'chain':json.dumps(chain),'step':index}).mappings().one())


@router.post('/joining/{employee_id}/submit')
def submit_joining(employee_id:UUID,data:dict,db:Session=Depends(get_db),user=Depends(require_hr_or_admin)):
    row=employee(db,employee_id,True)
    if data.get('version')!=row['version']: raise HTTPException(409,'Reopen the current employee file before submitting.')
    draft=db.execute(text('select status from employee_joining_drafts where employee_id=:id'),{'id':str(employee_id)}).first()
    if not draft or draft[0] not in {'DRAFT','REJECTED'}: raise HTTPException(409,'This file is already submitted or approved.')
    validate_links(db,profile(row)); ready=readiness(db,row,user.role.value=='OWNER')
    if not ready['ready']: raise HTTPException(422,ready)
    if user.role.value=='OWNER':
        activate(db,row,user);db.commit();return {'status':'APPROVED','employee_id':str(employee_id),'final':True}
    chain=approval_chain(db);request=add_request(db,employee_id,user,chain)
    db.execute(text("update employees set status='PENDING_APPROVAL',version=version+1,updated_at=now() where id=:id"),{'id':str(employee_id)})
    db.execute(text("update employee_joining_drafts set status='PENDING_APPROVAL',updated_at=now() where employee_id=:id"),{'id':str(employee_id)})
    audit(db,employee_id,user,'SUBMIT',row['version']+1,{'approvers':chain});db.commit();return request


@router.get('/approvals')
def list_approvals(db:Session=Depends(get_db),user=Depends(require_hr_or_admin)):
    rows=db.execute(text("select ar.*,e.name,e.employee_code from employee_approval_requests ar join employees e on e.id=ar.employee_id where ar.status='PENDING' and (:owner or ar.assigned_to=:user) order by ar.submitted_at"),{'owner':user.role.value=='OWNER','user':user.id}).mappings().all()
    return [dict(r) for r in rows]


@router.post('/approvals/{approval_id}/decision')
def decide(approval_id:UUID,data:dict,db:Session=Depends(get_db),user=Depends(require_hr_or_admin)):
    # Match document mutations' employee-first lock order; concurrent decisions cannot activate twice.
    target=db.execute(text('select employee_id from employee_approval_requests where id=:id'),{'id':str(approval_id)}).first()
    if not target: raise HTTPException(404,'Approval request not found.')
    row=employee(db,target[0],True)
    req=db.execute(text('select * from employee_approval_requests where id=:id for update'),{'id':str(approval_id)}).mappings().one()
    if req['status']!='PENDING': raise HTTPException(409,'This request is already decided.')
    if user.role.value!='OWNER' and req['assigned_to']!=user.id: raise HTTPException(403,'This request is assigned to another approver.')
    decision=data.get('decision');remarks=str(data.get('remarks') or '').strip()
    if decision not in {'APPROVE','REJECT'}: raise HTTPException(422,'Choose APPROVE or REJECT.')
    if decision=='REJECT' and not remarks: raise HTTPException(422,'Return remarks are required.')
    chain=req['workflow_snapshot'];index=req['step_index']
    if decision=='APPROVE':
        validate_links(db,profile(row))
        ready=readiness(db,row,True)
        if not ready['ready']: raise HTTPException(422,ready)
        if not chain or index>=len(chain): raise HTTPException(409,'Approval chain is missing; Owner must return this file and resubmit.')
    db.execute(text('update employee_approval_requests set status=:status,remarks=:remarks,decided_by=:user,decided_at=now() where id=:id'),{'id':str(approval_id),'status':'APPROVED' if decision=='APPROVE' else 'REJECTED','remarks':remarks or None,'user':user.id})
    if decision=='REJECT':
        db.execute(text("update employees set status='REJECTED',version=version+1,updated_at=now() where id=:id"),{'id':str(row['id'])})
        db.execute(text("update employee_joining_drafts set status='REJECTED',updated_at=now() where employee_id=:id"),{'id':str(row['id'])})
        audit(db,row['id'],user,'RETURN',row['version']+1,{'remarks':remarks})
    elif index==len(chain)-1: activate(db,row,user)
    else:
        next_user=db.get(User,chain[index+1]['assigned_to'])
        if not next_user or not next_user.is_active or not has_permission(db,next_user,'employees.approve'): raise HTTPException(409,'Next assigned approver is unavailable. Owner can return the file for resubmission.')
        add_request(db,row['id'],user,chain,index+1);audit(db,row['id'],user,'APPROVE_STEP',row['version'],{'remarks':remarks,'step':index})
    db.commit();return {'status':decision,'employee_id':str(row['id']),'final':decision=='APPROVE' and index==len(chain)-1}


@router.get('/approval-categories')
def categories(db:Session=Depends(get_db),user=Depends(require_hr_or_admin)):
    return [dict(x) for x in db.execute(text('select c.*,u.full_name as approver_name from employee_approval_categories c left join users u on u.id=c.approver_user_id order by sequence_order,id')).mappings()]


@router.put('/approval-categories/{category_id}')
def update_category(category_id:int,data:dict,db:Session=Depends(get_db),user=Depends(get_current_owner)):
    assigned=data.get('approver_user_id') or None
    if assigned:
        target=db.get(User,assigned)
        if not target or not target.is_active or target.role.value not in {'OWNER','SUPER_ADMIN','ADMIN','HR'} or not has_permission(db,target,'employees.approve') or not has_permission(db,target,'employees.view'): raise HTTPException(422,'Choose an active approver with Employee view and approve access.')
    final=data.get('is_final_approver',False)
    if not isinstance(final,bool): raise HTTPException(422,'Final approver must be true or false.')
    if final: db.execute(text("update employee_approval_categories set is_final_approver=false where task_type='EMPLOYEE_JOINING'"))
    row=db.execute(text('update employee_approval_categories set approver_user_id=:user,is_final_approver=:final,updated_at=now() where id=:id returning *'),{'id':category_id,'user':assigned,'final':final}).mappings().first()
    if not row: raise HTTPException(404,'Approval step not found.')
    db.commit();return dict(row)
