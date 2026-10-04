from app.core.business_time import business_date
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import update, func, or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.api.deps import require_ops_or_admin
from app.core.database import get_db
from app.models.site import Site
from app.models.client import Client, ClientStaffAssignment
from app.models.company import CompanySettings
from app.models.internal_staff import InternalStaff
from app.models.commercial import ClientContract, SiteCodeCounter, SiteRateCard, CommercialHistory
from app.schemas.commercial import SiteProfile, SiteUpdate
from app.api.v1.endpoints.client_master import eligible

router = APIRouter()


def record(db, site_id, lock=False):
    q = db.query(Site).filter_by(id=site_id)
    row = (q.with_for_update() if lock else q).first()
    if not row: raise HTTPException(404, 'Site not found.')
    return row


def coordinator_options(db, client_id):
    rows = db.query(InternalStaff).join(ClientStaffAssignment, ClientStaffAssignment.staff_id == InternalStaff.id).filter(ClientStaffAssignment.client_id == client_id, ClientStaffAssignment.is_active.is_(True)).all()
    return [{'id':s.id,'name':s.name,'staff_code':s.staff_code,'branch':s.profile.get('branch','')} for s in rows if eligible(s)]


def validate(db, data, row=None):
    client = db.get(Client, data.client_id)
    if not client or (not client.is_active and (not row or data.is_active)): raise HTTPException(422, 'Choose an active client, or inactivate its existing site.')
    if row and row.client_id != data.client_id: raise HTTPException(422, 'A saved site cannot be moved to another client.')
    if client.branch and data.branch != client.branch:
        raise HTTPException(422, 'Site branch must match the client branch.')
    if data.branch and (not row or data.branch != row.branch):
        company = db.get(CompanySettings, 1)
        if not company or not any(b['code'] == data.branch and b.get('is_active',True) for b in company.profile.get('branches', [])):
            raise HTTPException(422, 'Choose an active company branch.')
    if data.contract_id:
        contract = db.get(ClientContract, data.contract_id)
        if not contract or contract.client_id != client.id or (contract.status not in {'DRAFT','ACTIVE','RENEWED'} and (not row or row.contract_id!=data.contract_id)):
            raise HTTPException(422, 'Choose a current or draft contract belonging to this client.')
    valid_staff = {s['id']:s for s in coordinator_options(db, client.id)}
    for sid in data.field_officer_ids:
        if sid not in valid_staff: raise HTTPException(422, 'Site coordinators must be active internal staff assigned to this client.')
        if valid_staff[sid]['branch'] and valid_staff[sid]['branch'] != data.branch:
            raise HTTPException(422, 'Coordinator branch must match the site branch.')
    duplicate = db.query(Site).filter(Site.client_id == data.client_id, func.lower(Site.site_name) == data.site_name.lower())
    if row: duplicate = duplicate.filter(Site.id != row.id)
    if duplicate.first(): raise HTTPException(409, 'This client already has a site with that name.')
    if row and row.contract_id != data.contract_id and db.query(SiteRateCard).filter(SiteRateCard.site_id==row.id,SiteRateCard.is_active.is_(True),or_(SiteRateCard.effective_to.is_(None),SiteRateCard.effective_to>=business_date())).first():
        raise HTTPException(409, 'End the current and upcoming site rates before changing its contract.')
    return client


def save_values(row, data, client):
    values = data.model_dump(mode='json')
    for key in ['client_id','site_name','address','city','state','postal_code','branch','contract_id','contact_phone','latitude','longitude','geofence_radius_meters','is_active']:
        setattr(row,key,getattr(data,key))
    row.shift_requirements = values['shift_requirements']
    row.branch_region = client.branch_region
    row.profile = values


def response(db, row):
    client = db.get(Client,row.client_id)
    profile = {**(row.profile or {})}
    for key in ['client_id','site_name','address','city','state','postal_code','branch','contract_id','contact_phone','latitude','longitude','geofence_radius_meters','is_active','shift_requirements']:
        profile[key] = getattr(row,key)
    ids = profile.get('field_officer_ids',[])
    names = [{'id':s.id,'name':s.name,'staff_code':s.staff_code,'status':s.status} for s in db.query(InternalStaff).filter(InternalStaff.id.in_(ids)).all()] if ids else []
    return {**profile,'id':row.id,'site_code':row.site_code,'version':row.version,'profile':profile,'company_name':client.company_name,'branch_region':row.branch_region,'assigned_staff':names,'rate_card_count':db.query(SiteRateCard).filter_by(site_id=row.id,is_active=True).count()}


def audit(db,row,user,action):
    db.add(CommercialHistory(site_id=row.id,changed_by=user.id,action=action,snapshot=jsonable_encoder({'site_code':row.site_code,'version':row.version,'profile':row.profile})))


@router.get('')
def list_sites(db:Session=Depends(get_db),user=Depends(require_ops_or_admin)):
    return [response(db,row) for row in db.query(Site).order_by(Site.id.desc()).all()]


@router.get('/options')
def options(db:Session=Depends(get_db),user=Depends(require_ops_or_admin)):
    company = db.get(CompanySettings,1)
    return {'branches':[{'code':b['code'],'name':b['name']} for b in (company.profile.get('branches',[]) if company else []) if b.get('is_active',True)],
            'clients':[{'id':c.id,'company_name':c.company_name,'branch':c.branch or '', 'branch_region':c.branch_region,'staff':coordinator_options(db,c.id)} for c in db.query(Client).filter_by(is_active=True).order_by(Client.company_name).all()],
            'contracts':[{'id':c.id,'client_id':c.client_id,'contract_number':c.contract_number,'status':c.status} for c in db.query(ClientContract).filter(ClientContract.status.in_(['DRAFT','ACTIVE','RENEWED'])).all()]}


@router.get('/{site_id}')
def get_site(site_id:int,db:Session=Depends(get_db),user=Depends(require_ops_or_admin)):
    return response(db,record(db,site_id))


@router.get('/{site_id}/history')
def history(site_id:int,db:Session=Depends(get_db),user=Depends(require_ops_or_admin)):
    record(db,site_id)
    return [{'id':h.id,'action':h.action,'changed_by':h.changed_by,'created_at':h.created_at,'snapshot':h.snapshot} for h in db.query(CommercialHistory).filter_by(site_id=site_id,rate_id=None).order_by(CommercialHistory.id.desc()).limit(100).all()]


@router.post('',status_code=201)
def create_site(data:SiteProfile,db:Session=Depends(get_db),user=Depends(require_ops_or_admin)):
    client = validate(db,data)
    # The counter update serializes allocation and rolls back with a failed save.
    number = db.execute(update(SiteCodeCounter).where(SiteCodeCounter.id==1).values(next_number=SiteCodeCounter.next_number+1).returning(SiteCodeCounter.next_number)).scalar_one_or_none()
    if number is None: raise HTTPException(503,'Site code allocation is not configured.')
    row = Site(site_code=f'SITE-DAS-{number-1:04d}',version=1)
    save_values(row,data,client);db.add(row)
    try:
        db.flush();audit(db,row,user,'CREATE');result=response(db,row);db.commit();return result
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Site name or code already exists.') from None


@router.patch('/{site_id}')
def update_site(site_id:int,data:SiteUpdate,db:Session=Depends(get_db),user=Depends(require_ops_or_admin)):
    row = record(db,site_id,True)
    if row.version != data.version: raise HTTPException(409,'This site changed. Reload before saving.')
    client = validate(db,data.profile,row)
    try:
        if db.execute(update(Site).where(Site.id==site_id,Site.version==data.version).values(version=data.version+1)).rowcount != 1:
            db.rollback();raise HTTPException(409,'This site changed. Reload before saving.')
        db.refresh(row);save_values(row,data.profile,client);db.flush();audit(db,row,user,'UPDATE')
        result=response(db,row);db.commit();return result
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Site name or code already exists.') from None
