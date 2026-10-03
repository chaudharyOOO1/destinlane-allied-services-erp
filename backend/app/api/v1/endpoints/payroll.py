from calendar import monthrange
from datetime import date
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import require_accounts_or_admin, require_hr_or_admin
from app.core.database import get_db
from app.services.company import company_document_profile

router = APIRouter()


def _month(value: str) -> date:
    try:
        return date.fromisoformat(f"{value}-01")
    except ValueError:
        raise HTTPException(422, "month must use YYYY-MM format")


@router.get("/payroll")
def list_payroll(month: str | None = None, db: Session = Depends(get_db), current_user=Depends(require_hr_or_admin)):
    q = """select ss.*,e.employee_code,e.name,pr.payroll_month,pr.status payroll_status
      from salary_slips ss join employees e on e.id=ss.employee_id
      join payroll_runs pr on pr.id=ss.payroll_run_id"""
    params = {}
    if month:
        q += " where pr.payroll_month=:month"
        params["month"] = _month(month)
    q += " order by pr.payroll_month desc,e.name"
    return [dict(r) for r in db.execute(text(q), params).mappings().all()]


@router.post("/payroll/calculate")
def calculate_payroll(payload: dict, db: Session = Depends(get_db), current_user=Depends(require_hr_or_admin)):
    payroll_month = _month(str(payload.get("month", "")))
    last_day = monthrange(payroll_month.year, payroll_month.month)[1]
    month_end = date(payroll_month.year, payroll_month.month, last_day)

    run = db.execute(text("""insert into payroll_runs(payroll_month,status,calculated_at)
      values(:month,'CALCULATED',now())
      on conflict(payroll_month) do update set status='CALCULATED',calculated_at=now(),updated_at=now()
      returning *"""), {"month": payroll_month}).mappings().one()

    rows = db.execute(text("""select e.id employee_id,e.employee_code,e.name,
      coalesce(sp.category,e.category,'STAFF') category,
      coalesce(gp.daily_rate,0) daily_rate,
      coalesce(sp.uniform_monthly_emi,0) uniform_emi,
      coalesce(sp.uniform_balance_due,0) uniform_balance_due,
      sp.police_verification_expiry,sp.medical_fitness_expiry,
      coalesce(e.status,'active') employee_status,
      count(a.id) filter (where a.status::text in ('present','PRESENT','late','LATE')) present_days,
      coalesce(sum(a.shift_hours),0) regular_hours,
      coalesce(sum(a.overtime_hours),0) overtime_hours,
      count(a.id) filter (where r.shift_type='NIGHT' and a.status::text in ('present','PRESENT','late','LATE')) night_days
      from employees e
      left join staff_profiles sp on sp.employee_id=e.id
      left join guard_profiles gp on gp.employee_id=e.id
      left join attendance a on a.employee_id=e.id
        and a.attendance_date between :start_date and :end_date
        and a.is_geofence_verified=true
      left join shift_rosters r on r.id=a.roster_id
      group by e.id,e.employee_code,e.name,sp.category,e.category,gp.daily_rate,
        sp.uniform_monthly_emi,sp.uniform_balance_due,sp.police_verification_expiry,
        sp.medical_fitness_expiry,e.status
      order by e.name"""), {"start_date": payroll_month, "end_date": month_end}).mappings().all()

    created = 0
    held = 0
    for row in rows:
        daily = float(row["daily_rate"] or 0)
        basic = float(row["present_days"] or 0) * daily
        hra = round(basic * 0.10, 2)
        allowances = round(basic * 0.05, 2)
        overtime_pay = round(float(row["overtime_hours"] or 0) * (daily / 8.0) * 1.5, 2)
        night_allowance = round(float(row["night_days"] or 0) * 50.0, 2)
        gross = round(basic + hra + allowances + overtime_pay + night_allowance, 2)
        pf = round(basic * 0.12, 2)
        esic = round(gross * 0.0075, 2)
        lwf = 50.0 if gross > 0 else 0.0
        uniform = min(float(row["uniform_monthly_emi"] or 0), gross)
        deductions = round(pf + esic + lwf + uniform, 2)
        net = round(max(gross - deductions, 0), 2)
        reasons = []
        if not row["police_verification_expiry"] or row["police_verification_expiry"] < payroll_month:
            reasons.append("Missing/expired Police Verification")
        if str(row["employee_status"]).lower() in {"absconding", "terminated"}:
            reasons.append("Absconding/terminated status")
        if float(row["uniform_balance_due"] or 0) > 0:
            reasons.append("Pending Uniform Cost")
        lifecycle = "HELD" if reasons else "CALCULATED"
        hold_reason = "; ".join(reasons) if reasons else None
        existing = db.execute(text("select id from salary_slips where payroll_run_id=:run and employee_id=:employee"), {"run": run["id"], "employee": row["employee_id"]}).scalar()
        data = {"run":run["id"],"employee":row["employee_id"],"present_days":row["present_days"] or 0,"regular_hours":row["regular_hours"] or 0,
          "overtime_hours":row["overtime_hours"] or 0,"basic":basic,"hra":hra,"allowances":allowances,"overtime_pay":overtime_pay,
          "night_shift_allowance":night_allowance,"gross_pay":gross,"pf":pf,"esic":esic,"lwf":lwf,"uniform_emi":uniform,
          "total_deductions":deductions,"net_pay":net,"lifecycle_status":lifecycle,"hold_reason":hold_reason}
        if existing:
            db.execute(text("""update salary_slips set present_days=:present_days,regular_hours=:regular_hours,overtime_hours=:overtime_hours,
              basic=:basic,hra=:hra,allowances=:allowances,overtime_pay=:overtime_pay,night_shift_allowance=:night_shift_allowance,
              gross_pay=:gross_pay,pf=:pf,esic=:esic,lwf=:lwf,uniform_emi=:uniform_emi,total_deductions=:total_deductions,
              net_pay=:net_pay,lifecycle_status=:lifecycle_status,hold_reason=:hold_reason,updated_at=now() where id=:id"""),
              {**data,"id":existing})
        else:
            db.execute(text("""insert into salary_slips(payroll_run_id,employee_id,present_days,regular_hours,overtime_hours,basic,hra,allowances,
              overtime_pay,night_shift_allowance,gross_pay,pf,esic,lwf,uniform_emi,total_deductions,net_pay,lifecycle_status,hold_reason)
              values(:run,:employee,:present_days,:regular_hours,:overtime_hours,:basic,:hra,:allowances,:overtime_pay,:night_shift_allowance,
              :gross_pay,:pf,:esic,:lwf,:uniform_emi,:total_deductions,:net_pay,:lifecycle_status,:hold_reason)"""), data)
        created += 1
        if reasons: held += 1
    db.commit()
    return {"payroll_run_id":run["id"],"month":payroll_month.isoformat()[:7],"employees_processed":created,"salary_holds":held,"status":"CALCULATED"}


@router.post("/payroll/{slip_id}/hold")
def hold_salary(slip_id: int, payload: dict, db: Session = Depends(get_db), current_user=Depends(require_hr_or_admin)):
    reason = str(payload.get("reason") or "").strip()
    audit_note = str(payload.get("audit_note") or "").strip()
    if reason not in {"Missing Police Verification","Absconding","Pending Uniform Cost","Manual Flag"}:
        raise HTTPException(422, "Invalid salary hold reason")
    if not audit_note:
        raise HTTPException(422, "audit_note is required")
    row = db.execute(text("""update salary_slips set lifecycle_status='HELD',hold_reason=:reason,updated_at=now()
      where id=:id returning *"""), {"id":slip_id,"reason":reason}).mappings().first()
    if not row: raise HTTPException(404, "Salary slip not found")
    db.execute(text("""insert into salary_slip_holds(salary_slip_id,reason,audit_note,created_by)
      values(:slip,:reason,:note,:user)"""), {"slip":slip_id,"reason":reason,"note":audit_note,"user":current_user.id})
    db.commit()
    return dict(row)


@router.get("/payroll/slips/{slip_id}/pdf")
def salary_slip_pdf(slip_id: int, db: Session = Depends(get_db), current_user=Depends(require_hr_or_admin)):
    row = db.execute(text("""select ss.*,e.employee_code,e.name,e.category,pr.payroll_month
      from salary_slips ss join employees e on e.id=ss.employee_id join payroll_runs pr on pr.id=ss.payroll_run_id
      where ss.id=:id"""), {"id":slip_id}).mappings().first()
    if not row: raise HTTPException(404, "Salary slip not found")
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError:
        raise HTTPException(500, "PDF dependency is not installed")
    buf = BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    pdf.setTitle(f"Salary Slip {row['employee_code']}")
    y = 800
    company = company_document_profile(db)
    from reportlab.lib.utils import simpleSplit
    pdf.setFont("Helvetica-Bold", 14)
    for line in simpleSplit(company['legal_name'], 'Helvetica-Bold', 14, 490):
        pdf.drawString(50, y, line); y -= 18
    pdf.setFont('Helvetica-Bold', 12); pdf.drawString(50, y, 'Salary Slip'); y -= 25
    pdf.setFont("Helvetica", 10); pdf.drawString(50,y,f"Employee: {row['name']} ({row['employee_code']})"); y -= 18
    pdf.drawString(50,y,f"Payroll Month: {row['payroll_month']}"); y -= 30
    for label,key in [("Present Days","present_days"),("Regular Hours","regular_hours"),("Overtime Hours","overtime_hours"),("Basic","basic"),("HRA","hra"),("Allowances","allowances"),("Overtime Pay","overtime_pay"),("Night Shift Allowance","night_shift_allowance"),("Gross Pay","gross_pay"),("PF","pf"),("ESIC","esic"),("LWF","lwf"),("Uniform EMI","uniform_emi"),("Total Deductions","total_deductions"),("Net Pay","net_pay")]:
        pdf.drawString(60,y,f"{label}: {row[key] or 0}"); y -= 17
    if row["hold_reason"]:
        y -= 10; pdf.setFont("Helvetica-Bold",10); pdf.drawString(60,y,f"SALARY HOLD: {row['hold_reason']}")
    pdf.save(); buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="application/pdf",
      headers={"Content-Disposition":f'attachment; filename="salary-slip-{row["employee_code"]}-{row["payroll_month"]}.pdf"'})


@router.post("/billing/generate")
def generate_attendance_invoice(payload: dict, db: Session = Depends(get_db), current_user=Depends(require_accounts_or_admin)):
    billing_month = _month(str(payload.get("month", "")))
    month_end = date(billing_month.year, billing_month.month, monthrange(billing_month.year,billing_month.month)[1])
    client_id = payload.get("client_id")
    filters = " and s.client_id=:client_id" if client_id else ""
    params = {"start":billing_month,"end":month_end}
    if client_id: params["client_id"]=int(client_id)
    rows = db.execute(text(f"""select s.id site_id,s.site_name,s.client_id,c.company_name,c.branch_region,s.branch_region site_region,
      count(a.id) filter (where a.status::text in ('present','PRESENT','late','LATE')) present_days,
      coalesce(sum(a.overtime_hours),0) overtime_hours,
      coalesce(sum(coalesce(rc.daily_rate,0)),0) service_value,
      coalesce(sum(coalesce(rc.hourly_rate,0) * coalesce(a.overtime_hours,0) * 1.5),0) overtime_value
      from sites s join clients c on c.id=s.client_id
      join shift_rosters r on r.site_id=s.id join attendance a on a.roster_id=r.id
      left join staff_profiles sp on sp.employee_id=a.employee_id
      left join site_rate_cards rc on rc.site_id=s.id and rc.vertical=coalesce(sp.vertical,'SECURITY') and rc.category=coalesce(sp.category,'STAFF') and rc.is_active=true
      where a.attendance_date between :start and :end and a.is_geofence_verified=true{filters}
      group by s.id,s.site_name,s.client_id,c.company_name,c.branch_region,c.gst_region"""),params).mappings().all()
    generated=[]
    for row in rows:
        subtotal=round(float(row["service_value"] or 0)+float(row["overtime_value"] or 0),2)
        if subtotal<=0: continue
        client_region=(row["branch_region"] or "").upper()
        site_state=(row["site_region"] or row["branch_region"] or "").upper()
        intra=client_region==site_state
        tax=round(subtotal*0.18,2); cgst=round(tax/2,2) if intra else 0; sgst=round(tax/2,2) if intra else 0; igst=tax if not intra else 0
        invoice_number=f"AUTO-{billing_month.strftime('%Y%m')}-{row['site_id']}"
        existing=db.execute(text("select id from invoices where invoice_number=:n"),{"n":invoice_number}).scalar()
        data={"client_id":row["client_id"],"invoice_number":invoice_number,"billing_month":billing_month.isoformat()[:7],"issue_date":date.today(),"due_date":month_end,
          "subtotal":subtotal,"tax_rate":18,"cgst":cgst,"sgst":sgst,"igst":igst,"tax_amount":tax,"total_amount":subtotal+tax,
          "status":"DRAFT","clearance_status":"PENDING","notes":f"Auto-generated from verified GPS attendance for {row['site_name']}"}
        if not existing:
            cols=", ".join(data); binds=", ".join(f":{k}" for k in data)
            invoice=db.execute(text(f"insert into invoices({cols}) values({binds}) returning *"),data).mappings().one()
            generated.append(dict(invoice))
    db.commit()
    return {"month":billing_month.isoformat()[:7],"invoices_created":len(generated),"invoices":generated}
