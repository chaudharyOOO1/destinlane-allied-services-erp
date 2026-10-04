"""Employee joining rules shared by the directory, documents and deployment APIs."""
import json
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from fastapi import HTTPException
from sqlalchemy import text
from app.core.business_time import business_date
from app.models.company import CompanySettings

BASIC = {'name','father_name','phone','dob','gender','designation','branch','site_id','joining_date','category','aadhaar_no','pan_no','permanent_address','present_address','emergency_contact','marital_status','client_id'}
EXTRA = {'vertical','emergency_name','emergency_relation','uan','esic_number','nominee_name','nominee_relation','nominee_dob','nominee_aadhaar','nominee_percentage','bank_account_no','bank_name','bank_branch','bank_ifsc','gun_license_no','arms_issuing_authority','gun_license_expiry','arms_caliber','weapon_serial_no','ammunition_count','jurisdiction_limits','uniform_shirt','uniform_trousers','uniform_shoes','uniform_belt','uniform_cap','uniform_total_cost','uniform_monthly_emi','uniform_issue_date','notes'}
DATES = {'dob','joining_date','nominee_dob','gun_license_expiry','uniform_issue_date'}
REQUIRED = {'name','father_name','phone','dob','gender','designation','branch','client_id','joining_date','category','aadhaar_no','pan_no','permanent_address','present_address','emergency_contact','marital_status','vertical','bank_account_no','bank_ifsc','bank_name','bank_branch','nominee_name','nominee_relation'}
DOCUMENTS = {'PHOTO','AADHAAR','PAN','FORM_11','ESIC_FORM','BANK_PASSBOOK','POLICE_VERIFICATION','MEDICAL_FITNESS'}
CRITICAL = {'POLICE_VERIFICATION','MEDICAL_FITNESS','GUN_LICENSE'}


def aadhaar_valid(value):
    d=((0,1,2,3,4,5,6,7,8,9),(1,2,3,4,0,6,7,8,9,5),(2,3,4,0,1,7,8,9,5,6),(3,4,0,1,2,8,9,5,6,7),(4,0,1,2,3,9,5,6,7,8),(5,9,8,7,6,0,4,3,2,1),(6,5,9,8,7,1,0,4,3,2),(7,6,5,9,8,2,1,0,4,3),(8,7,6,5,9,3,2,1,0,4),(9,8,7,6,5,4,3,2,1,0))
    p=((0,1,2,3,4,5,6,7,8,9),(1,5,7,6,2,8,3,0,9,4),(5,8,0,3,7,9,1,6,4,2),(8,9,1,6,0,4,3,5,2,7),(9,4,5,3,1,2,6,8,7,0),(4,2,8,6,5,7,3,9,0,1),(2,7,9,3,8,0,6,4,1,5),(7,0,4,6,9,1,3,2,5,8))
    if not re.fullmatch(r'[2-9]\d{11}',str(value)): return False
    c=0
    for i,n in enumerate(reversed(value)): c=d[c][p[i%8][int(n)]]
    return c == 0


def clean_profile(payload):
    unknown = set(payload) - BASIC - EXTRA
    if unknown: raise HTTPException(422,'Unknown employee fields: '+', '.join(sorted(unknown)))
    result={}
    for key,value in payload.items():
        if isinstance(value,str): value=value.strip()
        if value in ('',None): result[key]=None; continue
        numeric={'client_id','site_id','ammunition_count','uniform_total_cost','uniform_monthly_emi','nominee_percentage'}
        flags={'uniform_shirt','uniform_trousers','uniform_shoes','uniform_belt','uniform_cap'}
        if key not in numeric|flags and not isinstance(value,(str,date)): raise HTTPException(422,f'{key} must be text.')
        if key in {'name','father_name','designation','branch','bank_name','bank_branch','nominee_name'} and (not isinstance(value,str) or len(value)>150): raise HTTPException(422,f'Invalid {key}.')
        if isinstance(value,str) and len(value)>2000: raise HTTPException(422,f'{key} is too long.')
        if key in DATES:
            try: parsed=date.fromisoformat(str(value))
            except ValueError: raise HTTPException(422,f'{key} must be a valid date.')
            if key in {'dob','nominee_dob'} and parsed>=business_date(): raise HTTPException(422,f'{key} must be in the past.')
            value=parsed.isoformat()
        if key in {'phone','emergency_contact'}:
            value=re.sub(r'[\s()-]','',str(value)).removeprefix('+91')
            if not re.fullmatch(r'[6-9]\d{9}',value): raise HTTPException(422,f'{key} must be a ten digit Indian mobile number.')
        if key in {'aadhaar_no','nominee_aadhaar'}:
            value=re.sub(r'\s','',str(value))
            if not aadhaar_valid(value): raise HTTPException(422,f'{key} failed Aadhaar checksum validation.')
        if key in {'pan_no','bank_ifsc','gender','category','vertical','marital_status'}: value=str(value).upper()
        if key=='pan_no' and not re.fullmatch(r'[A-Z]{5}\d{4}[A-Z]',value): raise HTTPException(422,'PAN format is invalid.')
        if key=='bank_ifsc' and not re.fullmatch(r'[A-Z]{4}0[A-Z0-9]{6}',value): raise HTTPException(422,'IFSC format is invalid.')
        if key=='bank_account_no' and not re.fullmatch(r'\d{6,25}',str(value)): raise HTTPException(422,'Bank account must contain 6–25 digits.')
        if key=='uan' and not re.fullmatch(r'\d{12}',str(value)): raise HTTPException(422,'UAN must contain 12 digits.')
        if key=='esic_number' and not re.fullmatch(r'\d{10}',str(value)): raise HTTPException(422,'ESIC number must contain 10 digits.')
        if key=='vertical' and value not in {'SECURITY','HOUSEKEEPING','NURSING'}: raise HTTPException(422,'Choose Security, Housekeeping or Nursing.')
        if key=='gender' and value not in {'MALE','FEMALE','OTHER'}: raise HTTPException(422,'Invalid gender.')
        if key=='category' and value not in {'GUARD','GUNMAN','SUPERVISOR','FIELD_OFFICER','JANITOR','CLEANER','FACILITY_ATTENDANT','GDA','NURSE_ASSISTANT','HOSPITAL_ATTENDANT'}: raise HTTPException(422,'Invalid workforce category.')
        if key in {'client_id','site_id','ammunition_count'}:
            try:
                if isinstance(value,bool) or not re.fullmatch(r'\d+',str(value)): raise ValueError()
                value=int(value)
                if value< (0 if key=='ammunition_count' else 1): raise ValueError()
            except (ValueError,TypeError): raise HTTPException(422,f'Invalid {key}.')
        if key in {'uniform_total_cost','uniform_monthly_emi','nominee_percentage'}:
            try:
                number=Decimal(str(value))
                if not number.is_finite() or number<0 or number>Decimal('99999999') or (key=='nominee_percentage' and not 0<number<=100): raise InvalidOperation()
                value=str(number.quantize(Decimal('.01')))
            except (InvalidOperation,ValueError): raise HTTPException(422,f'Invalid {key}.')
        if key.startswith('uniform_') and key not in {'uniform_total_cost','uniform_monthly_emi','uniform_issue_date'} and not isinstance(value,bool): raise HTTPException(422,f'{key} must be true or false.')
        result[key]=value
    return result


def employee(db,eid,lock=False):
    row=db.execute(text('select * from employees where id=:id'+(' for update' if lock else '')),{'id':str(eid)}).mappings().first()
    if not row: raise HTTPException(404,'Employee not found.')
    return dict(row)


def profile(row):
    return {**(row.get('profile') or {}),**{k:row.get(k) for k in BASIC}}


def validate_links(db,p):
    company=db.get(CompanySettings,1)
    if not company or not any(x.get('code')==p.get('branch') and x.get('is_active',True) for x in company.profile.get('branches',[])): raise HTTPException(422,'Choose an active branch from Company Profile & Docs.')
    client=db.execute(text('select id,is_active from clients where id=:id'),{'id':p.get('client_id')}).mappings().first()
    if not client or not client['is_active']: raise HTTPException(422,'Choose an active client.')
    if p.get('site_id'):
        site=db.execute(text('select client_id,is_active,branch from sites where id=:id'),{'id':p['site_id']}).mappings().first()
        if not site or not site['is_active'] or site['client_id']!=p.get('client_id') or (site['branch'] and site['branch']!=p.get('branch')): raise HTTPException(422,'Site must belong to the selected client and branch.')


def bank_match(db,p):
    code=p.get('bank_ifsc')
    bank=db.execute(text('select * from ifsc_master where ifsc_code=:code and approved=true'),{'code':code}).mappings().first() if code else None
    return bool(bank and str(p.get('bank_name') or '').casefold()==bank['bank_name'].strip().casefold() and str(p.get('bank_branch') or '').casefold()==bank['branch_name'].strip().casefold())


def doc_requirements(p): return DOCUMENTS | ({'GUN_LICENSE'} if p.get('category')=='GUNMAN' else set())


def doc_valid(doc,verified=False):
    today=business_date()
    return bool(doc.get('storage_path') and doc.get('sha256') and doc.get('verification_status')!='REJECTED' and (not verified or doc.get('verification_status')=='VERIFIED') and (not doc.get('issue_date') or doc['issue_date']<=today) and (not doc.get('expiry_date') or doc['expiry_date']>=today) and (doc.get('document_type') not in CRITICAL or doc.get('expiry_date')))


def readiness(db,row,verified=False):
    p=profile(row); clean_profile(p); missing=sorted(k for k in REQUIRED if not p.get(k))
    if p.get('category')=='GUNMAN': missing+=sorted(k for k in {'gun_license_no','gun_license_expiry','arms_caliber','weapon_serial_no','arms_issuing_authority'} if not p.get(k))
    if p.get('dob'):
        dob=date.fromisoformat(str(p['dob']));today=business_date()
        age=today.year-dob.year-((today.month,today.day)<(dob.month,dob.day))
        if age<18: missing.append('minimum age 18')
    if p.get('gun_license_expiry') and date.fromisoformat(str(p['gun_license_expiry']))<business_date(): missing.append('valid gun licence')
    if not bank_match(db,p): missing.append('approved IFSC with matching bank and branch')
    docs=db.execute(text('select * from employee_documents where employee_id=:id'),{'id':str(row['id'])}).mappings().all()
    available={d['document_type'] for d in docs if doc_valid(d,verified)}
    # A verified cheque may serve as bank proof instead of the passbook.
    needed=doc_requirements(p)
    if 'BANK_CHEQUE' in available: needed=needed-{'BANK_PASSBOOK'}
    return {'missing_fields':missing,'missing_documents':sorted(needed-available),'ready':not missing and not (needed-available)}


def audit(db,eid,user,action,version,detail=None):
    db.execute(text('insert into employee_history(employee_id,changed_by,action,version,details) values (:id,:user,:action,:version,cast(:detail as jsonb))'),{'id':str(eid),'user':user.id,'action':action,'version':version,'detail':json.dumps(detail or {},default=str)})


def compliance_reasons(db,eid):
    row=employee(db,eid);p=profile(row)
    critical={'POLICE_VERIFICATION','MEDICAL_FITNESS'}|({'GUN_LICENSE'} if p.get('category')=='GUNMAN' else set())
    docs=db.execute(text('select * from employee_documents where employee_id=:id'),{'id':str(eid)}).mappings().all()
    valid={d['document_type'] for d in docs if doc_valid(d,True)}
    return sorted(critical-valid)


def refresh_compliance(db,eid):
    row=employee(db,eid,True)
    approved=db.execute(text("select 1 from employee_joining_drafts where employee_id=:id and status='APPROVED'"),{'id':str(eid)}).first()
    if not approved: return {'locked':True,'reasons':['Joining approval incomplete']}
    reasons=compliance_reasons(db,eid);locked=bool(reasons)
    if str(row['status']).upper()=='ACTIVE' or (str(row['status']).upper()=='BENCH' and str(row.get('status_reason') or '').startswith('COMPLIANCE:')):
        status='BENCH' if locked else 'ACTIVE'
        db.execute(text('update employees set status=:status,status_reason=:reason where id=:id'),{'id':str(eid),'status':status,'reason':('COMPLIANCE: '+', '.join(reasons)) if reasons else None})
        db.execute(text('update guard_profiles set status=cast(:status as guard_status_enum) where employee_id=:id'),{'id':str(eid),'status':status})
        db.execute(text('update staff_profiles set status=:status,is_bench_locked=:locked,bench_lock_reason=:reason,updated_at=now() where employee_id=:id'),{'id':str(eid),'status':status,'locked':locked,'reason':('COMPLIANCE: '+', '.join(reasons)) if reasons else None})
    return {'locked':locked,'reasons':reasons}


def activate(db,row,user):
    eid=str(row['id']); p=profile(row)
    db.execute(text("update employees set status='ACTIVE',status_reason=null,version=version+1,updated_at=now() where id=:id"),{'id':eid})
    db.execute(text("update employee_joining_drafts set status='APPROVED',updated_at=now() where employee_id=:id"),{'id':eid})
    db.execute(text("update employee_intimations set status='APPROVED',updated_at=now() where intimation_id=:iid"),{'iid':row['intimation_id']})
    db.execute(text("insert into guard_profiles(employee_id,badge_number,daily_rate,status,joining_date,emergency_contact) values (:id,:badge,0,'ACTIVE',:date,:phone) on conflict (employee_id) do nothing"),{'id':eid,'badge':row['employee_code'],'date':row['joining_date'],'phone':row['emergency_contact']})
    db.execute(text("""insert into staff_profiles(employee_id,staff_code,intimation_id,vertical,category,status,is_bench_locked) values (:id,:code,:iid,:vertical,:category,'ACTIVE',false) on conflict (employee_id) do nothing"""),{'id':eid,'code':row['employee_code'],'iid':row['intimation_id'],'vertical':p['vertical'],'category':row['category']})
    expiries={d['document_type']:d['expiry_date'] for d in db.execute(text("select distinct on (document_type) document_type,expiry_date from employee_documents where employee_id=:id and verification_status='VERIFIED' order by document_type,verified_at desc,created_at desc"),{'id':eid}).mappings()}
    db.execute(text("""update staff_profiles set aadhaar_number=:aadhaar,pan_number=:pan,bank_account_no=:account,bank_name=:bank,bank_ifsc=:ifsc,nominee_name=:nominee,nominee_relation=:relation,nominee_aadhaar=:nominee_aadhaar,arms_license_no=:licence,arms_caliber=:caliber,arms_expiry_date=:gun_expiry,gun_license_expiry=:gun_expiry,ammunition_count=:ammunition,uniform_total_cost=:cost,uniform_monthly_emi=:emi,uniform_balance_due=:cost,police_verification_expiry=:police,medical_fitness_expiry=:medical where employee_id=:id"""),{'id':eid,'aadhaar':row['aadhaar_no'],'pan':row['pan_no'],'account':p['bank_account_no'],'bank':p['bank_name'],'ifsc':p['bank_ifsc'],'nominee':p['nominee_name'],'relation':p['nominee_relation'],'nominee_aadhaar':p.get('nominee_aadhaar'),'licence':p.get('gun_license_no'),'caliber':p.get('arms_caliber'),'gun_expiry':expiries.get('GUN_LICENSE'),'ammunition':p.get('ammunition_count',0),'cost':p.get('uniform_total_cost') or 0,'emi':p.get('uniform_monthly_emi') or 0,'police':expiries.get('POLICE_VERIFICATION'),'medical':expiries.get('MEDICAL_FITNESS')})
    audit(db,eid,user,'ACTIVATE',row['version']+1)
