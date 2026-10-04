from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query, UploadFile, File, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import require_admin, require_hr_or_admin, require_accounts_or_admin, require_owner, require_admin_or_staff
from app.core.database import get_db
from app.api.deps import require_management, require_payroll, require_roles
from app.models.enums import UserRole

router = APIRouter()

@router.get("/ifsc")
def list_ifsc(
    search: str | None = Query(None),
    bank: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    sql = """select ifsc_code, bank_name, branch_name, address, city, district, state, source, approved, approved_at
             from ifsc_master where approved=true"""
    params = {}
    if search:
        sql += " and (ifsc_code ilike :search or branch_name ilike :search or bank_name ilike :search)"
        params["search"] = f"%{search.strip()}%"
    if bank:
        sql += " and bank_name ilike :bank"
        params["bank"] = f"%{bank.strip()}%"
    sql += " order by bank_name, branch_name, ifsc_code limit :limit"
    params["limit"] = limit
    return [dict(r) for r in db.execute(text(sql), params).mappings().all()]


@router.get("/ifsc/stats")
def ifsc_stats(db: Session = Depends(get_db), current_user=Depends(require_admin)):
    row = db.execute(text("""
        select count(*) as total,
               count(*) filter (where approved=true) as approved,
               count(distinct bank_name) as banks
        from ifsc_master
    """)).mappings().one()
    return dict(row)


@router.post("/ifsc/import-csv")
async def import_ifsc_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    import csv, io, re
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(422, "Upload a CSV file. Required columns: IFSC, Bank, Branch, Address, City, District, State.")
    raw = await file.read()
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(413, "IFSC CSV is larger than the 25 MB limit.")
    try:
        text_data = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(422, "CSV must be UTF-8 encoded.")
    reader = csv.DictReader(io.StringIO(text_data))
    if not reader.fieldnames:
        raise HTTPException(422, "CSV has no header row.")
    aliases = {
        "ifsc": ["ifsc", "ifsc_code", "ifsc code"],
        "bank": ["bank", "bank_name", "bank name"],
        "branch": ["branch", "branch_name", "branch name"],
        "address": ["address"],
        "city": ["city"],
        "district": ["district"],
        "state": ["state"],
    }
    normalized = {str(h).strip().lower(): h for h in reader.fieldnames}
    def col(key):
        for alias in aliases[key]:
            if alias in normalized:
                return normalized[alias]
        return None
    ifsc_col, bank_col = col("ifsc"), col("bank")
    if not ifsc_col or not bank_col:
        raise HTTPException(422, "CSV must contain IFSC and Bank columns.")
    rows=[]; invalid=0
    for source_row in reader:
        code=str(source_row.get(ifsc_col) or "").strip().upper().replace(" ", "")
        bank_name=str(source_row.get(bank_col) or "").strip()
        if not re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", code) or not bank_name:
            invalid += 1
            continue
        rows.append({
            "ifsc_code": code, "bank_name": bank_name,
            "branch_name": str(source_row.get(col("branch")) or "").strip() if col("branch") else None,
            "address": str(source_row.get(col("address")) or "").strip() if col("address") else None,
            "city": str(source_row.get(col("city")) or "").strip() if col("city") else None,
            "district": str(source_row.get(col("district")) or "").strip() if col("district") else None,
            "state": str(source_row.get(col("state")) or "").strip() if col("state") else None,
        })
    if not rows:
        raise HTTPException(422, "No valid IFSC records were found in the CSV.")
    for row in rows:
        db.execute(text("""
            insert into ifsc_master(ifsc_code,bank_name,branch_name,address,city,district,state,source,approved,approved_at,updated_at)
            values(:ifsc_code,:bank_name,:branch_name,:address,:city,:district,:state,'ADMIN_CSV',true,now(),now())
            on conflict(ifsc_code) do update set
              bank_name=excluded.bank_name, branch_name=excluded.branch_name, address=excluded.address,
              city=excluded.city, district=excluded.district, state=excluded.state,
              source='ADMIN_CSV', approved=true, approved_at=now(), updated_at=now()
        """), row)
    db.commit()
    return {"imported": len(rows), "invalid_rows_skipped": invalid, "filename": file.filename}


@router.get("/summary")
def erp_summary(db: Session = Depends(get_db), current_user=Depends(require_accounts_or_admin)):
    def scalar(sql: str, params=None):
        return db.execute(text(sql), params or {}).scalar_one()
    month_start = date.today().replace(day=1)
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    output_gst = scalar("select coalesce(sum(tax_amount), 0) from invoices where issue_date >= :month_start and issue_date < :next_month", {"month_start": month_start, "next_month": next_month})
    input_itc = scalar("select coalesce(sum(gst_amount), 0) from gst_itc_ledger where created_at >= :month_start and created_at < :next_month and upper(coalesce(reconciliation_status, 'PENDING')) in ('RECONCILED','APPROVED')", {"month_start": month_start, "next_month": next_month})
    pending_compliance = scalar("select count(*) from corporate_compliances where upper(coalesce(status, 'PENDING')) not in ('FILED','COMPLETED','COMPLIANT')")
    reminders = [dict(r) for r in db.execute(text("""select id, compliance_type, period, due_date, status, 'Corporate compliance' as reminder_type from corporate_compliances where due_date is not null and due_date <= current_date + 30 and upper(coalesce(status, 'PENDING')) not in ('FILED','COMPLETED','COMPLIANT') order by due_date asc limit 8""")).mappings().all()]
    reminders += [dict(r) for r in db.execute(text("""select d.id, d.document_type as compliance_type, e.name as employee_name, d.expiry_date as due_date, d.status, 'Employee document' as reminder_type from employee_documents d join employees e on e.id = d.employee_id where d.expiry_date is not null and d.expiry_date <= current_date + 30 and upper(coalesce(d.status, 'VALID')) not in ('EXPIRED','CANCELLED') order by d.expiry_date asc limit 8""")).mappings().all()]
    reminders = sorted(reminders, key=lambda x: x.get("due_date") or date.max)[:10]
    return {
        "month": month_start.strftime("%B %Y"),
        "monthly_billing_pending": scalar("select coalesce(sum(total_amount), 0) from invoices where issue_date >= :month_start and issue_date < :next_month and upper(coalesce(clearance_status, 'PENDING')) <> 'PAID'", {"month_start": month_start, "next_month": next_month}),
        "total_amount_received": scalar("select coalesce(sum(total_amount), 0) from invoices where issue_date >= :month_start and issue_date < :next_month and upper(coalesce(clearance_status, 'PENDING')) = 'PAID'", {"month_start": month_start, "next_month": next_month}),
        "gst_collected": scalar("select coalesce(sum(tax_amount), 0) from invoices where issue_date >= :month_start and issue_date < :next_month and upper(coalesce(clearance_status, 'PENDING')) = 'PAID'", {"month_start": month_start, "next_month": next_month}),
        "pending_to_collect": scalar("select coalesce(sum(total_amount), 0) from invoices where upper(coalesce(clearance_status, 'PENDING')) <> 'PAID'"),
        "gst_to_be_paid": output_gst - input_itc,
        "pending_compliance": pending_compliance,
        "compliance_reminders": reminders,
    }

@router.get("/employees")
def list_employees(
    status: Optional[str] = Query(None),
    branch: Optional[str] = Query(None),
    site_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(require_hr_or_admin),
):
    sql = "select * from employees where 1=1"
    params = {}
    if status:
        sql += " and status = :status"; params["status"] = status
    if branch:
        sql += " and branch = :branch"; params["branch"] = branch
    if site_id is not None:
        sql += " and site_id = :site_id"; params["site_id"] = site_id
    sql += " order by created_at desc"
    return [dict(r) for r in db.execute(text(sql), params).mappings().all()]

@router.get("/compliance-expiry")
def compliance_expiry(
    days: int = Query(60, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user=Depends(require_hr_or_admin),
):
    cutoff = date.today() + timedelta(days=days)
    rows = db.execute(text("""
        select d.*, e.employee_code, e.name
        from employee_documents d
        join employees e on e.id = d.employee_id
        where d.expiry_date is not null and d.expiry_date <= :cutoff
        order by d.expiry_date asc
    """), {"cutoff": cutoff}).mappings().all()
    return [dict(r) for r in rows]

@router.get("/payroll")
def payroll(month: Optional[str] = Query(None), db: Session = Depends(get_db), current_user=Depends(require_payroll)):
    sql = """
        select s.*, e.employee_code, e.name
        from salary_records s join employees e on e.id=s.employee_id
        where 1=1
    """
    params = {}
    if month:
        sql += " and s.month = :month"; params["month"] = month
    sql += " order by s.month desc, e.name"
    return [dict(r) for r in db.execute(text(sql), params).mappings().all()]

@router.get("/expenses")
def expenses(branch: Optional[str] = Query(None), client_id: Optional[int] = Query(None), db: Session = Depends(get_db), current_user=Depends(require_accounts_or_admin)):
    sql = "select * from expenses where 1=1"; params={}
    if branch: sql += " and branch=:branch"; params["branch"]=branch
    if client_id is not None: sql += " and client_id=:client_id"; params["client_id"]=client_id
    sql += " order by expense_date desc, created_at desc"
    return [dict(r) for r in db.execute(text(sql), params).mappings().all()]

@router.get("/risk-flags")
def risk_flags(db: Session = Depends(get_db), current_user=Depends(require_management)):
    rows = db.execute(text("select * from risk_flags where resolved=false order by detected_at desc")).mappings().all()
    return [dict(r) for r in rows]


@router.get("/risk-engine")
def risk_engine(db: Session = Depends(get_db), current_user=Depends(require_management)):
    """Read-only owner risk scan. It derives operational exceptions without mutating source records."""
    risks = []
    def add(code, category, severity, entity_type, entity_id, description):
        risks.append({"trigger_code": code, "category": category, "severity": severity, "entity_type": entity_type, "entity_id": str(entity_id) if entity_id is not None else None, "description": description})
    for r in db.execute(text("""select d.id,d.employee_id,e.employee_code,e.name,d.document_type,d.expiry_date from employee_documents d join employees e on e.id=d.employee_id where d.expiry_date < current_date order by d.expiry_date""")).mappings():
        add("DOC_EXPIRED","COMPLIANCE","HIGH","EMPLOYEE_DOCUMENT",r["id"],f'{r["document_type"]} expired for {r["employee_code"]} - {r["name"]}')
    for r in db.execute(text("""select id,invoice_number,client_id,due_date,total_amount from invoices where clearance_status <> 'PAID' and due_date < current_date order by due_date""")).mappings():
        add("INVOICE_OVERDUE","FINANCE","HIGH","INVOICE",r["id"],f'Invoice {r["invoice_number"]} is overdue')
    for r in db.execute(text("""select id,employee_id,month,amount from salary_records where lifecycle_status = 'HELD'""")).mappings():
        add("SALARY_HELD","PAYROLL","MEDIUM","SALARY_RECORD",r["id"],f'Salary for {r["month"]} is on hold')
    for r in db.execute(text("""select id,employee_id,exception_type,description from attendance_exceptions where resolved = false order by created_at desc""")).mappings():
        add("ATTENDANCE_EXCEPTION","OPERATIONS","MEDIUM","ATTENDANCE_EXCEPTION",r["id"],r["description"] or r["exception_type"])
    for r in db.execute(text("""select id,compliance_type,period,due_date from corporate_compliances where due_date < current_date and status not in ('FILED','COMPLETED','COMPLIANT') order by due_date""")).mappings():
        add("COMPLIANCE_OVERDUE","STATUTORY","HIGH","CORPORATE_COMPLIANCE",r["id"],f'{r["compliance_type"]} for {r["period"]} is overdue')
    return {"count": len(risks), "risks": risks}
