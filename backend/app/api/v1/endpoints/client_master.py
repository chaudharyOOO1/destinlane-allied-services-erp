from datetime import date,datetime,timezone
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import update,func,text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.api.deps import get_current_active_user,require_admin
from app.core.database import get_db
from app.models.client import Client,ClientCodeCounter,ClientStaffAssignment,ClientHistory
from app.models.internal_staff import InternalStaff
from app.models.company import CompanySettings
from app.models.user import User
from app.models.site import Site
from app.models.enums import UserRole
from app.schemas.client_master import ClientProfile,ClientUpdate

router=APIRouter()
READ_ROLES={UserRole.OWNER,UserRole.SUPER_ADMIN,UserRole.ADMIN,UserRole.HR,UserRole.OPERATIONS,UserRole.ACCOUNTS,UserRole.SUPERVISOR,UserRole.CLIENT}


def reader(user=Depends(get_current_active_user)):
    if user.role not in READ_ROLES:raise HTTPException(403,'Client records require authorized business access.')
    return user


def scoped_query(db,user):
    query=db.query(Client)
    return query.filter(Client.user_id==user.id) if user.role==UserRole.CLIENT else query


def get_record(db,user,client_id,lock=False):
    query=scoped_query(db,user).filter(Client.id==client_id)
    row=(query.with_for_update() if lock else query).first()
    if not row:raise HTTPException(404,'Client not found.')
    return row


def officers(db,client_id):
    return [{'id':s.id,'staff_code':s.staff_code,'name':s.name,'designation':s.profile.get('designation',''),'branch':s.profile.get('branch',''),'status':s.status} for s in db.query(InternalStaff).join(ClientStaffAssignment,ClientStaffAssignment.staff_id==InternalStaff.id).filter(ClientStaffAssignment.client_id==client_id,ClientStaffAssignment.is_active.is_(True)).order_by(InternalStaff.name).all()]


def response(db,row,counts=True):
    profile={**(row.profile or {}),'company_name':row.company_name,'gstin':row.gstin or row.gst_number or '',
             'billing_address':row.billing_address,'contact_person':row.contact_person,'contact_email':row.contact_email,
             'contact_phone':row.contact_phone,'branch':row.branch or '', 'branch_region':row.branch_region or '',
             'credit_terms_days':row.credit_terms_days,'portal_user_id':row.user_id,'is_active':row.is_active}
    assigned=officers(db,row.id);profile['field_officer_ids']=[s['id'] for s in assigned]
    result={'id':row.id,'client_code':row.client_code,'version':row.version,'profile':profile,**profile,
            'field_officers':', '.join(s['name'] for s in assigned),'assigned_staff':assigned}
    if counts:
        result['site_count']=db.query(Site).filter_by(client_id=row.id,is_active=True).count()
        contract=db.execute(text("select count(*) as total,min(contract_end_date) as expiry from client_contracts where client_id=:id and status in ('ACTIVE','RENEWED')"),{'id':row.id}).mappings().one()
        expiry=contract['expiry']
        if isinstance(expiry,str):expiry=date.fromisoformat(expiry)
        days=(expiry-date.today()).days if expiry else None
        result.update(active_contract_count=contract['total'],nearest_contract_end=expiry,renewal_status='EXPIRED' if days is not None and days<0 else 'EXPIRING_30' if days is not None and days<=30 else 'EXPIRING_60' if days is not None and days<=60 else 'NORMAL')
    return result


def eligible(staff):
    return staff.status=='ACTIVE' and (staff.profile.get('management_level') in {'UPPER_MANAGEMENT','MANAGEMENT','BRANCH_HEAD','FIELD_OFFICER'} or staff.profile.get('portal_role') in {'OWNER','SUPER_ADMIN','ADMIN','OPERATIONS','SUPERVISOR'})


def validate_links(db,profile,row=None):
    if profile.branch and (not row or row.branch!=profile.branch):
        company=db.get(CompanySettings,1)
        if not company or not any(b.get('code')==profile.branch and b.get('is_active',True) for b in company.profile.get('branches',[])):
            raise HTTPException(422,'Choose an active branch from Company Profile & Docs.')
    for staff_id in profile.field_officer_ids:
        staff=db.get(InternalStaff,staff_id)
        if not staff or not eligible(staff):raise HTTPException(422,'Field officers must be active operations or management staff from Staff Master.')
        region=staff.profile.get('region','')
        if region and region not in {'ALL_REGIONS',profile.branch_region}:raise HTTPException(422,'Assigned staff region does not match the client region.')
        branch=staff.profile.get('branch','')
        if branch and profile.branch and branch!=profile.branch:raise HTTPException(422,'Assigned staff branch does not match the client branch.')
    if profile.portal_user_id:
        account=db.get(User,profile.portal_user_id)
        if not account or not account.is_active or account.role!=UserRole.CLIENT:raise HTTPException(422,'Client portal access requires an active CLIENT account.')
        linked=db.query(Client).filter(Client.user_id==profile.portal_user_id)
        if row:linked=linked.filter(Client.id!=row.id)
        if linked.first():raise HTTPException(409,'This portal account is already assigned to another client.')
    gst=db.query(Client).filter(func.upper(Client.gstin)==profile.gstin)
    if row:gst=gst.filter(Client.id!=row.id)
    if gst.first():raise HTTPException(409,'A client with this GSTIN already exists.')


def save_values(row,profile):
    values=profile.model_dump(mode='json')
    for key in ['company_name','gstin','billing_address','contact_person','contact_email','contact_phone','branch','branch_region','credit_terms_days','is_active','registration_no','billing_cycle']:
        setattr(row,key,values[key])
    row.contract_start_date=profile.contract_start_date;row.contract_end_date=profile.contract_end_date
    row.gst_number=profile.gstin;row.user_id=profile.portal_user_id;row.profile=values
    row.updated_at=datetime.now(timezone.utc)


def assign(db,row,ids):
    db.query(ClientStaffAssignment).filter_by(client_id=row.id).update({'is_active':False})
    for staff_id in ids:
        existing=db.query(ClientStaffAssignment).filter_by(client_id=row.id,staff_id=staff_id).first()
        if existing:existing.is_active=True
        else:db.add(ClientStaffAssignment(client_id=row.id,staff_id=staff_id,is_active=True))
    db.flush()


def audit(db,row,user,action):
    db.add(ClientHistory(client_id=row.id,changed_by=user.id,action=action,snapshot={'client_code':row.client_code,'version':row.version,'profile':row.profile}))


@router.get('')
def list_clients(db:Session=Depends(get_db),user=Depends(reader)):
    return [response(db,row) for row in scoped_query(db,user).order_by(Client.id.desc()).all()]


@router.get('/options')
def options(db:Session=Depends(get_db),user=Depends(reader)):
    if user.role==UserRole.CLIENT:raise HTTPException(403,'Internal client setup only.')
    company=db.get(CompanySettings,1)
    branches=company.profile.get('branches',[]) if company else []
    staff=db.query(InternalStaff).filter_by(status='ACTIVE').order_by(InternalStaff.name).all()
    accounts=db.query(User).filter_by(role=UserRole.CLIENT,is_active=True).all() if user.role in {UserRole.OWNER,UserRole.SUPER_ADMIN,UserRole.ADMIN} else []
    return {'branches':[{'code':b['code'],'name':b['name']} for b in branches if b.get('is_active',True)],
            'staff':[{'id':s.id,'name':s.name,'staff_code':s.staff_code,'region':s.profile.get('region',''),'branch':s.profile.get('branch','')} for s in staff if eligible(s)],
            'portal_accounts':[{'id':u.id,'name':u.full_name,'login_id':u.login_id} for u in accounts]}


@router.get('/{client_id}')
def get_client(client_id:int,db:Session=Depends(get_db),user=Depends(reader)):
    return response(db,get_record(db,user,client_id))


@router.get('/{client_id}/field-officers')
def get_field_officers(client_id:int,db:Session=Depends(get_db),user=Depends(reader)):
    get_record(db,user,client_id)
    return officers(db,client_id)


@router.post('',status_code=201)
def create_client(profile:ClientProfile,db:Session=Depends(get_db),user=Depends(require_admin)):
    validate_links(db,profile)
    number=db.execute(update(ClientCodeCounter).where(ClientCodeCounter.id==1).values(next_number=ClientCodeCounter.next_number+1).returning(ClientCodeCounter.next_number)).scalar_one_or_none()
    if number is None:raise HTTPException(503,'Client code allocation is not configured.')
    row=Client(client_code=f'C-DAS-{number-1:04d}',version=1)
    save_values(row,profile);db.add(row)
    try:
        db.flush();assign(db,row,profile.field_officer_ids);audit(db,row,user,'CREATE')
        result=response(db,row);db.commit();return result
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Client name, GSTIN or portal account already exists.') from None


@router.patch('/{client_id}')
def update_client(client_id:int,data:ClientUpdate,db:Session=Depends(get_db),user=Depends(require_admin)):
    row=get_record(db,user,client_id,True)
    if db.execute(update(Client).where(Client.id==client_id,Client.version==data.version).values(version=data.version+1)).rowcount!=1:
        db.rollback();raise HTTPException(409,'This client changed. Reload before saving.')
    db.refresh(row);validate_links(db,data.profile,row);save_values(row,data.profile)
    try:
        db.flush();assign(db,row,data.profile.field_officer_ids);audit(db,row,user,'UPDATE')
        result=response(db,row);db.commit();return result
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Client name, GSTIN or portal account already exists.') from None
