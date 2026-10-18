"""MD identity boundary, exact books and bank reconciliation; no production data."""
from datetime import timedelta
from decimal import Decimal
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_authentication import client
from test_postgres_workflow import postgres_workflow
from app.core.config import settings
from app.core.business_time import business_date
from app.models.user import User
from app.models.enums import UserRole
from app.models.md_accounting import AccountingSetup, LedgerAccount, JournalEntry, JournalLine, BankStatementLine

BASE='/api/v1/erp/md-accounting'


@pytest.fixture
def md_client(client,monkeypatch):
    http,sessions=client
    monkeypatch.setattr(settings,'MD_ACCOUNTING_USER_ID',1)
    day=business_date();start=day-timedelta(days=10)
    with sessions() as db:
        db.execute(text("ATTACH DATABASE ':memory:' AS public"))
        db.execute(text('CREATE TABLE public.user_permissions(user_id INTEGER,permission_key TEXT,allowed BOOLEAN, UNIQUE(user_id,permission_key))'))
        db.add(AccountingSetup(id=1,books_start_date=start,financial_year_start_month=4,opening_confirmed=False,opening_reason='',version=1))
        for code,name,section,bank in [('1010','Current account','CURRENT_ASSET',True),('1100','Receivables','CURRENT_ASSET',False),('2103','GST payable','CURRENT_LIABILITY',False),('3000','Capital','EQUITY',False),('4000','Services','REVENUE',False),('5100','Travel','EXPENSE',False)]:
            db.add(LedgerAccount(code=code,name=name,section=section,group_name=name,is_bank=bank,bank_details={},is_active=True,version=1))
        db.commit();accounts={row.code:row.id for row in db.query(LedgerAccount)}
    token=http.post('/api/v1/auth/login',json={'login_id':'ADMIN-001','password':'test-password-before'}).json()['access_token']
    headers={'Authorization':'Bearer '+token}
    return http,sessions,headers,accounts,start,day


def voucher(http,headers,accounts,date,lines,kind='JOURNAL',post=True):
    body={'entry_date':str(date),'kind':kind,'narration':'Local accountant example','party':'Test party','reference':'TEST-REF','lines':[{'account_id':accounts[code],'debit':str(dr),'credit':str(cr)} for code,dr,cr in lines]}
    response=http.post(BASE+'/journals',headers=headers,json=body)
    assert response.status_code==201,response.text
    row=response.json()
    if post:
        response=http.post(f"{BASE}/journals/{row['id']}/post",headers=headers,json={'version':row['version']})
        assert response.status_code==200,response.text
        row=response.json()
    return row


def confirm(http,headers):
    setup=http.get(BASE+'/setup',headers=headers).json()
    response=http.put(BASE+'/setup',headers=headers,json={'version':setup['version'],'books_start_date':setup['books_start_date'],'financial_year_start_month':4,'confirm_opening':True,'opening_reason':'Opening balances reconciled against signed records'})
    assert response.status_code==200,response.text
    return response.json()


def test_designated_md_only_even_for_other_management_and_it(md_client,monkeypatch):
    http,sessions,headers,accounts,start,day=md_client
    assert http.get(BASE+'/setup',headers=headers).status_code==200
    assert http.get(BASE+'/setup').status_code==401
    for role in [UserRole.OWNER,UserRole.SUPER_ADMIN,UserRole.ACCOUNTS,UserRole.HR]:
        with sessions() as db:
            password=db.get(User,1).hashed_password
            user=User(login_id='TEST-'+role.value,email=role.value.lower()+'@example.invalid',full_name='Other user',role=role,is_active=True,is_superuser=role==UserRole.OWNER,hashed_password=password)
            db.add(user);db.commit();uid=user.id
            db.execute(text("insert into public.user_permissions values(:id,'md_accounting.view',true)"),{'id':uid});db.commit()
        token=http.post('/api/v1/auth/login',json={'login_id':'TEST-'+role.value,'password':'test-password-before'}).json()['access_token']
        other={'Authorization':'Bearer '+token}
        assert http.get(BASE+'/setup',headers=other).status_code==403
        assert http.post(BASE+'/journals',headers=other,json={}).status_code==403
        rights=http.get(f'/api/v1/users/{uid}/permissions',headers=other).json()['permissions']
        assert not rights['md_accounting.view']
    monkeypatch.setattr(settings,'MD_ACCOUNTING_USER_ID',None)
    assert http.get(BASE+'/setup',headers=headers).status_code==403


def test_double_entry_reports_accrual_gst_and_reversal(md_client):
    http,_,headers,accounts,start,day=md_client
    voucher(http,headers,accounts,start,[('1010',1000,0),('3000',0,1000)],'OPENING')
    confirm(http,headers)
    voucher(http,headers,accounts,day,[('1010',100,0),('4000',0,100)],'RECEIPT')
    payment=voucher(http,headers,accounts,day,[('5100',40,0),('1010',0,40)],'PAYMENT')
    voucher(http,headers,accounts,day,[('1100',1180,0),('4000',0,1000),('2103',0,180)])
    report=http.get(BASE+'/reports',headers=headers).json()
    assert report['trial_difference']=='0.00'
    assert report['profit_and_loss']['revenue']=='1100.00'
    assert report['profit_and_loss']['expense']=='40.00'
    assert report['profit_and_loss']['net_profit']=='1060.00'
    assert report['balance_sheet']['assets']=='2240.00'
    assert report['balance_sheet']['liabilities']=='180.00'
    assert report['balance_sheet']['total_equity']=='2060.00'
    assert report['balance_sheet']['difference']=='0.00'
    ledger=http.get(f"{BASE}/ledger/{accounts['1010']}",headers=headers,params={'from_date':str(start),'to_date':str(day)}).json()
    assert ledger['closing_balance']=='1060.00' and len(ledger['entries'])==3
    reversal=http.post(f"{BASE}/journals/{payment['id']}/reverse",headers=headers,json={'version':payment['version'],'entry_date':str(day),'reason':'Duplicate booking corrected by accountant'})
    assert reversal.status_code==201,reversal.text
    assert reversal.json()['reversal_of']==payment['id']
    assert http.get(BASE+'/reports',headers=headers).json()['profit_and_loss']['net_profit']=='1100.00'
    assert http.post(f"{BASE}/journals/{payment['id']}/reverse",headers=headers,json={'version':payment['version'],'entry_date':str(day),'reason':'Cannot reverse same original twice'}).status_code==409


def test_balancing_stale_versions_opening_and_period_locks(md_client):
    http,_,headers,accounts,start,day=md_client
    row=voucher(http,headers,accounts,day,[('5100',40,0),('1010',0,39)],post=False)
    assert http.post(f"{BASE}/journals/{row['id']}/post",headers=headers,json={'version':row['version']}).status_code==422
    valid=voucher(http,headers,accounts,day,[('5100',40,0),('1010',0,40)],post=False)
    assert http.post(f"{BASE}/journals/{valid['id']}/post",headers=headers,json={'version':1}).status_code==409
    setup=confirm(http,headers)
    assert http.post(f"{BASE}/journals/{valid['id']}/post",headers=headers,json={'version':99}).status_code==409
    assert http.post(f"{BASE}/journals/{valid['id']}/post",headers=headers,json={'version':1}).status_code==200
    assert http.post(BASE+'/period',headers=headers,json={'version':setup['version'],'through':str(day),'reason':'Month closing control check'}).status_code==409 # unbalanced draft remains
    lock=http.post(BASE+'/period',headers=headers,json={'version':setup['version'],'through':str(start),'reason':'Opening day reconciled and closed'})
    assert lock.status_code==200,lock.text
    blocked=http.post(BASE+'/journals',headers=headers,json={'entry_date':str(start),'narration':'Backdated attempt','lines':[{'account_id':accounts['1010'],'debit':'1','credit':'0'},{'account_id':accounts['3000'],'debit':'0','credit':'1'}]})
    assert blocked.status_code==409
    report=http.get(BASE+'/reports',headers=headers).json()
    assert report['profit_and_loss']['expense']=='40.00' # draft imbalance is excluded


def test_bank_import_idempotence_matching_and_reconciliation(md_client):
    http,_,headers,accounts,start,day=md_client
    voucher(http,headers,accounts,start,[('1010',1000,0),('3000',0,1000)],'OPENING');confirm(http,headers)
    receipt=voucher(http,headers,accounts,day,[('1010',100,0),('4000',0,100)],'RECEIPT')
    payment=voucher(http,headers,accounts,day,[('5100',40,0),('1010',0,40)],'PAYMENT')
    csv=f'statement_id,date,reference,description,debit,credit\nBANK1,{day},REF1,"Deposit, test",0,100\nBANK2,{day},REF2,Taxi,40,0\n'
    def upload(value):return http.post(BASE+'/bank/import',headers=headers,data={'account_id':accounts['1010']},files={'file':('bank.csv',value.encode(),'text/csv')})
    first=upload(csv);assert first.status_code==201,first.text
    assert first.json()['inserted']==2
    assert upload(csv).json()['skipped']==2
    assert upload(csv.replace('40,0','41,0')).status_code==409
    recon={'account_id':accounts['1010'],'as_of':str(day),'statement_balance':'1060','reference':'BANK-CLOSING'}
    result=http.post(BASE+'/bank/reconciliation',headers=headers,json=recon).json()
    assert result['difference']=='0.00' and result['unbooked_count']==2 and result['status']=='REVIEW_REQUIRED'
    rows=http.get(BASE+'/bank/statements',headers=headers,params={'account_id':accounts['1010']}).json()['rows']
    for statement,v in [(next(r for r in rows if r['statement_id']=='BANK1'),receipt),(next(r for r in rows if r['statement_id']=='BANK2'),payment)]:
        line=next(line for line in v['lines'] if line['account_id']==accounts['1010'])
        response=http.post(f"{BASE}/bank/statements/{statement['id']}/match",headers=headers,json={'journal_line_id':line['id']})
        assert response.status_code==200,response.text
    result=http.post(BASE+'/bank/reconciliation',headers=headers,json=recon).json()
    assert result['status']=='RECONCILED' and result['difference']=='0.00'
    assert http.post(BASE+'/bank/reconciliation',headers=headers,json={**recon,'statement_balance':'999'}).json()['status']=='REVIEW_REQUIRED'
    assert http.post(f"{BASE}/bank/statements/{rows[0]['id']}/unmatch",headers=headers,json={'reason':'short'}).status_code==422
    assert http.post(f"{BASE}/bank/statements/{rows[0]['id']}/unmatch",headers=headers,json={'reason':'Bank clearing match needs review'}).status_code==200


@pytest.mark.parametrize('supply,cgst,sgst,igst',[('INTRA_STATE','90.00','90.00','0.00'),('INTER_STATE','0.00','0.00','180.00')])
def test_gst_decimal_arithmetic_does_not_post(md_client,supply,cgst,sgst,igst):
    http,sessions,headers,_,_,_=md_client
    response=http.post(BASE+'/gst/calculate',headers=headers,json={'taxable_amount':'1000','rate':'18','supply':supply})
    assert response.status_code==200,response.text
    result=response.json();assert (result['cgst'],result['sgst'],result['igst'])==(cgst,sgst,igst)
    assert result['total']=='1180.00'
    with sessions() as db:assert db.query(JournalEntry).count()==0


def test_postgres_enforces_posted_immutability_and_balance(postgres_workflow,monkeypatch):
    http,sessions,engine,day,_,owner_id,*_=postgres_workflow
    monkeypatch.setattr(settings,'MD_ACCOUNTING_USER_ID',owner_id)
    token=http.post('/api/v1/auth/login',json={'login_id':'TEST-OWNER','password':'local-test-password'}).json()['access_token']
    headers={'Authorization':'Bearer '+token}
    setup=http.get(BASE+'/setup',headers=headers).json()
    with sessions() as db:accounts={row.code:row.id for row in db.query(LedgerAccount)}
    opening=voucher(http,headers,accounts,setup['books_start_date'],[('1010',1000,0),('3000',0,1000)],'OPENING')
    with pytest.raises(DBAPIError):
        with engine.begin() as connection:connection.execute(text('update md_journal_lines set debit=debit+1 where id=:id'),{'id':opening['lines'][0]['id']})
    with pytest.raises(DBAPIError):
        with engine.begin() as connection:connection.execute(text("update md_journal_entries set narration='tamper' where id=:id"),{'id':opening['id']})
    with pytest.raises(DBAPIError):
        with engine.begin() as connection:
            connection.execute(text("insert into md_journal_entries(entry_date,kind,narration,status,created_by) values(:date,'JOURNAL','Unbalanced direct insert','POSTED',:user)"),{'date':day,'user':owner_id})
    with engine.connect() as connection:
        for role in ['anon','authenticated']:
            for table in ['md_accounting_setup','md_ledger_accounts','md_journal_entries','md_journal_lines','md_bank_statement_lines','md_accounting_audit']:
                assert not connection.execute(text("select has_table_privilege(:role,:table,'select')"),{'role':role,'table':table}).scalar_one()


def test_prior_year_earnings_and_exports_are_not_confused_with_current_profit(md_client):
    http,_,headers,accounts,_,day=md_client
    fy_start=day.replace(year=day.year-(day.month<4),month=4,day=1)
    prior_start=fy_start.replace(year=fy_start.year-1)
    response=http.put(BASE+'/setup',headers=headers,json={'version':1,'books_start_date':str(prior_start),'financial_year_start_month':4,'confirm_opening':True,'opening_reason':'Genuine zero opening balances confirmed for test'})
    assert response.status_code==200,response.text
    voucher(http,headers,accounts,fy_start-timedelta(days=1),[('1010',100,0),('4000',0,100)],'RECEIPT')
    voucher(http,headers,accounts,day,[('1010',50,0),('4000',0,50)],'RECEIPT')
    report=http.get(BASE+'/reports',headers=headers).json()
    assert report['profit_and_loss']['net_profit']=='50.00'
    assert report['balance_sheet']['current_fy_earnings']=='50.00'
    assert report['balance_sheet']['prior_unclosed_earnings']=='100.00'
    assert report['balance_sheet']['assets']=='150.00' and report['balance_sheet']['difference']=='0.00'
    created=http.post(BASE+'/accounts',headers=headers,json={'code':'9000','name':'=SUM(1,2)','section':'EXPENSE','group_name':'Other expenses'})
    assert created.status_code==201,created.text
    exported=http.get(BASE+'/reports/export',headers=headers)
    assert exported.status_code==200 and "'=SUM" in exported.text
    assert 'Profit and loss' in exported.text and 'Balance sheet' in exported.text
    ledger=http.get(f"{BASE}/ledger/{accounts['1010']}/export",headers=headers,params={'from_date':str(prior_start),'to_date':str(day)})
    assert ledger.status_code==200 and 'Closing balance,150.00' in ledger.text
