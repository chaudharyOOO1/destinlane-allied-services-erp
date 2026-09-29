from datetime import datetime
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
import json

from app.api.deps import require_hr_or_admin
from app.core.database import get_db

router = APIRouter()
VERTICALS = {"SECURITY", "HOUSEKEEPING", "NURSING"}
CATEGORIES = {
    "SECURITY": {"GUARD", "GUNMAN", "SUPERVISOR", "FIELD_OFFICER"},
    "HOUSEKEEPING": {"JANITOR", "CLEANER", "FACILITY_ATTENDANT"},
    "NURSING": {"GDA", "NURSE_ASSISTANT", "HOSPITAL_ATTENDANT"},
}

def verhoeff(number: str) -> bool:
    if not number.isdigit() or len(number) != 12:
        return False
    d=[[0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,1,6,4,2],[8,7,9,0,6,4,3,5,2,1],[6,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,1,6,4,2],[8,7,9,0,6,4,3,5,2,1],[6,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4]]
    p=[[0,1,2,3,4,5,6,7,8,9],[0,5,7,8,9,4,2,1,3,6],[0,8,1,4,6,3,5,9,7,2],[0,9,4,7,2,6,3,8,5,1],[0,4,8,1,6,2,9,5,7,3],[0,2,9,5,1,7,4,8,6,3],[0,7,3,6,4,5,2,9,8,1],[0,3,5,2,7,9,8,6,1,4]]
    c=0
    for i,n in enumerate(reversed(number)): c=d[c][p[i%8][int(n)]]
    return c==0

def validate(payload):
    v=str(payload.get("vertical","")).upper()
    cat=str(payload.get("category","")).upper()
    if v not in VERTICALS: raise HTTPException(422,"Invalid staff vertical.")
    if cat and cat not in CATEGORIES[v]: raise HTTPException(422,"Invalid category for selected vertical.")
    return v,cat

@router.get("")
def list_candidates(db: Session=Depends(get_db), current_user=Depends(require_hr_or_admin)):
    return [dict(r) for r in db.execute(text("select * from recruitment_candidates order by created_at desc")).mappings().all()]

@router.post("",status_code=201)
def create_candidate(payload: dict, db: Session=Depends(get_db), current_user=Depends(require_hr_or_admin)):
    v,cat=validate(payload)
    if not payload.get("full_name") or not payload.get("phone"): raise HTTPException(422,"Full name and phone are required.")
    cid=payload.get("candidate_id") or f"CND-{datetime.utcnow():%Y%m%d}-{uuid4().hex[:6].upper()}"
    row=db.execute(text("""insert into recruitment_candidates(candidate_id,full_name,phone,vertical,category,documents)
      values(:cid,:name,:phone,:vertical,:category,cast(:docs as jsonb)) returning *"""),
      {"cid":cid,"name":payload["full_name"],"phone":payload["phone"],"vertical":v,"category":cat or None,"docs":json.dumps(payload.get("documents") or {})}).mappings().one()
    db.commit(); return dict(row)

@router.patch("/{candidate_id}")
def update_candidate(candidate_id:str,payload:dict,db:Session=Depends(get_db),current_user=Depends(require_hr_or_admin)):
    row=db.execute(text("select * from recruitment_candidates where candidate_id=:id"),{"id":candidate_id}).mappings().first()
    if not row: raise HTTPException(404,"Candidate not found.")
    status=str(payload.get("status",row["status"])).upper()
    if status not in {"APPLIED","VERIFIED","ONBOARDED"}: raise HTTPException(422,"Invalid recruitment status.")
    if status=="ONBOARDED": raise HTTPException(409,"Use the onboarding endpoint to create the staff record.")
    db.execute(text("update recruitment_candidates set status=:status,verified_at=case when :status='VERIFIED' then now() else verified_at end,updated_at=now() where candidate_id=:id"),{"id":candidate_id,"status":status})
    db.commit(); return dict(db.execute(text("select * from recruitment_candidates where candidate_id=:id"),{"id":candidate_id}).mappings().one())

@router.post("/{candidate_id}/onboard",status_code=201)
def onboard_candidate(candidate_id:str,payload:dict|None=None,db:Session=Depends(get_db),current_user=Depends(require_hr_or_admin)):
    row=db.execute(text("select * from recruitment_candidates where candidate_id=:id for update"),{"id":candidate_id}).mappings().first()
    if not row: raise HTTPException(404,"Candidate not found.")
    if row["status"]!="VERIFIED": raise HTTPException(409,"Candidate must be VERIFIED before onboarding.")
    if row["employee_id"]: return dict(db.execute(text("select * from staff_profiles where employee_id=:id"),{"id":str(row["employee_id"])}).mappings().one())
    payload=payload or {}
    cat=str(payload.get("category") or row["category"] or "").upper()
    if cat not in CATEGORIES[row["vertical"]]:
        raise HTTPException(422,"Valid staff category is required.")

    # Phase 2: mandatory KYC for every onboarded staff member.
    aadhaar=payload.get("aadhaar_number")
    pan=str(payload.get("pan_number") or "").strip().upper()
    bank_account=str(payload.get("bank_account_no") or "").strip()
    bank_ifsc=str(payload.get("bank_ifsc") or "").strip().upper()
    missing=[label for label,value in {
        "Aadhaar": aadhaar,
        "PAN": pan,
        "Bank Account": bank_account,
        "IFSC": bank_ifsc,
    }.items() if not value]
    if missing:
        raise HTTPException(422, f"Mandatory KYC fields missing: {', '.join(missing)}.")
    if not verhoeff(aadhaar):
        raise HTTPException(422,"Aadhaar failed 12-digit Verhoeff checksum validation.")
    if len(pan) != 10:
        raise HTTPException(422,"PAN must be 10 characters.")
    if len(bank_ifsc) != 11:
        raise HTTPException(422,"IFSC must be 11 characters.")

    # Gunman records require arms-license information.
    if cat == "GUNMAN":
        missing_arms=[label for label,value in {
            "Arms License No": payload.get("arms_license_no"),
            "Arms Expiry Date": payload.get("arms_expiry_date"),
            "Arms Caliber": payload.get("arms_caliber"),
        }.items() if not value]
        if missing_arms:
            raise HTTPException(422, f"Gunman arms fields missing: {', '.join(missing_arms)}.")

    # Missing/expired Police Verification or Medical Fitness creates a BENCH LOCK.
    from datetime import date
    def expired_or_missing(value):
        return not value or value < date.today()
    lock_reasons=[]
    if expired_or_missing(payload.get("police_verification_expiry")):
        lock_reasons.append("Police Verification expired or missing")
    if expired_or_missing(payload.get("medical_fitness_expiry")):
        lock_reasons.append("Medical Fitness expired or missing")
    if cat == "GUNMAN" and expired_or_missing(payload.get("gun_license_expiry")):
        lock_reasons.append("Gun License expired or missing")
    is_bench_locked=bool(lock_reasons)
    staff_status="BENCH" if is_bench_locked else "ACTIVE"
    bench_reason="; ".join(lock_reasons) if lock_reasons else None

    iid=f"INT-{datetime.utcnow():%Y%m%d}-{uuid4().hex[:7].upper()}"
    code=f"S-DAS-{int(db.execute(text("select nextval('staff_code_seq')")).scalar()):04d}"
    badge=payload.get("badge_number") or f"BDG-{datetime.utcnow():%y%m%d}-{uuid4().hex[:5].upper()}"
    emp=db.execute(text("""insert into employees(employee_code,name,phone,status,intimation_id,designation,category,branch,joining_date,status_reason)
      values(:code,:name,:phone,:employee_status,:iid,:designation,:category,:branch,current_date,:status_reason) returning id"""),
      {"code":code,"name":row["full_name"],"phone":row["phone"],"employee_status":"bench" if is_bench_locked else "active","status_reason":bench_reason,"iid":iid,"designation":cat.replace("_"," ").title(),"category":cat,"branch":payload.get("branch") or "Delhi-NCR"}).mappings().one()
    eid=str(emp["id"])
    sp=db.execute(text("""insert into staff_profiles(employee_id,staff_code,intimation_id,badge_number,vertical,category,status,aadhaar_number,pan_number,bank_account_no,bank_name,bank_ifsc,nominee_name,nominee_relation,nominee_aadhaar,arms_license_no,arms_expiry_date,arms_caliber,ammunition_count,uniform_total_cost,uniform_monthly_emi,uniform_balance_due,police_verification_expiry,medical_fitness_expiry,psara_cert_no,psara_training_expiry,gun_license_expiry,is_bench_locked,bench_lock_reason)
      values(:eid,:staff_code,:iid,:badge,:vertical,:category,:status,:aadhaar,:pan,:bank,:bankname,:ifsc,:nominee,:relation,:naadhaar,:arms,:armsexp,:caliber,:ammo,:ucost,:emi,:balance,:police,:medical,:psara,:psaraexp,:gunexp,:locked,:reason) returning *"""),
      {"eid":eid,"staff_code":code,"iid":iid,"badge":badge,"vertical":row["vertical"],"category":cat,"status":staff_status,"aadhaar":aadhaar,"pan":payload.get("pan_number"),"bank":payload.get("bank_account_no"),"bankname":payload.get("bank_name"),"ifsc":payload.get("bank_ifsc"),"nominee":payload.get("nominee_name"),"relation":payload.get("nominee_relation"),"naadhaar":payload.get("nominee_aadhaar"),"arms":payload.get("arms_license_no"),"armsexp":payload.get("arms_expiry_date"),"caliber":payload.get("arms_caliber"),"ammo":payload.get("ammunition_count"),"ucost":payload.get("uniform_total_cost") or 0,"emi":payload.get("uniform_monthly_emi") or 0,"balance":payload.get("uniform_balance_due") or 0,"police":payload.get("police_verification_expiry"),"medical":payload.get("medical_fitness_expiry"),"psara":payload.get("psara_cert_no"),"psaraexp":payload.get("psara_training_expiry"),"gunexp":payload.get("gun_license_expiry"),"locked":is_bench_locked,"reason":bench_reason}).mappings().one()
    db.execute(text("update recruitment_candidates set status='ONBOARDED',employee_id=:eid,onboarded_at=now(),updated_at=now() where candidate_id=:cid"),{"eid":eid,"cid":candidate_id})
    db.commit(); return dict(sp)
