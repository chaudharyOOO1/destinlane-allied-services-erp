"""Internal staff proposals: no salary generation from active staff alone."""
import json
from datetime import date
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.api.deps import require_payroll, require_management, require_accounts_or_admin
from app.core.database import get_db
from app.core.business_time import business_date
from app.api.v1.endpoints.payroll import _month

router = APIRouter()


class Proposal(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    staff_id: int = Field(gt=0)
    month: str = Field(pattern=r'^\d{4}-\d{2}$')
    gross_pay: Decimal = Field(gt=0, le=99999999, max_digits=10, decimal_places=2)
    deductions: Decimal = Field(ge=0, le=99999999, max_digits=10, decimal_places=2)
    work_note: str = Field(min_length=10, max_length=2000)

    @model_validator(mode='after')
    def balanced(self):
        if self.deductions > self.gross_pay:
            raise ValueError('Deductions cannot exceed gross pay')
        return self


class Decision(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    version: int = Field(ge=1)
    decision: Literal['APPROVE','REJECT']
    note: str = Field(min_length=10, max_length=2000)


class Payment(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    version: int = Field(ge=1)
    paid_on: date
    reference: str = Field(min_length=3, max_length=200)


def record(db, row, user, action):
    data = dict(row)
    db.execute(text('''insert into staff_monthly_pay_audit(pay_id,actor_id,action,snapshot)
        values(:id,:actor,:action,cast(:snapshot as jsonb))'''),
        {'id': data['id'], 'actor': user.id, 'action': action, 'snapshot': json.dumps(data, default=str)})
    db.commit()
    return data


@router.get('')
def list_staff_pay(month: str, db:Session=Depends(get_db), user=Depends(require_payroll)):
    period = _month(month)
    rows = db.execute(text('''select p.*,s.staff_code,s.name from staff_monthly_pay p
        join internal_staff s on s.id=p.staff_id where p.payroll_month=:month order by s.name'''),
        {'month': period}).mappings().all()
    staff = db.execute(text("select id,staff_code,name,profile->>'branch' branch from internal_staff where status='ACTIVE' order by name")).mappings().all()
    return {'proposals':[dict(r) for r in rows], 'staff':[dict(r) for r in staff],
            'policy':'Management approval is required separately for every staff member and month.'}


@router.post('',status_code=201)
def propose(payload:Proposal, db:Session=Depends(get_db), user=Depends(require_payroll)):
    staff=db.execute(text("select id,profile->>'branch' branch from internal_staff where id=:id and status='ACTIVE' for update"),{'id':payload.staff_id}).mappings().first()
    if not staff: raise HTTPException(409,'Choose active internal staff')
    if not staff['branch']: raise HTTPException(409,'Assign the staff member to a branch before proposing pay')
    data=payload.model_dump(exclude={'month'}); data.update(month=_month(payload.month),branch=staff['branch'],user=user.id)
    row=db.execute(text('''insert into staff_monthly_pay(staff_id,payroll_month,branch,gross_pay,deductions,work_note,created_by)
        values(:staff_id,:month,:branch,:gross_pay,:deductions,:work_note,:user)
        on conflict(staff_id,payroll_month) do nothing returning *'''),data).mappings().first()
    if not row: raise HTTPException(409,'A proposal already exists for this staff member and month')
    return record(db,row,user,'PROPOSE')


def locked(db,pay_id,version):
    row=db.execute(text('select * from staff_monthly_pay where id=:id for update'),{'id':pay_id}).mappings().first()
    if not row: raise HTTPException(404,'Staff pay proposal not found')
    if row['version']!=version: raise HTTPException(409,'This proposal changed. Refresh before continuing')
    return row


class ProposalUpdate(Proposal):
    version: int = Field(ge=1)


@router.put('/{pay_id}')
def revise(pay_id:int,payload:ProposalUpdate,db:Session=Depends(get_db),user=Depends(require_payroll)):
    row=locked(db,pay_id,payload.version)
    if row['status'] not in {'DRAFT','REJECTED'}: raise HTTPException(409,'Approved or paid proposals cannot be edited')
    if row['staff_id']!=payload.staff_id or row['payroll_month']!=_month(payload.month):
        raise HTTPException(422,'Staff and month cannot be changed')
    data=payload.model_dump(exclude={'month','version'});data['id']=pay_id
    changed=db.execute(text("""update staff_monthly_pay set gross_pay=:gross_pay,deductions=:deductions,
        work_note=:work_note,status='DRAFT',approved_by=null,approved_at=null,decision_note=null,
        version=version+1,updated_at=now() where id=:id returning *"""),data).mappings().one()
    return record(db,changed,user,'REVISE')


@router.post('/{pay_id}/decision')
def decide(pay_id:int,payload:Decision,db:Session=Depends(get_db),user=Depends(require_management)):
    row=locked(db,pay_id,payload.version)
    if row['status']!='DRAFT': raise HTTPException(409,'Only a draft proposal can be decided')
    active=db.execute(text("select 1 from internal_staff where id=:id and status='ACTIVE'"),{'id':row['staff_id']}).first()
    if not active: raise HTTPException(409,'Staff member is no longer active')
    changed=db.execute(text('''update staff_monthly_pay set status=:status,decision_note=:note,
        approved_by=:user,approved_at=now(),version=version+1,updated_at=now()
        where id=:id returning *'''),{'id':pay_id,'status':'APPROVED' if payload.decision=='APPROVE' else 'REJECTED','note':payload.note,'user':user.id}).mappings().one()
    return record(db,changed,user,payload.decision)


@router.post('/{pay_id}/pay')
def pay(pay_id:int,payload:Payment,db:Session=Depends(get_db),user=Depends(require_accounts_or_admin)):
    row=locked(db,pay_id,payload.version)
    if row['status']!='APPROVED': raise HTTPException(409,'Management must approve this month before a payment can be recorded')
    if payload.paid_on>business_date(): raise HTTPException(422,'Payment date cannot be in the future')
    changed=db.execute(text('''update staff_monthly_pay set status='PAID',paid_on=:date,payment_reference=:reference,
        paid_by=:user,version=version+1,updated_at=now() where id=:id returning *'''),
        {'id':pay_id,'date':payload.paid_on,'reference':payload.reference,'user':user.id}).mappings().one()
    return record(db,changed,user,'RECORD_PAYMENT')
