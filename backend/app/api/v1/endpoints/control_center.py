from fastapi import APIRouter,Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.api.deps import require_admin,require_hr_or_admin,require_accounts_or_admin,require_owner
from app.core.database import get_db
from app.api.deps import require_management, require_payroll, require_roles
from app.models.enums import UserRole
router=APIRouter()
@router.get("/payroll")
def payroll(db:Session=Depends(get_db),current_user=Depends(require_payroll)):
 q="""select s.*,e.employee_code,e.name from salary_records s join employees e on e.id=s.employee_id order by s.month desc,e.name"""
 return [dict(r) for r in db.execute(text(q)).mappings().all()]
@router.get("/accounts")
def accounts(db:Session=Depends(get_db),current_user=Depends(require_accounts_or_admin)):
 return {"invoices":[dict(r) for r in db.execute(text("select i.*,c.company_name from invoices i join clients c on c.id=i.client_id order by i.issue_date desc")).mappings().all()],"expenses":[dict(r) for r in db.execute(text("select * from expenses order by expense_date desc")).mappings().all()],"gst_collection":[dict(r) for r in db.execute(text("select * from gst_collection_ledger order by created_at desc")).mappings().all()],"gst_itc":[dict(r) for r in db.execute(text("select * from gst_itc_ledger order by created_at desc")).mappings().all()]}
@router.get("/compliance")
def compliance(db:Session=Depends(get_db),current_user=Depends(require_payroll)):
 return {"employee_documents":[dict(r) for r in db.execute(text("""select d.*,e.employee_code,e.name from employee_documents d join employees e on e.id=d.employee_id order by d.expiry_date nulls last""")).mappings().all()],"corporate":[dict(r) for r in db.execute(text("select * from corporate_compliances order by due_date nulls last")).mappings().all()]}
@router.get("/risks")
def risks(db:Session=Depends(get_db),current_user=Depends(require_management)):
 return [dict(r) for r in db.execute(text("select * from risk_flags order by resolved,detected_at desc")).mappings().all()]
