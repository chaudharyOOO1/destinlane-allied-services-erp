from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import require_management
from app.core.database import get_db

router = APIRouter()


@router.get("/executive-summary")
def executive_summary(db: Session = Depends(get_db), current_user=Depends(require_management)):
    revenue = float(db.execute(text("select coalesce(sum(total_amount),0) from invoices where status <> 'DRAFT'")).scalar() or 0)
    expenses = float(db.execute(text("select coalesce(sum(amount),0) from expenses")).scalar() or 0)
    payroll = float(db.execute(text("select coalesce(sum(net_pay),0) from salary_records where lifecycle_status in ('CALCULATED','APPROVED','DISBURSED','HELD')")).scalar() or 0)
    statutory = float(db.execute(text("select coalesce(sum(pf+esic+lwf),0) from salary_records")).scalar() or 0)
    net_profit = revenue - expenses - payroll - statutory
    margin = round((net_profit / revenue * 100), 2) if revenue else 0

    clients = db.execute(text("""select c.id,c.company_name,
      coalesce(sum(i.total_amount),0) revenue,
      coalesce((select sum(e.amount) from expenses e where e.client_id=c.id),0) expenses,
      coalesce((select sum(ss.net_pay) from salary_slips ss join attendance a on a.employee_id=ss.employee_id
        join shift_rosters r on r.id=a.roster_id join sites s on s.id=r.site_id
        where s.client_id=c.id),0) payroll
      from clients c left join invoices i on i.client_id=c.id and i.status <> 'DRAFT'
      group by c.id,c.company_name order by revenue desc""")).mappings().all()

    risks = []
    overdue = db.execute(text("""select i.invoice_number,c.company_name,i.due_date,i.total_amount
      from invoices i join clients c on c.id=i.client_id
      where i.status in ('SENT','PARTIALLY_PAID','OVERDUE') and i.due_date < current_date - interval '15 days'""")).mappings().all()
    risks += [{"type":"FINANCIAL","severity":"HIGH","message":f"Invoice {r['invoice_number']} for {r['company_name']} is overdue by more than 15 days.","reference":dict(r)} for r in overdue]
    uniform = db.execute(text("""select e.employee_code,e.name,sp.uniform_balance_due
      from staff_profiles sp join employees e on e.id=sp.employee_id
      where sp.uniform_balance_due > 0 and e.status::text in ('terminated','TERMINATED')""")).mappings().all()
    risks += [{"type":"FINANCIAL","severity":"MEDIUM","message":f"Unrecovered uniform balance for {r['name']} ({r['employee_code']}).","reference":dict(r)} for r in uniform]
    compliance = db.execute(text("""select e.employee_code,e.name,sp.police_verification_expiry,sp.gun_license_expiry
      from staff_profiles sp join employees e on e.id=sp.employee_id
      where (sp.police_verification_expiry is not null and sp.police_verification_expiry < current_date)
         or (sp.gun_license_expiry is not null and sp.gun_license_expiry < current_date)""")).mappings().all()
    risks += [{"type":"COMPLIANCE","severity":"HIGH","message":f"Expired deployment compliance detected for {r['name']} ({r['employee_code']}).","reference":dict(r)} for r in compliance]
    return {
      "kpis":{"revenue":round(revenue,2),"expenses":round(expenses,2),"payroll":round(payroll,2),
        "statutory_liabilities":round(statutory,2),"net_profit":round(net_profit,2),"net_margin_percent":margin},
      "p_and_l":[dict(r) for r in clients],
      "risks":risks,
      "risk_count":len(risks)
    }
