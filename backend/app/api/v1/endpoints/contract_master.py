from app.core.business_time import business_date
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, update
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.api.deps import require_admin, get_current_active_user
from app.core.database import get_db
from app.models.client import Client
from app.models.site import Site
from app.models.commercial import ClientContract, SiteRateCard, CommercialHistory
from app.schemas.commercial import ContractProfile, ContractUpdate, RateProfile, RateUpdate
from app.models.enums import UserRole

router = APIRouter()
OFFICE = {UserRole.OWNER,UserRole.SUPER_ADMIN,UserRole.ADMIN,UserRole.HR,UserRole.OPERATIONS,UserRole.ACCOUNTS}


def reader(user=Depends(get_current_active_user)):
    if user.role not in OFFICE: raise HTTPException(403,'Commercial records require internal office access.')
    return user


def contract_record(db,contract_id,lock=False):
    q=db.query(ClientContract).filter_by(id=contract_id)
    row=(q.with_for_update() if lock else q).first()
    if not row: raise HTTPException(404,'Contract not found.')
    return row


def rate_record(db,site_id,rate_id):
    row=db.query(SiteRateCard).filter_by(id=rate_id,site_id=site_id).with_for_update().first()
    if not row: raise HTTPException(404,'Rate card not found at this site.')
    return row


def rate_site(db,site_id,lock=False):
    q=db.query(Site).filter_by(id=site_id)
    row=(q.with_for_update() if lock else q).first()
    if not row: raise HTTPException(404,'Site not found.')
    return row


def renewal(end):
    days=(end-business_date()).days
    return 'EXPIRED' if days<0 else 'EXPIRING_30' if days<=30 else 'EXPIRING_60' if days<=60 else 'NORMAL'


def contract_response(db,row):
    profile={**(row.profile or {})}
    for key in ContractProfile.model_fields:
        if hasattr(row,key): profile[key]=getattr(row,key)
    return {**profile,'id':row.id,'version':row.version,'profile':profile,'company_name':db.get(Client,row.client_id).company_name,'renewal_status':renewal(row.contract_end_date),'site_count':db.query(Site).filter_by(contract_id=row.id).count()}


def rate_response(row):
    profile={key:getattr(row,key) for key in RateProfile.model_fields}
    profile['vertical']='HEALTHCARE' if row.vertical=='NURSING' else row.vertical
    # Commercial money remains decimal strings for API consumers.
    for key in ['daily_rate','hourly_rate','monthly_rate','duty_hours','wage_indexation_percent']: profile[key]=str(profile[key])
    return {**profile,'id':row.id,'site_id':row.site_id,'version':row.version,'profile':profile}


def audit(db,user,action,snapshot,**links):
    from fastapi.encoders import jsonable_encoder
    db.add(CommercialHistory(changed_by=user.id,action=action,snapshot=jsonable_encoder(snapshot),**links))


def validate_contract(db,data,row=None):
    client=db.get(Client,data.client_id)
    if not client or (not client.is_active and (not row or data.status not in {'EXPIRED','TERMINATED'})): raise HTTPException(422,'Choose an active client, or close its existing contract.')
    if row and row.client_id!=data.client_id: raise HTTPException(422,'A contract cannot be moved to another client.')
    duplicate=db.query(ClientContract).filter(func.upper(ClientContract.contract_number)==data.contract_number)
    if row: duplicate=duplicate.filter(ClientContract.id!=row.id)
    if duplicate.first(): raise HTTPException(409,'Contract reference already exists.')
    if row:
        for rate in db.query(SiteRateCard).filter_by(contract_id=row.id,is_active=True).all():
            end=rate.effective_to
            if rate.effective_from<data.contract_start_date or not end or end>data.contract_end_date:
                raise HTTPException(409,'Contract dates must cover every active rate card. Update rate validity first.')
            vertical='HEALTHCARE' if rate.vertical=='NURSING' else rate.vertical
            if vertical not in data.service_verticals: raise HTTPException(409,'The contract must retain services used by active rate cards.')
        if row.status in {'TERMINATED','EXPIRED'} and data.status in {'ACTIVE','RENEWED'}:
            raise HTTPException(409,'Create a new contract reference to renew a closed contract.')


def save_contract(row,data):
    for key in ['client_id','contract_number','contract_start_date','contract_end_date','billing_cycle','credit_terms_days','wage_indexation_percent','status','renewal_notes']: setattr(row,key,getattr(data,key))
    row.profile=data.model_dump(mode='json')


def validate_rate(db,site,data,row=None):
    if not site.is_active or not db.get(Client,site.client_id).is_active: raise HTTPException(422,'Rate cards require an active site and client.')
    contract=contract_record(db,data.contract_id,True)
    if contract.client_id!=site.client_id or contract.status not in {'ACTIVE','RENEWED'}:
        raise HTTPException(422,'Rate cards require an active contract for the site’s client.')
    if not site.contract_id or site.contract_id!=contract.id: raise HTTPException(422,'Choose the contract linked to this site.')
    if data.vertical not in contract.profile.get('service_verticals',[]): raise HTTPException(422,'This service is outside the contract scope.')
    if data.effective_from<contract.contract_start_date or data.effective_from>contract.contract_end_date or (data.effective_to and data.effective_to>contract.contract_end_date):
        raise HTTPException(422,'Rate validity must stay inside the contract period.')
    if not data.effective_to: data.effective_to=contract.contract_end_date
    if row:
        old=rate_response(row)['profile'];new=data.model_dump(mode='json')
        if row.effective_from<=business_date():
            protected=['contract_id','vertical','category','rate_basis','daily_rate','hourly_rate','monthly_rate','duty_hours','billable_days','wage_indexation_percent','effective_from']
            # Compare native values so decimal representation does not change equality.
            if any(getattr(row,k)!=getattr(data,k) for k in protected if k!='vertical') or old['vertical']!=new['vertical']:
                raise HTTPException(409,'A rate that has started cannot be repriced. End it and add a dated successor.')
            if data.effective_to!=row.effective_to and data.effective_to<business_date(): raise HTTPException(422,'An existing rate cannot be ended retrospectively.')
            if data.is_active!=row.is_active: raise HTTPException(409,'A rate that has started must retain its billing history. Set an end date instead of changing its active flag.')
        if row.is_active and not data.is_active and not data.notes:
            raise HTTPException(422,'Enter a reason when retiring a rate card.')
    if data.is_active:
        vertical='NURSING' if data.vertical=='HEALTHCARE' else data.vertical
        overlap=db.query(SiteRateCard).filter(SiteRateCard.site_id==site.id,SiteRateCard.vertical==vertical,func.upper(SiteRateCard.category)==data.category,SiteRateCard.is_active.is_(True),SiteRateCard.effective_from<=data.effective_to,or_(SiteRateCard.effective_to.is_(None),SiteRateCard.effective_to>=data.effective_from))
        if row: overlap=overlap.filter(SiteRateCard.id!=row.id)
        if overlap.first(): raise HTTPException(409,'An active rate already covers this service/category and period. End the earlier rate first.')


def save_rate(row,data):
    for key in RateProfile.model_fields: setattr(row,key,getattr(data,key))
    row.vertical='NURSING' if data.vertical=='HEALTHCARE' else data.vertical


@router.get('')
def list_contracts(db:Session=Depends(get_db),user=Depends(reader)):
    return [contract_response(db,r) for r in db.query(ClientContract).order_by(ClientContract.contract_end_date).all()]


@router.get('/options')
def options(db:Session=Depends(get_db),user=Depends(reader)):
    return {'clients':[{'id':c.id,'company_name':c.company_name,'billing_cycle':c.billing_cycle,'credit_terms_days':c.credit_terms_days} for c in db.query(Client).filter_by(is_active=True).order_by(Client.company_name).all()],
            'sites':[{'id':s.id,'client_id':s.client_id,'site_name':s.site_name,'site_code':s.site_code,'contract_id':s.contract_id} for s in db.query(Site).filter_by(is_active=True).order_by(Site.site_name).all()]}


@router.get('/site/{site_id}/rates')
def list_rates(site_id:int,db:Session=Depends(get_db),user=Depends(reader)):
    rate_site(db,site_id)
    return [rate_response(r) for r in db.query(SiteRateCard).filter_by(site_id=site_id).order_by(SiteRateCard.effective_from.desc()).all()]


@router.post('/site/{site_id}/rates',status_code=201)
def create_rate(site_id:int,data:RateProfile,db:Session=Depends(get_db),user=Depends(require_admin)):
    site=rate_site(db,site_id,True);validate_rate(db,site,data)
    row=SiteRateCard(site_id=site_id,version=1);save_rate(row,data);db.add(row)
    try:
        db.flush();result=rate_response(row);audit(db,user,'CREATE_RATE',result,site_id=site_id,contract_id=row.contract_id,rate_id=row.id);db.commit();return result
    except IntegrityError:
        db.rollback();raise HTTPException(409,'A rate card already exists for this service/category and start date.') from None


@router.patch('/site/{site_id}/rates/{rate_id}')
def update_rate(site_id:int,rate_id:int,data:RateUpdate,db:Session=Depends(get_db),user=Depends(require_admin)):
    site=rate_site(db,site_id,True);row=rate_record(db,site_id,rate_id)
    if row.version!=data.version: raise HTTPException(409,'This rate changed. Reload before saving.')
    validate_rate(db,site,data.profile,row)
    try:
        if db.execute(update(SiteRateCard).where(SiteRateCard.id==rate_id,SiteRateCard.version==data.version).values(version=data.version+1)).rowcount!=1:
            db.rollback();raise HTTPException(409,'This rate changed. Reload before saving.')
        db.refresh(row);save_rate(row,data.profile);db.flush();result=rate_response(row)
        audit(db,user,'UPDATE_RATE',result,site_id=site_id,contract_id=row.contract_id,rate_id=row.id);db.commit();return result
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Rate card conflicts with another record.') from None


@router.get('/{contract_id}')
def get_contract(contract_id:int,db:Session=Depends(get_db),user=Depends(reader)):
    return contract_response(db,contract_record(db,contract_id))


@router.get('/{contract_id}/history')
def history(contract_id:int,db:Session=Depends(get_db),user=Depends(reader)):
    contract_record(db,contract_id)
    return [{'id':h.id,'action':h.action,'changed_by':h.changed_by,'created_at':h.created_at,'snapshot':h.snapshot} for h in db.query(CommercialHistory).filter_by(contract_id=contract_id).order_by(CommercialHistory.id.desc()).limit(100).all()]


@router.post('',status_code=201)
def create_contract(data:ContractProfile,db:Session=Depends(get_db),user=Depends(require_admin)):
    validate_contract(db,data);row=ClientContract(version=1);save_contract(row,data);db.add(row)
    try:
        db.flush();result=contract_response(db,row);audit(db,user,'CREATE_CONTRACT',result,contract_id=row.id);db.commit();return result
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Contract reference already exists.') from None


@router.patch('/{contract_id}')
def update_contract(contract_id:int,data:ContractUpdate,db:Session=Depends(get_db),user=Depends(require_admin)):
    row=contract_record(db,contract_id,True)
    if row.version!=data.version: raise HTTPException(409,'This contract changed. Reload before saving.')
    validate_contract(db,data.profile,row)
    try:
        if db.execute(update(ClientContract).where(ClientContract.id==contract_id,ClientContract.version==data.version).values(version=data.version+1)).rowcount!=1:
            db.rollback();raise HTTPException(409,'This contract changed. Reload before saving.')
        db.refresh(row);save_contract(row,data.profile);db.flush();result=contract_response(db,row)
        audit(db,user,'UPDATE_CONTRACT',result,contract_id=row.id);db.commit();return result
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Contract reference already exists.') from None
