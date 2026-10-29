from calendar import monthrange
from datetime import date
from io import BytesIO
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.core.business_time import business_date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import require_accounts_or_admin, require_hr_or_admin
from app.core.database import get_db
from app.api.deps import require_management, require_payroll, require_roles
from app.models.enums import UserRole
from app.services.company import company_document_profile

router = APIRouter()


def _money(value):
    return Decimal(str(value or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)



@router.get("/billing/invoices")
def list_billing_invoices(db: Session = Depends(get_db), current_user=Depends(require_accounts_or_admin)):
    """Billing-only directory; finance ledgers are deliberately outside this response.

    The request permission mapper enforces billing.view separately from finance.view.
    Keep these invoice fields explicit so new account-ledger data cannot leak through.
    """
    rows = db.execute(text("""select i.id,i.client_id,c.company_name as client_name,
      i.invoice_number,i.billing_month,i.issue_date,i.due_date,i.subtotal,i.tax_rate,
      i.cgst,i.sgst,i.igst,i.tax_amount,i.total_amount,i.status,i.clearance_status,
      i.notes,i.created_at,i.updated_at
      from invoices i join clients c on c.id=i.client_id
      order by i.issue_date desc,i.id desc""")).mappings().all()
    return [dict(row) for row in rows]


def _month(value: str) -> date:
    try:
        return date.fromisoformat(f"{value}-01")
    except ValueError:
        raise HTTPException(422, "month must use YYYY-MM format")


@router.get("/payroll")
def list_payroll(month: str | None = None, db: Session = Depends(get_db), current_user=Depends(require_payroll)):
    q = """select ss.*,e.employee_code,e.name,pr.payroll_month,pr.status payroll_status
      from salary_slips ss join employees e on e.id=ss.employee_id
      join payroll_runs pr on pr.id=ss.payroll_run_id"""
    params = {}
    if month:
        q += " where pr.payroll_month=:month"
        params["month"] = _month(month)
    q += " order by pr.payroll_month desc,e.name"
    return [dict(r) for r in db.execute(text(q), params).mappings().all()]


class WageCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    employee_id: UUID
    effective_from: date
    daily_rate: Decimal = Field(gt=0, le=99999999, max_digits=10, decimal_places=2)
    reason: str = Field(min_length=5, max_length=1000)


@router.get('/payroll/wages')
def list_wages(db:Session=Depends(get_db),current_user=Depends(require_payroll)):
    return [dict(r) for r in db.execute(text("""select e.id employee_id,e.employee_code,e.name,
        w.id,w.effective_from,w.daily_rate,w.reason,w.created_at
        from employees e left join employee_wage_rates w on w.employee_id=e.id
        order by e.name,w.effective_from desc""")).mappings().all()]


@router.post('/payroll/wages',status_code=201)
def create_wage(payload:WageCreate,db:Session=Depends(get_db),current_user=Depends(require_payroll)):
    # Employee lock serializes rate setup and makes duplicate retries explicit.
    employee=db.execute(text('select id from employees where id=:id for update'),{'id':payload.employee_id}).first()
    if not employee: raise HTTPException(404,'Employee not found')
    finalised=db.execute(text("""select ss.id from salary_slips ss join payroll_runs pr on pr.id=ss.payroll_run_id
        where ss.employee_id=:id and upper(ss.lifecycle_status) in ('APPROVED','DISBURSED','PAID')
        and (pr.payroll_month + interval '1 month')::date > :effective limit 1"""),
        {'id':payload.employee_id,'effective':payload.effective_from}).first()
    if finalised: raise HTTPException(409,'This rate would change a finalised payroll period. Choose a later effective date.')
    data=payload.model_dump();data['user']=current_user.id
    row=db.execute(text("""insert into employee_wage_rates(employee_id,effective_from,daily_rate,reason,created_by)
        values(:employee_id,:effective_from,:daily_rate,:reason,:user)
        on conflict(employee_id,effective_from) do nothing returning *"""),data).mappings().first()
    if not row: raise HTTPException(409,'A wage rate already exists for this effective date; retain its history.')
    result=dict(row);db.commit();return result


@router.post("/payroll/calculate")
def calculate_payroll(payload: dict, db: Session = Depends(get_db), current_user=Depends(require_payroll)):
    payroll_month = _month(str(payload.get("month", "")))
    last_day = monthrange(payroll_month.year, payroll_month.month)[1]
    month_end = date(payroll_month.year, payroll_month.month, last_day)

    # Serialize calculations for one month, including the first run. The lock
    # lasts until commit/rollback and prevents concurrent lifecycle overwrites.
    db.execute(text("select pg_advisory_xact_lock(71025, :month)"),
               {"month": payroll_month.year * 100 + payroll_month.month})
    existing_run = db.execute(text('select status from payroll_runs where payroll_month=:month for update'),
                              {'month':payroll_month}).mappings().first()
    if existing_run and str(existing_run['status']).upper() in {'APPROVED','DISBURSED','PAID'}:
        raise HTTPException(409,'Finalised payroll run cannot be recalculated')
    finalised = db.execute(text("""select ss.id from salary_slips ss
        join payroll_runs pr on pr.id=ss.payroll_run_id
        where pr.payroll_month=:month
        and upper(ss.lifecycle_status) in ('APPROVED','DISBURSED','PAID')
        limit 1"""), {"month": payroll_month}).first()
    if finalised:
        raise HTTPException(409, "Finalised payroll cannot be recalculated; use a reviewed adjustment")

    run = db.execute(text("""insert into payroll_runs(payroll_month,status,calculated_at)
      values(:month,'CALCULATED',now())
      on conflict(payroll_month) do update set status='CALCULATED',calculated_at=now(),updated_at=now()
      returning *"""), {"month": payroll_month}).mappings().one()

    rows = db.execute(text("""select e.id employee_id,e.employee_code,e.name,
      coalesce(sp.category,e.category,'STAFF') category,
      coalesce(sum(w.daily_rate),0) earned_basic,
      coalesce(sum(a.overtime_hours*w.daily_rate/8*1.5),0) earned_overtime,
      count(a.id) filter (where w.id is null) missing_wage_days,
      coalesce(sp.uniform_monthly_emi,0) uniform_monthly_emi,
      coalesce(sp.uniform_balance_due,0) uniform_balance_due,
      sp.police_verification_expiry,sp.medical_fitness_expiry,
      coalesce(e.status,'active') employee_status,
      count(a.id) filter (where a.status::text in ('present','PRESENT','late','LATE')) present_days,
      count(a.id) filter (where rc.id is null) missing_rate_days,
      coalesce(sum(a.shift_hours),0) regular_hours,
      coalesce(sum(a.overtime_hours),0) overtime_hours,
      count(a.id) filter (where r.shift_type='NIGHT' and a.status::text in ('present','PRESENT','late','LATE')) night_days
      from employees e
      left join staff_profiles sp on sp.employee_id=e.id
      left join guard_profiles gp on gp.employee_id=e.id
      left join attendance a on a.employee_id=e.id
        and a.attendance_date between :start_date and :end_date
        and a.verification_status='VERIFIED' and a.check_out_time is not null and a.status in ('present','late','PRESENT','LATE')
      left join lateral (select wr.id,wr.daily_rate from employee_wage_rates wr
        where wr.employee_id=e.id and wr.effective_from<=a.attendance_date
        order by wr.effective_from desc limit 1) w on true
      left join shift_rosters r on r.id=a.roster_id
      group by e.id,e.employee_code,e.name,sp.category,e.category,
        sp.uniform_monthly_emi,sp.uniform_balance_due,sp.police_verification_expiry,
        sp.medical_fitness_expiry,e.status
      order by e.name"""), {"start_date": payroll_month, "end_date": month_end}).mappings().all()

    missing=[r['employee_code'] for r in rows if r['missing_wage_days']]
    if missing:
        raise HTTPException(409,'Set employee wages effective on every attendance date before calculating: '+', '.join(missing))
    created = 0
    held = 0
    for row in rows:
        basic = _money(row["earned_basic"])
        hra = _money(basic * Decimal('0.10'))
        allowances = _money(basic * Decimal('0.05'))
        overtime_pay = _money(row["earned_overtime"])
        night_allowance = _money(Decimal(str(row["night_days"] or 0)) * 50)
        gross = _money(basic + hra + allowances + overtime_pay + night_allowance)
        pf = _money(basic * Decimal('0.12'))
        esic = _money(gross * Decimal('0.0075'))
        lwf = Decimal('50.00') if gross > 0 else Decimal('0.00')
        uniform = min(_money(row["uniform_monthly_emi"]), gross)
        deductions = _money(pf + esic + lwf + uniform)
        net = _money(max(gross - deductions, Decimal(0)))
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
def hold_salary(slip_id: int, payload: dict, db: Session = Depends(get_db), current_user=Depends(require_payroll)):
    reason = str(payload.get("reason") or "").strip()
    audit_note = str(payload.get("audit_note") or "").strip()
    if reason not in {"Missing Police Verification","Absconding","Pending Uniform Cost","Manual Flag"}:
        raise HTTPException(422, "Invalid salary hold reason")
    if not audit_note:
        raise HTTPException(422, "audit_note is required")
    slip = db.execute(text("select lifecycle_status from salary_slips where id=:id for update"),
                      {"id": slip_id}).mappings().first()
    if not slip:
        raise HTTPException(404, "Salary slip not found")
    if str(slip["lifecycle_status"]).upper() in {"APPROVED", "DISBURSED", "PAID"}:
        raise HTTPException(409, "Finalised salary cannot be placed on hold")
    row = db.execute(text("""update salary_slips set lifecycle_status='HELD',hold_reason=:reason,updated_at=now()
      where id=:id returning *"""), {"id":slip_id,"reason":reason}).mappings().first()
    if not row: raise HTTPException(404, "Salary slip not found")
    db.execute(text("""insert into salary_slip_holds(salary_slip_id,reason,audit_note,created_by)
      values(:slip,:reason,:note,:user)"""), {"slip":slip_id,"reason":reason,"note":audit_note,"user":current_user.id})
    db.commit()
    return dict(row)


@router.get("/payroll/slips/{slip_id}/pdf")
def salary_slip_pdf(slip_id: int, db: Session = Depends(get_db), current_user=Depends(require_payroll)):
    row = db.execute(text("""select ss.*,e.employee_code,e.name,e.category,pr.payroll_month
      from salary_slips ss join employees e on e.id=ss.employee_id join payroll_runs pr on pr.id=ss.payroll_run_id
      where ss.id=:id"""), {"id":slip_id}).mappings().first()
    if not row: raise HTTPException(404, "Salary slip not found")
    return render_salary_slip(db, row)


def render_salary_slip(db, row):
    """Render only an already-authorised salary row; callers enforce ownership."""
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
    # The selector is optional, but any supplied ID must be a positive DB integer.
    # Validate it before querying to avoid uncaught ValueError/overflow HTTP 500s.
    raw_client_id = payload.get("client_id")
    client_id = None
    if raw_client_id is not None and raw_client_id != "":
        if isinstance(raw_client_id, bool) or not isinstance(raw_client_id, (int, str)):
            raise HTTPException(422, "client_id must be a positive integer")
        client_id_text = str(raw_client_id).strip()
        if not (1 <= len(client_id_text) <= 10 and client_id_text.isascii()
                and client_id_text.isdecimal()):
            raise HTTPException(422, "client_id must be a positive integer")
        client_id = int(client_id_text)
        if not 1 <= client_id <= 2147483647:
            raise HTTPException(422, "client_id must be a positive integer")
    filters = " and s.client_id=:client_id" if client_id is not None else ""
    params = {"start":billing_month,"end":month_end}
    if client_id is not None: params["client_id"]=client_id
    rows = db.execute(text(f"""select s.id site_id,s.site_name,s.client_id,c.company_name,c.branch_region,s.branch_region site_region,
      count(a.id) filter (where a.status::text in ('present','PRESENT','late','LATE')) present_days,
      coalesce(sum(a.overtime_hours),0) overtime_hours,
      coalesce(sum(coalesce(rc.daily_rate,0)),0) service_value,
      coalesce(sum(coalesce(rc.hourly_rate,0) * coalesce(a.overtime_hours,0) * 1.5),0) overtime_value
      from sites s join clients c on c.id=s.client_id
      join shift_rosters r on r.site_id=s.id join attendance a on a.roster_id=r.id
      left join staff_profiles sp on sp.employee_id=a.employee_id
      left join site_rate_cards rc on rc.site_id=s.id and rc.vertical=coalesce(sp.vertical,'SECURITY') and rc.category=coalesce(sp.category,'STAFF') and rc.is_active=true
        and rc.effective_from<=a.attendance_date and (rc.effective_to is null or rc.effective_to>=a.attendance_date)
        and (rc.contract_id is null or exists(select 1 from client_contracts cc where cc.id=rc.contract_id and cc.status in ('ACTIVE','RENEWED','EXPIRED','TERMINATED') and a.attendance_date between cc.contract_start_date and cc.contract_end_date))
      where a.attendance_date between :start and :end and a.verification_status='VERIFIED' and a.check_out_time is not null and a.status in ('present','late','PRESENT','LATE'){filters}
      group by s.id,s.site_name,s.client_id,c.company_name,c.branch_region,s.branch_region"""),params).mappings().all()
    # Never issue a partial invoice when verified attendance lacks an effective
    # rate card. Check all selected sites before inserting any invoice.
    missing_rates = [str(row['site_name']) for row in rows if row['missing_rate_days']]
    if missing_rates:
        raise HTTPException(409, 'Missing effective billing rates for verified attendance at: ' + ', '.join(missing_rates))
    generated=[]
    for row in rows:
        subtotal=round(float(row["service_value"] or 0)+float(row["overtime_value"] or 0),2)
        if subtotal<=0: continue
        client_region=(row["branch_region"] or "").upper()
        site_state=(row["site_region"] or row["branch_region"] or "").upper()
        intra=client_region==site_state
        tax=round(subtotal*0.18,2); cgst=round(tax/2,2) if intra else 0; sgst=round(tax/2,2) if intra else 0; igst=tax if not intra else 0
        invoice_number=f"AUTO-{billing_month.strftime('%Y%m')}-{row['site_id']}"
        data={"client_id":row["client_id"],"invoice_number":invoice_number,"billing_month":billing_month.isoformat()[:7],"issue_date":business_date(),"due_date":max(business_date(),month_end),
          "subtotal":subtotal,"tax_rate":18,"cgst":cgst,"sgst":sgst,"igst":igst,"tax_amount":tax,"total_amount":subtotal+tax,
          "status":"DRAFT","clearance_status":"PENDING","notes":f"Auto-generated from approved attendance for {row['site_name']}"}
        # A unique invoice number also protects parallel retries; a separate
        # SELECT-before-INSERT leaves a race that may otherwise surface as HTTP 500.
        cols=", ".join(data); binds=", ".join(f":{k}" for k in data)
        invoice=db.execute(text(
            f"insert into invoices({cols}) values({binds}) "
            "on conflict (invoice_number) do nothing returning *"
        ),data).mappings().first()
        if invoice is not None:
            generated.append(dict(invoice))
    db.commit()
    return {"month":billing_month.isoformat()[:7],"invoices_created":len(generated),"invoices":generated}
