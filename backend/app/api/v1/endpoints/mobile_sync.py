from datetime import datetime,timedelta,timezone
import hashlib,re,uuid
from fastapi import APIRouter,Depends,File,HTTPException,UploadFile
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError,jwt
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_password_hash,verify_password
from app.core.supabase_auth import create_supabase_signed_url,upload_supabase_storage
from app.services import attendance as rules
from app.api.v1.endpoints.employee_documents import _magic_ok,_storage_request

router=APIRouter()
mobile_oauth=OAuth2PasswordBearer(tokenUrl='/api/v1/mobile/login')
class MobileLoginRequest(rules.Strict):
    phone:str=Field(min_length=10,max_length=20)
    pin:str=Field(pattern=r'^\d{8,12}$')
MobilePunchRequest=rules.Punch
# Equal-cost verification for unknown accounts; never persist this dummy credential.
_DUMMY_HASH=get_password_hash('000000000000')
def _clean_phone(value):
    digits=re.sub(r'\D','',value or '')
    return digits[-10:] if len(digits) in {10,12} and (len(digits)==10 or digits.startswith('91')) else ''
def _mobile_token(employee_id,version):
    return jwt.encode({'sub':f'employee:{employee_id}','mobile':True,'sv':version,'exp':rules.now()+timedelta(hours=12)},settings.SECRET_KEY,algorithm=settings.ALGORITHM)
def _mobile_employee_id(token):
    try:
        p=jwt.decode(token,settings.SECRET_KEY,algorithms=[settings.ALGORITHM])
        if p.get('mobile') is not True or not p.get('sub','').startswith('employee:'):raise ValueError
        return str(uuid.UUID(p['sub'].split(':',1)[1])),p.get('sv')
    except (JWTError,ValueError,TypeError):raise HTTPException(401,'Mobile session is invalid or expired.')

def get_mobile_employee(token:str=Depends(mobile_oauth),db:Session=Depends(get_db)):
    eid,version=_mobile_employee_id(token)
    record=rules.row(db,"""select e.id,e.employee_code,e.name,e.phone,e.status,e.designation,e.site_id,a.session_version from employees e join employee_attendance_access a on a.employee_id=e.id join employee_joining_drafts j on j.employee_id=e.id where e.id=:id and upper(e.status)='ACTIVE' and j.status='APPROVED'""",{'id':eid})
    if not record or version!=record['session_version']:raise HTTPException(401,'Employee session is inactive or expired. Sign in again.')
    return record

def personal(db,employee):
    result={k:v for k,v in dict(employee).items() if k!='session_version'}
    # An overnight open shift takes precedence over today's new assignment.
    site=rules.row(db,"""select r.id roster_id,r.date roster_date,r.shift_type,s.site_name,s.address site_address,s.latitude site_latitude,s.longitude site_longitude,coalesce(s.geofence_radius_meters,100) geofence_radius from shift_rosters r join guard_profiles g on g.id=r.guard_id join sites s on s.id=r.site_id left join attendance a on a.roster_id=r.id where g.employee_id=:id and r.status='SCHEDULED' and (r.date=:today or (a.check_in_time is not null and a.check_out_time is null)) order by case when a.check_in_time is not null then 0 else 1 end,r.date limit 1""",{'id':str(employee['id']),'today':rules.business_date()})
    if site:result.update(dict(site))
    else:
        result.update({'roster_id':None,'site_name':None,'site_latitude':None,'site_longitude':None})
    return result

@router.post('/login')
@router.post('/mobile/login',include_in_schema=False)
def mobile_login(payload:MobileLoginRequest,db:Session=Depends(get_db)):
    phone=_clean_phone(payload.phone)
    if not phone:raise HTTPException(422,'Enter an Indian 10-digit phone number, optionally prefixed by 91.')
    record=rules.row(db,"""select e.id,e.employee_code,e.name,e.phone,e.status,e.designation,e.site_id,a.pin_hash,a.session_version,a.failed_attempts,a.locked_until from employees e join employee_attendance_access a on a.employee_id=e.id join employee_joining_drafts j on j.employee_id=e.id where right(regexp_replace(coalesce(e.phone,''),'[^0-9]','','g'),10)=:phone and upper(e.status)='ACTIVE' and j.status='APPROVED' for update of a""",{'phone':phone})
    valid=verify_password(payload.pin,record['pin_hash'] if record else _DUMMY_HASH)
    if record and record['locked_until'] and rules.stamp(record['locked_until'])>rules.now():raise HTTPException(429,'Too many attempts. Try again after 15 minutes.')
    if not record or not valid:
        if record:
            attempts=record['failed_attempts']+1
            db.execute(text('update employee_attendance_access set failed_attempts=:attempts,locked_until=:until where employee_id=:id'),{'id':record['id'],'attempts':attempts,'until':rules.now()+timedelta(minutes=15) if attempts>=5 else None});db.commit()
        raise HTTPException(401,'Phone or PIN is incorrect, or employee access has not been enabled.')
    db.execute(text('update employee_attendance_access set failed_attempts=0,locked_until=null where employee_id=:id'),{'id':record['id']});db.commit()
    employee={k:v for k,v in dict(record).items() if k not in {'pin_hash','failed_attempts','locked_until'}}
    return {'access_token':_mobile_token(str(record['id']),record['session_version']),'token_type':'bearer','employee':personal(db,employee)}

@router.post('/selfie')
@router.post('/mobile/selfie',include_in_schema=False)
async def mobile_selfie(employee=Depends(get_mobile_employee),file:UploadFile=File(...),kind:str='check-in',db:Session=Depends(get_db)):
    if kind not in {'check-in','check-out'}:raise HTTPException(422,'Invalid selfie type.')
    extensions={'image/jpeg':'jpg','image/png':'png','image/webp':'webp'}
    if file.content_type not in extensions:raise HTTPException(415,'Selfie must be JPEG, PNG or WebP.')
    data=await file.read(3*1024*1024+1)
    if len(data)>3*1024*1024:raise HTTPException(413,'Selfie maximum size is 3 MB.')
    if not _magic_ok(file.content_type,data):raise HTTPException(415,'Selfie content does not match its image type.')
    path=f"{employee['id']}/{rules.business_date().isoformat()}/{kind}-{uuid.uuid4().hex}.{extensions[file.content_type]}"
    stored=upload_supabase_storage(bucket='employee-selfies',path=path,data=data,content_type=file.content_type)
    if not stored:raise HTTPException(503,'Selfie storage is temporarily unavailable.')
    try:
        db.execute(text('insert into attendance_selfies(employee_id,kind,storage_path,mime_type,sha256) values (:employee,:kind,:path,:mime,:hash)'),{'employee':str(employee['id']),'kind':kind,'path':stored,'mime':file.content_type,'hash':hashlib.sha256(data).hexdigest()});db.commit()
    except Exception:
        db.rollback()
        try:_storage_request('DELETE','object/employee-selfies/'+stored)
        except HTTPException:pass
        raise
    return {'path':stored}

@router.get('/me')
@router.get('/mobile/me',include_in_schema=False)
def mobile_me(employee=Depends(get_mobile_employee),db:Session=Depends(get_db)):return personal(db,employee)
@router.get('/me/attendance')
@router.get('/mobile/me/attendance',include_in_schema=False)
def mobile_attendance(employee=Depends(get_mobile_employee),db:Session=Depends(get_db)):
    return [rules.public(r) for r in db.execute(text('''select a.*,r.shift_type,r.date roster_date,s.site_name from attendance a left join shift_rosters r on r.id=a.roster_id left join sites s on s.id=r.site_id where a.employee_id=:employee order by a.attendance_date desc limit 100'''),{'employee':str(employee['id'])}).mappings().all()]
@router.get('/me/salary')
@router.get('/mobile/me/salary',include_in_schema=False)
def mobile_salary(employee=Depends(get_mobile_employee),db:Session=Depends(get_db)):
    return [dict(r) for r in db.execute(text('select id,employee_id,month,status,credited_date from salary_records where employee_id=:employee order by month desc limit 24'),{'employee':str(employee['id'])}).mappings().all()]
@router.post('/punch')
@router.post('/mobile/punch',include_in_schema=False)
def mobile_punch(payload:MobilePunchRequest,employee=Depends(get_mobile_employee),db:Session=Depends(get_db)):
    try:result=rules.punch(db,payload,employee['id']);db.commit();return result
    except Exception:db.rollback();raise
