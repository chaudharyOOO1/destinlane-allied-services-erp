"""Real source totals, permission boundaries and recoverable dashboard failures."""
from datetime import datetime, timedelta

from sqlalchemy import event, text

from test_postgres_workflow import postgres_workflow
from app.models.enums import UserRole
from app.models.user import User

BASE = '/api/v1/erp/dashboard'


def login(http, identifier='TEST-OWNER'):
    response = http.post('/api/v1/auth/login', json={'login_id': identifier, 'password': 'local-test-password'})
    assert response.status_code == 200, response.text
    return {'Authorization': 'Bearer ' + response.json()['access_token']}


def get_dashboard(http, headers):
    response = http.get(BASE, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_empty_source_is_zero_and_not_mocked(postgres_workflow):
    http, sessions, _, today, *_ = postgres_workflow
    assert http.get(BASE).status_code == 401
    result = get_dashboard(http, login(http))
    assert result['as_of'] == today.isoformat()
    assert result['month'] == today.strftime('%Y-%m')
    assert datetime.fromisoformat(result['generated_at']).utcoffset() == timedelta(0)
    sections = result['sections']
    assert all(section['status'] == 'ready' for section in sections.values())
    assert sections['workforce']['employee_total'] == sections['workforce']['staff_total'] == 0
    assert sections['deployment']['active_sites'] == 1  # The real fixture's configured site.
    assert sections['deployment']['today_shifts'] == 0
    assert sections['attendance']['recorded'] == sections['attendance']['unrecorded_shifts'] == 0
    assert sections['billing']['issued_amount'] == '0.00'
    assert sections['billing']['collections'] is None
    assert sections['billing']['outstanding_amount'] is None
    assert sections['compliance']['reminders'] == []
    with sessions() as db:
        assert db.execute(text('select count(*) from md_journal_entries')).scalar_one() == 0
        assert db.execute(text('select count(*) from employees')).scalar_one() == 0


def test_totals_use_canonical_records_and_include_expired_documents(postgres_workflow):
    http, sessions, _, today, start, owner_id, hr_id, client_id, site_id, _ = postgres_workflow
    with sessions() as db:
        employees = []
        for number, status in enumerate(('ACTIVE', 'DRAFT', 'INACTIVE')):
            employees.append(db.execute(text("""insert into employees(name,phone,status)
                values(:name,:phone,:status) returning id"""),
                {'name': f'Local worker {number}', 'phone': f'98765432{30+number}', 'status': status}).scalar_one())
        for number, status in enumerate(('ACTIVE', 'INACTIVE')):
            db.execute(text("""insert into internal_staff(staff_code,name,phone,profile,status)
                values(:code,'Local office staff',:phone,'{}',:status)"""),
                {'code': f'DASS{10+number:04d}', 'phone': f'98765432{40+number}', 'status': status})
        guards = []
        for user, employee, badge in zip((owner_id, hr_id), employees, ('TEST-G1', 'TEST-G2')):
            guards.append(db.execute(text("""insert into guard_profiles(user_id,employee_id,badge_number,daily_rate,status)
                values(:user,:employee,:badge,0,'ACTIVE') returning id"""),
                {'user': user, 'employee': employee, 'badge': badge}).scalar_one())
        rosters = []
        for guard, day, shift, status in ((guards[0], today, 'GENERAL', 'SCHEDULED'),
                (guards[1], today, 'GENERAL', 'SCHEDULED'),
                (guards[0], today + timedelta(days=1), 'GENERAL', 'SCHEDULED'),
                (guards[0], today, 'DAY', 'CANCELLED')):
            rosters.append(db.execute(text("""insert into shift_rosters(site_id,guard_id,date,shift_type,status)
                values(:site,:guard,:day,:shift,:status) returning id"""),
                {'site': site_id, 'guard': guard, 'day': day, 'shift': shift, 'status': status}).scalar_one())
        db.execute(text("""insert into attendance(employee_id,roster_id,attendance_date,status,check_in_time,verification_status)
            values(:employee,:roster,:day,'present',:start,'PENDING_REVIEW')"""),
            {'employee': employees[0], 'roster': rosters[0], 'day': today, 'start': start})
        db.execute(text("""insert into attendance(employee_id,attendance_date,status,verification_status)
            values(:employee,:day,'absent','VERIFIED')"""), {'employee': employees[2], 'day': today})
        for number, (day, amount, status, clearance) in enumerate((
                (today, 100, 'SENT', 'PENDING'), (today, 200, 'PAID', 'PAID'),
                (today, 999, 'DRAFT', 'PENDING'), (today, 888, 'CANCELLED', 'PENDING'),
                (today.replace(day=1) - timedelta(days=1), 300, 'OVERDUE', 'PENDING'),
                (today + timedelta(days=1), 500, 'SENT', 'PENDING'))):
            db.execute(text("""insert into invoices(client_id,invoice_number,billing_month,issue_date,due_date,
                subtotal,tax_amount,total_amount,status,clearance_status)
                values(:client,:number,:month,:day,:day,:amount,:amount*0.18,:amount*1.18,:status,:clearance)"""),
                {'client': client_id, 'number': f'TEST-INV-{number}', 'month': day.strftime('%Y-%m'),
                 'day': day, 'amount': amount, 'status': status, 'clearance': clearance})
        india_month_start = datetime.fromisoformat(today.replace(day=1).isoformat() + 'T00:01:00+05:30')
        for day, amount, status in ((india_month_start, 4, 'APPROVED'), (today, 50, 'PENDING'),
                (today + timedelta(days=1), 5, 'RECONCILED'),
                (today.replace(day=1) - timedelta(days=1), 6, 'APPROVED')):
            db.execute(text("""insert into gst_itc_ledger(gst_amount,reconciliation_status,created_at)
                values(:amount,:status,:day)"""), {'amount': amount, 'status': status, 'day': day})
        for day, status in ((today - timedelta(days=1), 'PENDING'),
                (today + timedelta(days=10), 'PENDING'), (today - timedelta(days=2), 'FILED'), (None, 'PENDING')):
            db.execute(text("""insert into corporate_compliances(compliance_type,due_date,status)
                values('Local compliance',:day,:status)"""), {'day': day, 'status': status})
        for number, (day, status) in enumerate(((today - timedelta(days=3), 'EXPIRED'),
                (today + timedelta(days=10), 'VALID'), (today - timedelta(days=5), 'CANCELLED'))):
            db.execute(text("""insert into employee_documents(employee_id,document_type,expiry_date,status,
                original_filename,storage_path,mime_type,size_bytes,sha256)
                values(:employee,'POLICE_VERIFICATION',:day,:status,'local.pdf',:path,'application/pdf',100,:sha)"""),
                {'employee': employees[0], 'day': day, 'status': status,
                 'path': f'test/{number}.pdf', 'sha': str(number) * 64})
        db.commit()
    sections = get_dashboard(http, login(http))['sections']
    assert all(section['status'] == 'ready' for section in sections.values()), sections
    assert sections['workforce']['employee_total'] == 3
    assert sections['workforce']['employee_active'] == 1
    assert sections['workforce']['staff_total'] == 2
    assert sections['workforce']['staff_active'] == 1
    assert sections['deployment']['today_shifts'] == 2
    assert sections['deployment']['upcoming_shifts'] == 1
    assert len(sections['deployment']['rosters']) == 3
    attendance = sections['attendance']
    assert {key: attendance[key] for key in ('recorded','present','absent','checked_in','awaiting_review',
        'scheduled_shifts','rostered_records','unrecorded_shifts')} == dict(recorded=2,present=1,absent=1,
        checked_in=1,awaiting_review=1,scheduled_shifts=2,rostered_records=1,unrecorded_shifts=1)
    billing = sections['billing']
    assert billing['issued_count'] == 2
    assert billing['issued_amount'] == '354.00'
    assert billing['unpaid_invoice_face_value'] == '472.00'
    assert billing['output_gst'] == '54.00'
    assert billing['eligible_itc'] == '4.00'
    assert billing['net_gst_estimate'] == '50.00'
    assert billing['collections'] is None and billing['outstanding_amount'] is None
    assert len(billing['recent_invoices']) == 3
    compliance = sections['compliance']
    assert compliance['pending_corporate'] == 3
    assert compliance['overdue_corporate'] == compliance['due30_corporate'] == 1
    assert compliance['expired_documents'] == compliance['expiring_documents'] == 1
    assert len(compliance['reminders']) == 4
    assert compliance['reminders'][0]['status'] == 'EXPIRED'


def test_dashboard_grant_never_grants_source_access_or_bypasses_role(postgres_workflow):
    http, sessions, engine, *_ = postgres_workflow
    with sessions() as db:
        password = db.query(User).first().hashed_password
        account = User(login_id='TEST-ACCOUNTS',email='accounts@example.test',full_name='Accounts',
                       role=UserRole.ACCOUNTS,is_active=True,is_superuser=False,hashed_password=password)
        db.add(account); db.flush(); uid = account.id
        # Unsupported explicit grants must not bypass the source module's role gate.
        for key, allowed in (('rosters.view',True),('attendance.view',True),('finance.view',False)):
            db.execute(text("insert into user_permissions(user_id,permission_key,allowed) values(:id,:key,:allowed)"),
                       {'id': uid, 'key': key, 'allowed': allowed})
        db.commit()
    headers = login(http, 'TEST-ACCOUNTS')
    queries = []
    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        queries.append(statement.lower())
    event.listen(engine, 'before_cursor_execute', capture)
    try:
        sections = get_dashboard(http, headers)['sections']
    finally:
        event.remove(engine, 'before_cursor_execute', capture)
    for forbidden_source in ('from employees', 'from attendance', 'from shift_rosters', 'from gst_itc_ledger', 'from md_'):
        assert not any(forbidden_source in query for query in queries), forbidden_source
    for name in ('workforce', 'deployment', 'attendance'):
        assert sections[name]['status'] == 'restricted'
        assert set(sections[name]) == {'status','message'}
    assert sections['billing']['status'] == 'ready'
    assert sections['billing']['eligible_itc'] is None
    assert sections['compliance']['expired_documents'] is None
    assert not sections['compliance']['access']['documents']
    with sessions() as db:
        db.execute(text("insert into user_permissions(user_id,permission_key,allowed) values(:id,'employees.view',true)"), {'id': uid})
        db.commit()
    partial = get_dashboard(http, headers)['sections']['workforce']
    assert partial['status'] == 'ready'
    assert partial['employee_total'] == 0 and partial['staff_total'] is None
    assert partial['access'] == {'employees': True, 'staff': False}
    with sessions() as db:
        db.execute(text("insert into user_permissions(user_id,permission_key,allowed) values(:id,'dashboard.view',false)"), {'id': uid})
        db.commit()
    assert http.get(BASE, headers=headers).status_code == 403
    with sessions() as db:
        account = db.get(User, uid); account.role = UserRole.HR
        db.execute(text("update user_permissions set allowed=true where user_id=:id and permission_key='dashboard.view'"), {'id': uid})
        db.commit()
    assert http.get(BASE, headers=headers).status_code == 403


def test_source_error_does_not_become_zero_or_abort_other_sections(postgres_workflow, caplog):
    http, sessions, *_ = postgres_workflow
    with sessions() as db:
        db.execute(text('alter table invoices rename to unavailable_dashboard_invoices'))
        db.commit()
    sections = get_dashboard(http, login(http))['sections']
    assert sections['billing']['status'] == 'error'
    assert set(sections['billing']) == {'status','message'}
    assert all(sections[name]['status'] == 'ready' for name in ('workforce','deployment','attendance','compliance'))
    assert 'Dashboard section unavailable: billing' in caplog.text
    assert 'unavailable_dashboard_invoices' not in caplog.text


def test_management_overview_uses_own_gate_and_never_grants_source_access(postgres_workflow):
    http, sessions, engine, *_ = postgres_workflow
    with sessions() as db:
        password = db.query(User).first().hashed_password
        account = User(login_id='TEST-MANAGEMENT',email='management@example.test',full_name='Management',
                       role=UserRole.OWNER,is_active=True,is_superuser=False,hashed_password=password)
        db.add(account); db.flush(); uid = account.id
        for module in ('dashboard','employees','staff','sites','rosters','attendance','billing','finance','compliance'):
            db.execute(text("insert into user_permissions(user_id,permission_key,allowed) values(:id,:key,false)"),
                       {'id': uid, 'key': module+'.view'})
        db.commit()
    headers = login(http, 'TEST-MANAGEMENT')
    assert http.get('/api/v1/owner/executive-summary').status_code == 401
    assert http.get(BASE, headers=headers).status_code == 403
    queries = []
    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        queries.append(statement.lower())
    event.listen(engine, 'before_cursor_execute', capture)
    try:
        response = http.get('/api/v1/owner/executive-summary', headers=headers)
    finally:
        event.remove(engine, 'before_cursor_execute', capture)
    assert response.status_code == 200, response.text
    result = response.json()
    assert all(section['status'] == 'restricted' for section in result['sections'].values())
    assert 'kpis' not in result and 'p_and_l' not in result
    for forbidden_source in ('from employees', 'from attendance', 'from shift_rosters', 'from invoices',
                             'from gst_itc_ledger', 'from salary_slips', 'from md_'):
        assert not any(forbidden_source in query for query in queries), forbidden_source
    with sessions() as db:
        db.execute(text("insert into user_permissions(user_id,permission_key,allowed) values(:id,'owner.view',false)"), {'id': uid})
        db.commit()
    assert http.get('/api/v1/owner/executive-summary', headers=headers).status_code == 403
