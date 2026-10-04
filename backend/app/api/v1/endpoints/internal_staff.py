from datetime import datetime, timezone
import re
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_active_user
from app.api.permissions import has_permission
from app.models.enums import UserRole
from app.models.internal_staff import InternalStaff, StaffCodeCounter, StaffHistory, StaffApprovalSettings
from app.models.user import User
from app.models.company import CompanySettings
from app.schemas.internal_staff import StaffCreate, StaffUpdate, StaffAction, StaffProfile, ApprovalSettingUpdate

router = APIRouter()
MANAGERS = {UserRole.OWNER, UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.HR, UserRole.OPERATIONS, UserRole.ACCOUNTS}


def internal_access(user=Depends(get_current_active_user)):
    if user.role not in MANAGERS: raise HTTPException(403, 'Staff records require authorized internal office access.')
    return user


def snapshot(row):
    return {key:getattr(row,key) for key in ['id','staff_code','name','phone','profile','status','status_reason','version','approver_id']}


def record(db, row, user, action):
    row.updated_by = user.id
    row.updated_at = datetime.now(timezone.utc)
    db.flush()
    db.add(StaffHistory(staff_id=row.id, snapshot=snapshot(row), changed_by=user.id, action=action))


def commit(db):
    try: db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'This phone number or staff code is already registered.') from None


def get_locked(db, staff_id, version):
    row = db.query(InternalStaff).filter_by(id=staff_id).with_for_update().first()
    if not row: raise HTTPException(404, 'Staff record not found.')
    # Conditional update also prevents stale writes on databases without row locks.
    result = db.execute(update(InternalStaff).where(InternalStaff.id == staff_id, InternalStaff.version == version).values(version=version+1))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, 'This staff record changed. Reload it before saving.')
    db.refresh(row)
    return row


def approver_for_submission(db):
    rule = db.get(StaffApprovalSettings,1)
    if rule and rule.approver_id:
        target = db.get(User,rule.approver_id)
        if not target or not target.is_active or target.role not in MANAGERS or not has_permission(db,target,'staff.approve') or not has_permission(db,target,'staff.view'):
            raise HTTPException(409, 'The assigned staff approver is unavailable. Ask the Owner to update approval settings.')
        return target.id
    return None


def validate_branch(db, profile, previous=None):
    if not profile.branch or (previous and previous.get('branch') == profile.branch): return
    company = db.get(CompanySettings,1)
    branches = company.profile.get('branches',[]) if company else []
    if not any(b.get('code') == profile.branch and b.get('is_active',True) for b in branches):
        raise HTTPException(422, 'Choose an active branch configured in Company Profile & Docs.')


def ready(profile):
    try: profile.ready_for_submission()
    except ValueError as exc: raise HTTPException(422, str(exc)) from None


@router.get('')
def list_staff(q: str = Query('', max_length=150), status: str = '', db: Session = Depends(get_db), user=Depends(internal_access)):
    query = db.query(InternalStaff)
    if q:
        pattern = '%' + q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_') + '%'
        query = query.filter(InternalStaff.name.ilike(pattern, escape='\\') | InternalStaff.staff_code.ilike(pattern, escape='\\') | InternalStaff.phone.ilike(pattern, escape='\\'))
    if status:
        if status not in {'DRAFT','PENDING','ACTIVE','INACTIVE','TERMINATED'}: raise HTTPException(422, 'Invalid staff status.')
        query = query.filter_by(status=status)
    rows = query.order_by(InternalStaff.id.desc()).all()
    # Personal, bank and statutory details are returned only when opening a record.
    return [{'id':r.id,'staff_code':r.staff_code,'name':r.name,'phone':r.phone,'status':r.status,'version':r.version,
             **{key:r.profile.get(key,'') for key in ['department','designation','region','management_level','branch','joining_date']}} for r in rows]


@router.get('/office-options')
def office_options(db: Session = Depends(get_db), user=Depends(internal_access)):
    company = db.get(CompanySettings,1)
    branches = company.profile.get('branches',[]) if company else []
    return {'branches':[{'code':b['code'],'name':b['name']} for b in branches if b.get('is_active',True)]}


@router.get('/approval-settings')
def get_approval_settings(db: Session = Depends(get_db), user=Depends(internal_access)):
    rule = db.get(StaffApprovalSettings,1)
    return {'approver_id':rule.approver_id if rule else None,'version':rule.version if rule else 1}


@router.put('/approval-settings')
def set_approval_settings(data: ApprovalSettingUpdate, db: Session = Depends(get_db), user=Depends(internal_access)):
    if user.role != UserRole.OWNER: raise HTTPException(403, 'Only the Owner can assign approval responsibility.')
    if data.approver_id:
        target = db.get(User,data.approver_id)
        if not target or not target.is_active or target.role not in MANAGERS or not has_permission(db,target,'staff.approve') or not has_permission(db,target,'staff.view'):
            raise HTTPException(422, 'Choose an active internal office account with staff view and approval permissions.')
    result = db.execute(update(StaffApprovalSettings).where(StaffApprovalSettings.id==1,StaffApprovalSettings.version==data.version).values(approver_id=data.approver_id,version=data.version+1))
    if result.rowcount != 1: raise HTTPException(409,'Approval settings changed. Reload before saving.')
    commit(db)
    return {'approver_id':data.approver_id,'version':data.version+1}


@router.get('/code-check')
def code_check(code: str = Query(..., max_length=30), db: Session = Depends(get_db), user=Depends(internal_access)):
    code = code.strip().upper()
    valid = bool(re.fullmatch(r'S-DAS-[0-9]{4,}', code)) and int(code[6:]) >= 10
    row = db.query(InternalStaff).filter_by(staff_code=code).first() if valid else None
    return {'code':code,'valid_format':valid,'registered':row is not None,'status':row.status if row else None}


@router.post('', status_code=201)
def create_staff(data: StaffCreate, db: Session = Depends(get_db), user=Depends(internal_access)):
    validate_branch(db,data.profile)
    if data.submit: ready(data.profile)
    if db.query(InternalStaff).filter_by(phone=data.profile.phone).first(): raise HTTPException(409, 'This phone number is already registered.')
    number = db.execute(update(StaffCodeCounter).where(StaffCodeCounter.id == 1).values(next_number=StaffCodeCounter.next_number+1).returning(StaffCodeCounter.next_number)).scalar_one_or_none()
    if number is None: raise HTTPException(503, 'Staff code allocation is not configured.')
    status = ('ACTIVE' if user.role == UserRole.OWNER else 'PENDING') if data.submit else 'DRAFT'
    row = InternalStaff(staff_code=f'S-DAS-{number-1:04d}', name=data.profile.name, phone=data.profile.phone,
                        profile=data.profile.model_dump(mode='json'), status=status, version=1, created_by=user.id, approver_id=approver_for_submission(db) if status=='PENDING' else None)
    db.add(row)
    try:
        record(db,row,user,'CREATE')
        response = snapshot(row)
        commit(db)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Staff code or phone number already exists.') from None
    return response


@router.get('/{staff_id}')
def read_staff(staff_id: int, db: Session = Depends(get_db), user=Depends(internal_access)):
    row = db.get(InternalStaff, staff_id)
    if not row: raise HTTPException(404, 'Staff record not found.')
    account = db.query(User).filter_by(login_id=row.staff_code).first()
    return {**snapshot(row), 'account': {'login_id':account.login_id,'role':account.role.value,'is_active':account.is_active} if account else None}


@router.put('/{staff_id}')
def update_staff(staff_id: int, data: StaffUpdate, db: Session = Depends(get_db), user=Depends(internal_access)):
    row = get_locked(db,staff_id,data.version)
    validate_branch(db,data.profile,row.profile)
    if row.status == 'TERMINATED': raise HTTPException(409, 'Terminated staff records are retained and cannot be edited.')
    if row.status in {'PENDING','ACTIVE','INACTIVE'}: ready(data.profile)
    row.name, row.phone, row.profile = data.profile.name, data.profile.phone, data.profile.model_dump(mode='json')
    try:
        record(db,row,user,'UPDATE')
        response = snapshot(row)
        commit(db)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'This phone number is already registered.') from None
    return response


@router.post('/{staff_id}/submit')
def submit_staff(staff_id: int, data: StaffAction, db: Session = Depends(get_db), user=Depends(internal_access)):
    if not has_permission(db,user,'staff.edit'): raise HTTPException(403,'Permission denied: staff.edit')
    row = get_locked(db,staff_id,data.version)
    if row.status != 'DRAFT': raise HTTPException(409, 'Only drafts can be submitted.')
    ready(StaffProfile(**row.profile))
    row.status = 'ACTIVE' if user.role == UserRole.OWNER else 'PENDING'
    row.approver_id = approver_for_submission(db) if row.status=='PENDING' else None
    row.status_reason = ''
    record(db,row,user,'SUBMIT'); response = snapshot(row); commit(db)
    return response


@router.post('/{staff_id}/decision')
def decide_staff(staff_id: int, data: StaffAction, db: Session = Depends(get_db), user=Depends(internal_access)):
    row = get_locked(db,staff_id,data.version)
    if user.role != UserRole.OWNER and row.approver_id != user.id: raise HTTPException(403, 'This staff approval is assigned to another account.')
    if row.status != 'PENDING': raise HTTPException(409, 'Staff record is not awaiting approval.')
    if data.decision == 'RETURN' and not data.reason: raise HTTPException(422, 'A return reason is required.')
    ready(StaffProfile(**row.profile))
    row.status = 'ACTIVE' if data.decision == 'APPROVE' else 'DRAFT'
    row.status_reason = data.reason
    record(db,row,user,data.decision); response = snapshot(row); commit(db)
    return response


@router.post('/{staff_id}/status')
def change_status(staff_id: int, data: StaffAction, db: Session = Depends(get_db), user=Depends(internal_access)):
    if not has_permission(db,user,'staff.edit'): raise HTTPException(403,'Permission denied: staff.edit')
    if user.role not in {UserRole.OWNER,UserRole.ADMIN,UserRole.SUPER_ADMIN}: raise HTTPException(403,'Only administrators can change staff status.')
    row = get_locked(db,staff_id,data.version)
    if row.status not in {'ACTIVE','INACTIVE'}: raise HTTPException(409, 'Only approved staff can change operational status.')
    if not data.reason: raise HTTPException(422, 'A status change reason is required.')
    row.status, row.status_reason = data.status, data.reason
    record(db,row,user,'STATUS'); response = snapshot(row); commit(db)
    return response
