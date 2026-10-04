from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.api.deps import require_hr_or_admin, require_accounts_or_admin, require_owner
from app.core.database import get_db

router = APIRouter()

@router.get("/employee-documents")
def list_employee_documents(db: Session = Depends(get_db), current_user=Depends(require_hr_or_admin)):
    q = """select d.id,d.employee_id,d.document_type,d.original_filename,d.issue_date,d.expiry_date,d.verification_status,e.employee_code,e.name
           from employee_documents d join employees e on e.id=d.employee_id
           order by d.expiry_date nulls last, e.name"""
    return [dict(r) for r in db.execute(text(q)).mappings().all()]

@router.post("/employee-documents")
def create_employee_document(payload: dict, db: Session = Depends(get_db), current_user=Depends(require_hr_or_admin)):
    raise HTTPException(409,"Use private file upload and verification in Employee Compliance Documents.")

@router.patch("/employee-documents/{document_id}")
def update_employee_document(document_id: str, payload: dict, db: Session = Depends(get_db), current_user=Depends(require_hr_or_admin)):
    raise HTTPException(409,"Use private file upload and verification in Employee Compliance Documents.")

@router.get("/corporate-compliances")
def list_corporate_compliances(db: Session = Depends(get_db), current_user=Depends(require_hr_or_admin)):
    return [dict(r) for r in db.execute(text("select * from corporate_compliances order by due_date nulls last")).mappings().all()]

@router.post("/corporate-compliances")
def create_corporate_compliance(payload: dict, db: Session = Depends(get_db), current_user=Depends(require_hr_or_admin)):
    allowed=["compliance_type","period","due_date","filed_date","status","reference_number","notes"]
    data={k:v for k,v in payload.items() if k in allowed}
    if not data.get("compliance_type"): raise HTTPException(400,"compliance_type is required")
    cols=", ".join(data); vals=", ".join(f":{k}" for k in data)
    return dict(db.execute(text(f"insert into corporate_compliances ({cols}) values ({vals}) returning *"),data).mappings().one())

@router.patch("/corporate-compliances/{compliance_id}")
def update_corporate_compliance(compliance_id: str, payload: dict, db: Session = Depends(get_db), current_user=Depends(require_hr_or_admin)):
    allowed=["compliance_type","period","due_date","filed_date","status","reference_number","notes"]
    data={k:v for k,v in payload.items() if k in allowed}; data["id"]=compliance_id
    if len(data)==1: raise HTTPException(400,"No editable fields supplied")
    sets=", ".join(f"{k}=:{k}" for k in data if k!="id")
    row=db.execute(text(f"update corporate_compliances set {sets}, updated_at=now() where id=:id returning *"),data).mappings().first()
    if not row: raise HTTPException(404,"Compliance record not found")
    return dict(row)

@router.post("/payroll/salary-records")
def create_salary_record(payload: dict, db: Session = Depends(get_db), current_user=Depends(require_hr_or_admin)):
    allowed=["employee_id","month","amount","status","credited_date","work_days","present_days","late_days","leave_days","absent_days","basic","hra","allowances","gross_pay","pf","esic","lwf","dress_emi","net_pay","lifecycle_status"]
    data={k:v for k,v in payload.items() if k in allowed}
    if not data.get("employee_id") or not data.get("month"): raise HTTPException(400,"employee_id and month are required")
    cols=", ".join(data); vals=", ".join(f":{k}" for k in data)
    return dict(db.execute(text(f"insert into salary_records ({cols}) values ({vals}) returning *"),data).mappings().one())

@router.patch("/payroll/salary-records/{record_id}")
def update_salary_record(record_id: str, payload: dict, db: Session = Depends(get_db), current_user=Depends(require_hr_or_admin)):
    allowed=["amount","status","credited_date","work_days","present_days","late_days","leave_days","absent_days","basic","hra","allowances","gross_pay","pf","esic","lwf","dress_emi","net_pay","lifecycle_status"]
    data={k:v for k,v in payload.items() if k in allowed}; data["id"]=record_id
    if len(data)==1: raise HTTPException(400,"No editable fields supplied")
    sets=", ".join(f"{k}=:{k}" for k in data if k!="id")
    row=db.execute(text(f"update salary_records set {sets}, updated_at=now() where id=:id returning *"),data).mappings().first()
    if not row: raise HTTPException(404,"Salary record not found")
    return dict(row)

@router.patch("/risks/{risk_id}")
def resolve_risk(risk_id: str, payload: dict, db: Session = Depends(get_db), current_user=Depends(require_owner)):
    resolved=bool(payload.get("resolved", True))
    row=db.execute(text("update risk_flags set resolved=:resolved, resolved_at=case when :resolved then now() else null end where id=:id returning *"),{"id":risk_id,"resolved":resolved}).mappings().first()
    if not row: raise HTTPException(404,"Risk flag not found")
    return dict(row)
