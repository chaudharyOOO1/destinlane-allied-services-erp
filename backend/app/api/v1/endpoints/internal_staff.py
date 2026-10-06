from datetime import datetime, timezone
import re
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import update, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_active_user
from app.api.permissions import has_permission, all_permission_keys, permission_supported, role_allows, effective_permissions
from app.models.enums import UserRole
from app.models.internal_staff import InternalStaff, StaffCodeCounter, StaffHistory, StaffApprovalSettings
from app.models.user import User
from app.models.company import CompanySettings
from app.schemas.internal_staff import StaffCreate, StaffUpdate, StaffAction, StaffProfile, StaffLoginCreate, StaffAccessUpdate, ApprovalSettingUpdate
from app.schemas.user import UserCreate
from app.api.v1.endpoints import users as accounts

router = APIRouter()
MANAGERS = {UserRole.OWNER, UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.HR, UserRole.OPERATIONS, UserRole.ACCOUNTS}
ADMINISTRATORS = {UserRole.OWNER, UserRole.SUPER_ADMIN, UserRole.ADMIN}


def require_staff_administrator(user):
    if user.role not in {UserRole.OWNER,UserRole.HR}:
        raise HTTPException(403,'Only the Owner or HR can create staff or activate staff logins.')


def account_summary(user):
    return {'id':user.id,'login_id':user.login_id,'role':user.role.value,'is_active':user.is_active,
            'must_change_password':user.must_change_password} if user else None


def with_account(db, row):
    account = db.get(User,row.user_id) if row.user_id else None
    response = {**snapshot(row),'account':account_summary(account)}
    if account: response['profile'] = {**row.profile,'email':account.email}
    return response


def internal_access(user=Depends(get_current_active_user)):
    if user.role not in MANAGERS: raise HTTPException(403, 'Staff records require authorized internal office access.')
    return user


def snapshot(row):
    return {key:getattr(row,key) for key in ['id','staff_code','name','phone','profile','status','status_reason','version','approver_id','user_id']}


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
    roles = ['HR','OPERATIONS','ACCOUNTS']
    if user.role == UserRole.OWNER: roles = ['OWNER','SUPER_ADMIN','ADMIN'] + roles
    return {'branches':[{'code':b['code'],'name':b['name']} for b in branches if b.get('is_active',True)],
            'login_roles':roles,'permissions':{role:{key:role_allows(role,key) for key in all_permission_keys()} for role in roles},
            'supported':{role:{key:permission_supported(role,key) for key in all_permission_keys()} for role in roles}}



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
    valid = bool(re.fullmatch(r'(?:DASS|S-DAS-)[0-9]{4,}', code)) and int(re.search(r'[0-9]+$',code)[0]) >= 10
    row = db.query(InternalStaff).filter_by(staff_code=code).first() if valid else None
    return {'code':code,'valid_format':valid,'registered':row is not None,'status':row.status if row else None}


def create_login(db, row, data, user):
    email = row.profile.get('email')
    if not email: raise HTTPException(422,'Staff email is required for ERP login.')
    if data.role not in MANAGERS: raise HTTPException(422,'Choose an internal office role for this staff login.')
    for key, allowed in data.permissions.items():
        if key not in all_permission_keys() or (allowed and not permission_supported(data.role.value,key)):
            raise HTTPException(422,'A selected working permission is unavailable for this role.')
    account = accounts.prepare_user(db,UserCreate(email=email,login_id=row.staff_code,
        full_name=row.name,phone_number=row.phone,role=data.role,
        password=data.temporary_password.get_secret_value()),user)
    for key, allowed in data.permissions.items():
        db.execute(text('insert into public.user_permissions(user_id,permission_key,allowed) values(:user,:key,:allowed)'),
                   {'user':account.id,'key':key,'allowed':allowed})
        accounts.audit(db,user,account,'PERMISSION',{'permission_key':key,'allowed':allowed})
    return account


@router.post('', status_code=201)
def create_staff(data: StaffCreate, db: Session = Depends(get_db), user=Depends(internal_access)):
    require_staff_administrator(user)
    validate_branch(db,data.profile)
    if db.query(InternalStaff).filter_by(phone=data.profile.phone).first(): raise HTTPException(409, 'This phone number is already registered.')
    number = db.execute(update(StaffCodeCounter).where(StaffCodeCounter.id == 1).values(next_number=StaffCodeCounter.next_number+1).returning(StaffCodeCounter.next_number)).scalar_one_or_none()
    if number is None: raise HTTPException(503, 'Staff code allocation is not configured.')
    status = 'ACTIVE'
    row = InternalStaff(staff_code=f'DASS{number-1:04d}', name=data.profile.name, phone=data.profile.phone,
                        profile=data.profile.model_dump(mode='json'), status=status, version=1, created_by=user.id)
    db.add(row)
    try:
        db.flush()
        create_login(db,row,data.account,user)
        record(db,row,user,'CREATE')
        response = with_account(db,row)
        commit(db)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Staff code or phone number already exists.') from None
    except HTTPException:
        db.rollback(); raise
    return response


@router.get('/{staff_id}')
def read_staff(staff_id: int, db: Session = Depends(get_db), user=Depends(internal_access)):
    row = db.get(InternalStaff, staff_id)
    if not row: raise HTTPException(404, 'Staff record not found.')
    response = with_account(db,row)
    if row.user_id and user.role in {UserRole.OWNER,UserRole.HR}:
        response['permissions'] = effective_permissions(db,db.get(User,row.user_id),include_inactive=True)
    return response


@router.post('/{staff_id}/login', status_code=201)
def activate_staff_login(staff_id: int, data: StaffLoginCreate, db: Session = Depends(get_db), user=Depends(internal_access)):
    require_staff_administrator(user)
    row = db.query(InternalStaff).filter_by(id=staff_id).with_for_update().first()
    if not row: raise HTTPException(404,'Staff record not found.')
    if row.status != 'ACTIVE': raise HTTPException(409,'Activate the staff record before creating its ERP login.')
    if row.user_id or db.query(User).filter_by(login_id=row.staff_code).first():
        raise HTTPException(409,'This staff record already has an ERP account.')
    try:
        create_login(db,row,data,user)
        row.version+=1
        record(db,row,user,'LOGIN_ACTIVATED')
        response=with_account(db,row);commit(db);return response
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Account details already belong to another login.') from None
    except HTTPException:
        db.rollback();raise


@router.put('/{staff_id}')
def update_staff(staff_id: int, data: StaffUpdate, db: Session = Depends(get_db), user=Depends(internal_access)):
    require_staff_administrator(user)
    row = get_locked(db,staff_id,data.version)
    validate_branch(db,data.profile,row.profile)
    if row.status == 'TERMINATED': raise HTTPException(409, 'Terminated staff records are retained and cannot be edited.')
    if row.user_id:
        account = db.get(User,row.user_id)
        accounts._assert_manage_target(user,account)
        if data.profile.email != account.email: raise HTTPException(400,'The login email cannot be changed from Staff Master.')
        accounts.assert_unique(db,{'phone_number':data.profile.phone},account.id)
        account.full_name, account.phone_number = data.profile.name, data.profile.phone
        accounts.audit(db,user,account,'STAFF_DETAILS',{'full_name':account.full_name,'phone_number':account.phone_number})
    row.name, row.phone, row.profile = data.profile.name, data.profile.phone, data.profile.model_dump(mode='json')
    try:
        record(db,row,user,'UPDATE')
        response = with_account(db,row)
        commit(db)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'This phone number is already registered.') from None
    return response


@router.post('/{staff_id}/submit')
def submit_staff(staff_id: int, data: StaffAction, db: Session = Depends(get_db), user=Depends(internal_access)):
    require_staff_administrator(user)
    if not has_permission(db,user,'staff.edit'): raise HTTPException(403,'Permission denied: staff.edit')
    row = get_locked(db,staff_id,data.version)
    if row.status != 'DRAFT': raise HTTPException(409, 'Only drafts can be submitted.')
    row.status = 'ACTIVE'
    row.approver_id = None
    row.status_reason = ''
    record(db,row,user,'SUBMIT'); response = with_account(db,row); commit(db)
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
    record(db,row,user,data.decision); response = with_account(db,row); commit(db)
    return response


@router.post('/{staff_id}/status')
def change_status(staff_id: int, data: StaffAction, db: Session = Depends(get_db), user=Depends(internal_access)):
    if not has_permission(db,user,'staff.edit'): raise HTTPException(403,'Permission denied: staff.edit')
    require_staff_administrator(user)
    row = get_locked(db,staff_id,data.version)
    if row.status not in {'DRAFT','PENDING','ACTIVE','INACTIVE'}: raise HTTPException(409, 'Only approved staff can change operational status.')
    if not data.reason: raise HTTPException(422, 'A status change reason is required.')
    row.status, row.status_reason = data.status, data.reason
    if row.user_id:
        account = db.get(User,row.user_id)
        if account and data.status != 'ACTIVE':
            accounts._assert_manage_target(user,account)
            if account.id == user.id: raise HTTPException(400,'You cannot disable your own staff login.')
            account.is_active=False
            account.session_version+=1
            accounts.audit(db,user,account,'STAFF_DISABLED',{'staff_code':row.staff_code,'status':row.status})
    record(db,row,user,'STATUS'); response = with_account(db,row); commit(db)
    return response


@router.put('/{staff_id}/login')
def update_staff_access(staff_id: int, data: StaffAccessUpdate, db: Session = Depends(get_db), user=Depends(internal_access)):
    require_staff_administrator(user)
    row = get_locked(db,staff_id,data.version)
    account = db.get(User,row.user_id) if row.user_id else None
    if not account: raise HTTPException(404,'This staff record has no ERP login.')
    accounts._assert_manage_target(user,account,data.role)
    if account.id == user.id: raise HTTPException(400,'Use User Management to change your own access.')
    if data.role not in MANAGERS: raise HTTPException(422,'Choose an internal office role.')
    if data.is_active and row.status != 'ACTIVE': raise HTTPException(409,'Reactivate the staff record first.')
    for key, allowed in data.permissions.items():
        if key not in all_permission_keys() or (allowed and not permission_supported(data.role.value,key)):
            raise HTTPException(422,'A selected working permission is unavailable for this role.')
    account.role, account.is_active = data.role, data.is_active
    account.session_version += 1
    for key, allowed in data.permissions.items():
        db.execute(text('insert into public.user_permissions(user_id,permission_key,allowed) values(:user,:key,:allowed) on conflict(user_id,permission_key) do update set allowed=excluded.allowed'),
                   {'user':account.id,'key':key,'allowed':allowed})
    accounts.audit(db,user,account,'STAFF_ACCESS',{'role':data.role.value,'is_active':data.is_active,'permissions':data.permissions})
    record(db,row,user,'ACCESS_UPDATED')
    response=with_account(db,row);response['permissions']=effective_permissions(db,account,include_inactive=True)
    commit(db);return response
