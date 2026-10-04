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
    from app.services.employee_workflow import refresh_compliance
    result=refresh_compliance(db,employee_id);db.commit();return result

@router.post("/compliance/run")
def run_compliance(db:Session=Depends(get_db),current_user=Depends(require_hr_or_admin)):
    from app.services.employee_workflow import refresh_compliance
    ids=db.execute(text("select employee_id from employee_joining_drafts where status='APPROVED'")).scalars().all()
    results=[refresh_compliance(db,eid) for eid in ids];db.commit()
    return {'checked':len(results),'bench_locked':sum(r['locked'] for r in results)}

@router.post("", status_code=201)
def create_staff(payload: dict, db: Session = Depends(get_db), current_user=Depends(require_hr_or_admin)):
    raise HTTPException(409,"Use Employee Creation for deployed workforce. Internal company staff belong in Staff Master.")

@router.patch("/{employee_id}")
def update_staff(employee_id:str,payload:dict,db:Session=Depends(get_db),current_user=Depends(require_hr_or_admin)):
    raise HTTPException(409,"Use the employee joining file and private document review; legacy workforce editing is closed.")
