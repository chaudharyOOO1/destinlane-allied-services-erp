"""Authoritative dashboard queries and explicit unavailable/restricted states.

No seeds, browser-computed financial totals or MD journal access belong here.
Every source query runs only after its module's effective view permission. Each
section has its own savepoint so a missing/unavailable source cannot abort the
other sections or masquerade as a genuine zero.
"""
import logging
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)
CENT = Decimal('0.01')


def _money(value):
    return format(Decimal(value).quantize(CENT), '.2f')


def _one(db, query, params):
    return dict(db.execute(text(query), params).mappings().one())


def _rows(db, query, params):
    return [dict(row) for row in db.execute(text(query), params).mappings()]


def _restricted():
    return {'status': 'restricted', 'message': 'This information requires access to its source module.'}


def _workforce(db, access, params):
    result = {'employee_total': None, 'employee_active': None, 'staff_total': None, 'staff_active': None,
              'access': {'employees': access['employees.view'], 'staff': access['staff.view']}}
    if access['employees.view']:
        result.update(_one(db, """select count(*) employee_total,
            count(*) filter(where upper(status)='ACTIVE') employee_active from employees""", params))
    if access['staff.view']:
        result.update(_one(db, """select count(*) staff_total,
            count(*) filter(where status='ACTIVE') staff_active from internal_staff""", params))
    return result


def _deployment(db, access, params):
    result = _one(db, """select
        (select count(*) from sites where is_active=true) active_sites,
        count(*) filter(where date=:as_of) today_shifts,
        count(*) filter(where date>:as_of and date<=:week_end) upcoming_shifts
        from shift_rosters where date>=:as_of and date<=:week_end
        and status in ('SCHEDULED','COMPLETED')""", params)
    result['rosters'] = _rows(db, """select r.id,r.date,r.shift_type,r.status,s.site_name,
        coalesce(e.name,u.full_name) employee_name,coalesce(e.employee_code,g.badge_number) employee_code
        from shift_rosters r join sites s on s.id=r.site_id
        join guard_profiles g on g.id=r.guard_id left join employees e on e.id=g.employee_id
        left join users u on u.id=g.user_id
        where r.date>=:as_of and r.date<=:week_end and r.status in ('SCHEDULED','COMPLETED')
        order by r.date,r.shift_type,s.site_name,r.id limit 6""", params)
    return result


def _attendance(db, access, params):
    result = _one(db, """select count(*) recorded,
        count(*) filter(where lower(status) in ('present','late','half_day')) present,
        count(*) filter(where lower(status)='absent') absent,
        count(*) filter(where lower(status)='leave') leave,
        count(*) filter(where check_in_time is not null and check_out_time is null) checked_in,
        count(*) filter(where upper(verification_status) in ('PENDING','PENDING_REVIEW')) awaiting_review
        from attendance where attendance_date=:as_of""", params)
    result.update(scheduled_shifts=None, rostered_records=None, unrecorded_shifts=None)
    if access['rosters.view']:
        result.update(_one(db, """select count(*) scheduled_shifts,
            count(*) filter(where exists(select 1 from attendance a where a.roster_id=r.id
                and a.attendance_date=:as_of)) rostered_records,
            count(*) filter(where not exists(select 1 from attendance a where a.roster_id=r.id
                and a.attendance_date=:as_of)) unrecorded_shifts
            from shift_rosters r where r.date=:as_of and r.status in ('SCHEDULED','COMPLETED')""", params))
    return result


def _billing(db, access, params):
    # Status-only records cannot establish cash collections or part-payments.
    # Show the invoice face value as a separate operational measure; never call
    # it a receivable ledger balance or turn PAID invoices into bank receipts.
    result = _one(db, """select
        count(*) filter(where issue_date>=:month_start) issued_count,
        coalesce(sum(total_amount) filter(where issue_date>=:month_start),0) issued_amount,
        coalesce(sum(tax_amount) filter(where issue_date>=:month_start),0) output_gst,
        coalesce(sum(total_amount) filter(where cast(status as text)<>'PAID'
            and upper(coalesce(clearance_status,'PENDING'))<>'PAID'),0) unpaid_invoice_face_value
        from invoices where issue_date<=:as_of and cast(status as text) not in ('DRAFT','CANCELLED')""", params)
    for field in ('issued_amount', 'output_gst', 'unpaid_invoice_face_value'):
        result[field] = _money(result[field])
    result.update(eligible_itc=None, net_gst_estimate=None, collections=None, outstanding_amount=None,
                  collections_status='unavailable', access={'invoices': True, 'itc': access['finance.view']},
                  collection_note='Receipt allocation is not available. Unpaid invoice value uses invoice status; partial payments are not deducted.',
                  tax_note='Operational GST estimate from issued invoices and approved/reconciled ITC records. Not a statutory tax return or payment due.')
    if access['finance.view']:
        itc = _one(db, """select coalesce(sum(gst_amount),0) eligible_itc from gst_itc_ledger
            where created_at>=:period_start and created_at<:period_end
            and upper(reconciliation_status) in ('RECONCILED','APPROVED')""", params)['eligible_itc']
        result['eligible_itc'] = _money(itc)
        result['net_gst_estimate'] = _money(Decimal(result['output_gst']) - Decimal(str(itc)))
    result['recent_invoices'] = _rows(db, """select i.id,i.invoice_number,c.company_name,
        i.issue_date,i.due_date,i.total_amount,cast(i.status as text) status,i.clearance_status
        from invoices i join clients c on c.id=i.client_id
        where i.issue_date<=:as_of and cast(i.status as text) not in ('DRAFT','CANCELLED')
        order by i.issue_date desc,i.id desc limit 6""", params)
    for row in result['recent_invoices']:
        row['total_amount'] = _money(row['total_amount'])
    return result


def _compliance(db, access, params):
    result = _one(db, """select count(*) pending_corporate,
        count(*) filter(where due_date<:as_of) overdue_corporate,
        count(*) filter(where due_date>=:as_of and due_date<=:cutoff) due30_corporate
        from corporate_compliances where upper(coalesce(status,'PENDING')) not in ('FILED','COMPLETED','COMPLIANT')""", params)
    result['access'] = {'corporate': True, 'documents': access['employees.view']}
    reminders = _rows(db, """select id,'CORPORATE' type,compliance_type title,
        coalesce(period,'') detail,due_date,status,(due_date<:as_of) overdue
        from corporate_compliances where due_date<=:cutoff
        and upper(coalesce(status,'PENDING')) not in ('FILED','COMPLETED','COMPLIANT')
        order by due_date,id limit 6""", params)
    result.update(expiring_documents=None, expired_documents=None)
    if access['employees.view']:
        result.update(_one(db, """select
            count(*) filter(where expiry_date>=:as_of and expiry_date<=:cutoff) expiring_documents,
            count(*) filter(where expiry_date<:as_of) expired_documents
            from employee_documents where expiry_date is not null
            and upper(coalesce(status,'VALID'))<>'CANCELLED'""", params))
        # Include already-expired documents, regardless of their status label.
        reminders += _rows(db, """select d.id,'DOCUMENT' type,d.document_type title,
            e.name detail,d.expiry_date due_date,d.status,(d.expiry_date<:as_of) overdue
            from employee_documents d join employees e on e.id=d.employee_id
            where d.expiry_date<=:cutoff and upper(coalesce(d.status,'VALID'))<>'CANCELLED'
            order by d.expiry_date,d.id limit 6""", params)
    result['reminders'] = sorted(reminders, key=lambda row: (row['due_date'], str(row['id'])))[:6]
    return result


def build_dashboard(db, permissions: dict, as_of: date, generated_at: datetime):
    access = {key: bool(permissions.get(key)) for key in (
        'employees.view', 'staff.view', 'sites.view', 'rosters.view',
        'attendance.view', 'billing.view', 'finance.view', 'compliance.view')}
    india = ZoneInfo('Asia/Kolkata')
    params = {'as_of': as_of, 'month_start': as_of.replace(day=1),
              'period_start': datetime.combine(as_of.replace(day=1), time.min, india),
              'period_end': datetime.combine(as_of + timedelta(days=1), time.min, india),
              'week_end': as_of + timedelta(days=7),
              'cutoff': as_of + timedelta(days=30)}
    definitions = (
        ('workforce', access['employees.view'] or access['staff.view'], _workforce),
        ('deployment', access['sites.view'] and access['rosters.view'], _deployment),
        ('attendance', access['attendance.view'], _attendance),
        ('billing', access['billing.view'], _billing),
        ('compliance', access['compliance.view'], _compliance),
    )
    sections = {}
    for name, allowed, load in definitions:
        if not allowed:
            sections[name] = _restricted()
            continue
        try:
            with db.begin_nested():
                sections[name] = {'status': 'ready', **load(db, access, params)}
        except SQLAlchemyError as exc:
            # Do not log SQL, bound values, names or financial records.
            logger.warning('Dashboard section unavailable: %s (%s)', name, type(exc).__name__)
            sections[name] = {'status': 'error', 'message': 'This information could not be loaded. Refresh or open the source module.'}
    return {'as_of': as_of, 'generated_at': generated_at, 'month': as_of.strftime('%Y-%m'),
            'month_label': as_of.strftime('%B %Y'), 'sections': sections}
