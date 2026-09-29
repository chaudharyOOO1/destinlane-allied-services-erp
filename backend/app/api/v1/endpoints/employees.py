from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.api.deps import require_hr_or_admin
from app.core.database import get_db

router = APIRouter()

@router.get("")
def list_employees(db: Session = Depends(get_db), current_user=Depends(require_hr_or_admin)):
    return [dict(r) for r in db.execute(text("select * from employees order by created_at desc")).mappings().all()]

@router.post("", status_code=201)
def create_employee(payload: dict, db: Session = Depends(get_db), current_user=Depends(require_hr_or_admin)):
    required=["employee_code","name","phone"]
    missing=[k for k in required if not payload.get(k)]
    if missing: raise HTTPException(422, f"Missing required fields: {', '.join(missing)}")
    allowed=["employee_code","name","phone","status","intimation_id","dob","gender","designation","branch","site_id","joining_date","category","aadhaar_no","pan_no","permanent_address","present_address","emergency_contact","marital_status","status_reason"]
    data={k:payload[k] for k in allowed if k in payload}
    data.setdefault("status","active")
    cols=", ".join(data); binds=", ".join(f":{k}" for k in data)
    try:
        row=db.execute(text(f"insert into employees ({cols}) values ({binds}) returning *"),data).mappings().one(); db.commit(); return dict(row)
    except Exception as exc:
        db.rollback(); raise HTTPException(409, str(exc).split("\n")[0])

@router.patch("/{employee_id}")
def update_employee(employee_id: UUID, payload: dict, db: Session = Depends(get_db), current_user=Depends(require_hr_or_admin)):
    allowed={"employee_code","name","phone","status","intimation_id","dob","gender","designation","branch","site_id","joining_date","category","aadhaar_no","pan_no","permanent_address","present_address","emergency_contact","marital_status","status_reason"}
    data={k:v for k,v in payload.items() if k in allowed}
    if not data: raise HTTPException(422,"No editable fields supplied")
    data["id"]=str(employee_id); sets=", ".join(f"{k}=:{k}" for k in data if k!="id")
    row=db.execute(text(f"update employees set {sets} where id=:id returning *"),data).mappings().first()
    if not row: db.rollback(); raise HTTPException(404,"Employee not found")
    db.commit(); return dict(row)
