from datetime import date, datetime
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.api.deps import require_hr_or_admin
from app.core.database import get_db

router=APIRouter()

def lock_reasons(row):
    today=date.today(); reasons=[]
    if row.get("police_verification_expiry") is None or row["police_verification_expiry"]<today: reasons.append("Police Verification expired or missing")
    if row.get("medical_fitness_expiry") is None or row["medical_fitness_expiry"]<today: reasons.append("Medical Fitness expired or missing")
    return reasons

@router.get("")
def list_staff(db:Session=Depends(get_db),current_user=Depends(require_hr_or_admin)):
    rows=db.execute(text("""select s.*,e.name,e.phone,e.employee_code,e.branch,e.joining_date from staff_profiles s join employees e on e.id=s.employee_id order by e.name""")).mappings().all()
    return [dict(r) for r in rows]

@router.post("/{employee_id}/compliance-check")
def compliance_check(employee_id:str,db:Session=Depends(get_db),current_user=Depends(require_hr_or_admin)):
    row=db.execute(text("select * from staff_profiles where employee_id=:id for update"),{"id":employee_id}).mappings().first()
    if not row: raise HTTPException(404,"Staff profile not found.")
    reasons=lock_reasons(row); locked=bool(reasons); status="BENCH" if locked else ("ACTIVE" if row["status"]=="BENCH" else row["status"]); reason="; ".join(reasons) if reasons else None
    db.execute(text("update staff_profiles set status=:status,is_bench_locked=:locked,bench_lock_reason=:reason,updated_at=now() where employee_id=:id"),{"status":status,"locked":locked,"reason":reason,"id":employee_id})
    db.execute(text("update employees set status=:status,status_reason=:reason where id=:id"),{"status":"bench" if locked else "active","reason":reason,"id":employee_id})
    db.commit(); return dict(db.execute(text("select * from staff_profiles where employee_id=:id"),{"id":employee_id}).mappings().one())

@router.post("/compliance/run")
def run_compliance(db:Session=Depends(get_db),current_user=Depends(require_hr_or_admin)):
    rows=db.execute(text("select * from staff_profiles")).mappings().all(); locked=0
    for row in rows:
        reasons=lock_reasons(row); is_locked=bool(reasons); status="BENCH" if is_locked else ("ACTIVE" if row["status"]=="BENCH" else row["status"]); reason="; ".join(reasons) if reasons else None
        db.execute(text("update staff_profiles set status=:status,is_bench_locked=:locked,bench_lock_reason=:reason,updated_at=now() where employee_id=:id"),{"status":status,"locked":is_locked,"reason":reason,"id":str(row["employee_id"])})
        db.execute(text("update employees set status=:status,status_reason=:reason where id=:id"),{"status":"bench" if is_locked else "active","reason":reason,"id":str(row["employee_id"])}); locked+=int(is_locked)
    db.commit(); return {"checked":len(rows),"bench_locked":locked}

@router.post("", status_code=201)
def create_staff(payload: dict, db: Session = Depends(get_db), current_user=Depends(require_hr_or_admin)):
    vertical=str(payload.get("vertical") or "").upper()
    category=str(payload.get("category") or "").upper()
    if vertical not in {"SECURITY","HOUSEKEEPING","NURSING"} or category not in {
        "GUARD","GUNMAN","SUPERVISOR","FIELD_OFFICER","JANITOR","CLEANER","FACILITY_ATTENDANT",
        "GDA","NURSE_ASSISTANT","HOSPITAL_ATTENDANT"
    }:
        raise HTTPException(422,"Invalid staff vertical/category.")
    if not payload.get("name") or not payload.get("phone"):
        raise HTTPException(422,"Name and phone are required.")
    aadhaar=str(payload.get("aadhaar_number") or "").strip()
    if not __import__("app.api.v1.endpoints.recruitment",fromlist=["verhoeff"]).verhoeff(aadhaar):
        raise HTTPException(422,"Aadhaar failed 12-digit Verhoeff checksum validation.")
    pan=str(payload.get("pan_number") or "").strip().upper()
    if len(pan)!=10: raise HTTPException(422,"PAN must be 10 characters.")
    if len(str(payload.get("bank_ifsc") or "").strip())!=11: raise HTTPException(422,"IFSC must be 11 characters.")
    police=payload.get("police_verification_expiry"); medical=payload.get("medical_fitness_expiry")
    from datetime import date
    reasons=[]
    if not police or police < date.today(): reasons.append("Police Verification expired or missing")
    if not medical or medical < date.today(): reasons.append("Medical Fitness expired or missing")
    locked=bool(reasons)
    status="BENCH" if locked else "ACTIVE"
    staff_seq=db.execute(text("select nextval('staff_code_seq')")).scalar()
    code=f"S-DAS-{int(staff_seq):04d}"
    iid=f"INT-{datetime.utcnow():%Y%m%d}-{uuid4().hex[:7].upper()}"
    emp=db.execute(text("""
      insert into employees(employee_code,name,phone,status,intimation_id,designation,category,joining_date,status_reason)
      values(:code,:name,:phone,:emp_status,:iid,:designation,:category,current_date,:reason)
      returning id,employee_code,name,phone,status
    """),{"code":code,"name":payload["name"],"phone":payload["phone"],"emp_status":"bench" if locked else "active",
       "iid":iid,"designation":category.replace("_"," ").title(),"category":category,"reason":"; ".join(reasons) if reasons else None}).mappings().one()
    sp=db.execute(text("""
      insert into staff_profiles
      (employee_id,staff_code,intimation_id,vertical,category,status,aadhaar_number,pan_number,
       bank_account_no,bank_name,bank_ifsc,police_verification_expiry,medical_fitness_expiry,
       is_bench_locked,bench_lock_reason)
      values(:eid,:code,:iid,:vertical,:category,:status,:aadhaar,:pan,:bank,:bank_name,:ifsc,
             :police,:medical,:locked,:reason)
      returning *
    """),{"eid":str(emp["id"]),"code":code,"iid":iid,"vertical":vertical,"category":category,
       "status":status,"aadhaar":aadhaar,"pan":pan,"bank":payload.get("bank_account_no"),
       "bank_name":payload.get("bank_name"),"ifsc":str(payload.get("bank_ifsc")).upper(),
       "police":police,"medical":medical,"locked":locked,"reason":"; ".join(reasons) if reasons else None}).mappings().one()
    db.commit()
    return {"employee":dict(emp),"staff":dict(sp)}

@router.patch("/{employee_id}")
def update_staff(employee_id:str,payload:dict,db:Session=Depends(get_db),current_user=Depends(require_hr_or_admin)):
    allowed={"vertical","category","aadhaar_number","pan_number","bank_account_no","bank_name","bank_ifsc","nominee_name","nominee_relation","nominee_aadhaar","arms_license_no","arms_expiry_date","arms_caliber","ammunition_count","uniform_total_cost","uniform_monthly_emi","uniform_balance_due","police_verification_expiry","medical_fitness_expiry","psara_cert_no","psara_training_expiry","gun_license_expiry","badge_number"}
    data={k:v for k,v in payload.items() if k in allowed}
    if "aadhaar_number" in data and data["aadhaar_number"] and not __import__("app.api.v1.endpoints.recruitment",fromlist=["verhoeff"]).verhoeff(data["aadhaar_number"]): raise HTTPException(422,"Aadhaar failed 12-digit Verhoeff checksum validation.")
    if not data: raise HTTPException(422,"No editable staff fields supplied.")
    data["employee_id"]=employee_id; sets=", ".join(f"{k}=:{k}" for k in data if k!="employee_id")
    row=db.execute(text(f"update staff_profiles set {sets},updated_at=now() where employee_id=:employee_id returning *"),data).mappings().first()
    if not row: raise HTTPException(404,"Staff profile not found.")
    db.commit(); return dict(row)
