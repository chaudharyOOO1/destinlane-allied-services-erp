"""Accounting is restricted to a single server-configured MD identity, not a role label."""
import csv
import io
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import get_current_active_user
from app.core.config import settings
from app.core.database import get_db
from app.core.business_time import business_date
from app.models.company import CompanySettings
from app.models.md_accounting import AccountingSetup, LedgerAccount, JournalEntry, JournalLine, BankStatementLine, AccountingAudit
from app.schemas.md_accounting import SetupInput, PeriodInput, AccountInput, AccountUpdate, JournalInput, JournalUpdate, Version, ReversalInput, StatementInput, StatementBatch, MatchInput, ReconciliationInput, GSTInput
from app.services import md_accounting as books

router=APIRouter()


def require_md(user=Depends(get_current_active_user)):
    if not settings.MD_ACCOUNTING_USER_ID or user.id!=settings.MD_ACCOUNTING_USER_ID or user.role.value not in {'OWNER','SUPER_ADMIN'}:
        raise HTTPException(403,'This accounting workspace is restricted to the designated MD login.')
    return user


def audit(db,user,action,reference='',details=None):
    db.add(AccountingAudit(actor_id=user.id,action=action,reference=str(reference),details=jsonable_encoder(details or {})))


def commit(db):
    try:db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Accounting record conflicts with an existing record. Reopen and verify before retrying.') from None


def setup_response(row):
    return {key:getattr(row,key) for key in ['books_start_date','financial_year_start_month','closed_through','opening_confirmed','opening_reason','version']}


def account_response(row):
    return {key:getattr(row,key) for key in ['id','code','name','section','group_name','is_bank','bank_details','is_active','version']}


def locked_entry(db,entry_id,version):
    row=db.query(JournalEntry).filter_by(id=entry_id).with_for_update().first()
    if not row:raise HTTPException(404,'Voucher not found.')
    if row.version!=version:raise HTTPException(409,'Voucher changed. Reopen before continuing.')
    return row


def put_lines(db,row,data):
    ids={line.account_id for line in data.lines}
    accounts=db.query(LedgerAccount).filter(LedgerAccount.id.in_(ids)).all()
    if len(accounts)!=len(ids) or any(not account.is_active for account in accounts):raise HTTPException(422,'Choose existing active ledger accounts.')
    for key in ['entry_date','kind','narration','party','reference']:setattr(row,key,getattr(data,key))
    for line in db.query(JournalLine).filter_by(entry_id=row.id).all():db.delete(line)
    db.flush()
    for line in data.lines:db.add(JournalLine(entry_id=row.id,**line.model_dump()))
    db.flush()


@router.get('/setup')
def read_setup(db:Session=Depends(get_db),user=Depends(require_md)):
    row=books.setup(db)
    company=db.get(CompanySettings,1)
    return {**setup_response(row),'company_name':(company.profile if company else {}).get('legal_name','DestinLane Allied Services'),
            'basis':'ACCRUAL_DOUBLE_ENTRY','currency':'INR','sections':books.SECTIONS,
            'notice':'Management books. Opening balances, classifications, statutory schedules and tax treatment require accountant review.'}


@router.put('/setup')
def update_setup(data:SetupInput,db:Session=Depends(get_db),user=Depends(require_md)):
    row=books.setup(db,True)
    if data.version!=row.version:raise HTTPException(409,'Accounting setup changed. Reload it.')
    if data.books_start_date>business_date():raise HTTPException(422,'Books start date cannot be in the future.')
    used=db.query(JournalEntry.id).filter_by(status='POSTED').first() or db.query(BankStatementLine.id).first()
    if used and (row.books_start_date!=data.books_start_date or row.financial_year_start_month!=data.financial_year_start_month):
        raise HTTPException(409,'Books dates/year policy are locked after posting or importing statements.')
    if row.opening_confirmed and not data.confirm_opening:raise HTTPException(409,'Opening confirmation cannot be silently removed. Use adjusting vouchers.')
    if data.confirm_opening and len(data.opening_reason)<10:raise HTTPException(422,'Explain the reconciled opening balances, or explicitly confirm genuine zero opening balances.')
    row.books_start_date=data.books_start_date;row.financial_year_start_month=data.financial_year_start_month
    row.opening_confirmed=data.confirm_opening;row.opening_reason=data.opening_reason;row.version+=1
    audit(db,user,'SETUP',details=data.model_dump(exclude={'version'}));db.flush();response=setup_response(row);commit(db);return response


@router.post('/period')
def close_period(data:PeriodInput,db:Session=Depends(get_db),user=Depends(require_md)):
    row=books.setup(db,True)
    if data.version!=row.version:raise HTTPException(409,'Accounting setup changed. Reload it.')
    if data.through and not row.books_start_date<=data.through<=business_date():raise HTTPException(422,'Invalid period closing date.')
    if data.through and db.query(JournalEntry.id).filter(JournalEntry.status=='DRAFT',JournalEntry.entry_date<=data.through).first():
        raise HTTPException(409,'Post or move pending drafts before closing this period.')
    previous=row.closed_through;row.closed_through=data.through;row.version+=1
    audit(db,user,'PERIOD_LOCK',details={'previous':previous,'through':data.through,'reason':data.reason});db.flush();response=setup_response(row);commit(db);return response


@router.get('/accounts')
def accounts(db:Session=Depends(get_db),user=Depends(require_md)):
    return [account_response(row) for row in db.query(LedgerAccount).order_by(LedgerAccount.code)]


@router.post('/accounts',status_code=201)
def create_account(data:AccountInput,db:Session=Depends(get_db),user=Depends(require_md)):
    books.setup(db,True)
    row=LedgerAccount(**data.model_dump());db.add(row)
    try:db.flush()
    except IntegrityError:db.rollback();raise HTTPException(409,'Account code already exists.') from None
    audit(db,user,'ACCOUNT_CREATE',row.code,{'name':row.name,'section':row.section});response=account_response(row);commit(db);return response


@router.put('/accounts/{account_id}')
def update_account(account_id:int,data:AccountUpdate,db:Session=Depends(get_db),user=Depends(require_md)):
    books.setup(db,True);row=db.get(LedgerAccount,account_id)
    if not row:raise HTTPException(404,'Account not found.')
    if data.version!=row.version:raise HTTPException(409,'Account changed. Reload it.')
    used=db.query(JournalLine.id).filter_by(account_id=account_id).first() or db.query(BankStatementLine.id).filter_by(account_id=account_id).first()
    if used and any(getattr(row,key)!=getattr(data,key) for key in ['code','name','section','group_name','is_bank']):
        raise HTTPException(409,'Used account codes/names/classifications are retained. Create a new account and an adjusting voucher if needed.')
    for key,value in data.model_dump(exclude={'version'}).items():setattr(row,key,value)
    row.version+=1;audit(db,user,'ACCOUNT_UPDATE',row.code,{'changed_fields':list(data.model_dump(exclude={'version'}))});db.flush()
    response=account_response(row);commit(db);return response


@router.get('/journals')
def journals(status:str='',limit:int=Query(200,ge=1,le=500),db:Session=Depends(get_db),user=Depends(require_md)):
    query=db.query(JournalEntry)
    if status:
        if status not in {'DRAFT','POSTED'}:raise HTTPException(422,'Invalid voucher status.')
        query=query.filter_by(status=status)
    return [books.entry_response(db,row) for row in query.order_by(JournalEntry.entry_date.desc(),JournalEntry.id.desc()).limit(limit)]


@router.post('/journals',status_code=201)
def create_journal(data:JournalInput,db:Session=Depends(get_db),user=Depends(require_md)):
    configuration=books.setup(db,True);books.validate_date(configuration,data.entry_date,future=True)
    row=JournalEntry(created_by=user.id,status='DRAFT',version=1,**data.model_dump(exclude={'lines'}));db.add(row);db.flush()
    put_lines(db,row,data);audit(db,user,'VOUCHER_CREATE',row.id,{'kind':row.kind,'date':row.entry_date})
    response=books.entry_response(db,row);commit(db);return response


@router.get('/journals/{entry_id}')
def get_journal(entry_id:int,db:Session=Depends(get_db),user=Depends(require_md)):
    row=db.get(JournalEntry,entry_id)
    if not row:raise HTTPException(404,'Voucher not found.')
    return books.entry_response(db,row)


@router.put('/journals/{entry_id}')
def update_journal(entry_id:int,data:JournalUpdate,db:Session=Depends(get_db),user=Depends(require_md)):
    configuration=books.setup(db,True);row=locked_entry(db,entry_id,data.version)
    if row.status!='DRAFT':raise HTTPException(409,'Posted vouchers are immutable. Create a reversal.')
    books.validate_date(configuration,row.entry_date,future=True);books.validate_date(configuration,data.entry_date,future=True)
    put_lines(db,row,data);row.version+=1;audit(db,user,'VOUCHER_UPDATE',row.id,data.model_dump(exclude={'version'}));db.flush()
    response=books.entry_response(db,row);commit(db);return response


@router.post('/journals/{entry_id}/post')
def post_journal(entry_id:int,data:Version,db:Session=Depends(get_db),user=Depends(require_md)):
    configuration=books.setup(db,True);row=locked_entry(db,entry_id,data.version)
    if row.status!='DRAFT':raise HTTPException(409,'Voucher is already posted.')
    books.validate_post(db,row,configuration)
    row.status='POSTED';row.posted_by=user.id;row.posted_at=datetime.now(timezone.utc);row.version+=1
    audit(db,user,'VOUCHER_POST',row.id,books.entry_response(db,row));db.flush()
    response=books.entry_response(db,row);commit(db);return response


@router.post('/journals/{entry_id}/reverse',status_code=201)
def reverse_journal(entry_id:int,data:ReversalInput,db:Session=Depends(get_db),user=Depends(require_md)):
    configuration=books.setup(db,True);original=locked_entry(db,entry_id,data.version)
    if original.status!='POSTED' or original.reversal_of or db.query(JournalEntry.id).filter_by(reversal_of=entry_id).first():
        raise HTTPException(409,'Only an original posted voucher without an existing reversal can be reversed.')
    if data.entry_date<original.entry_date:raise HTTPException(422,'Reversal date cannot precede the original voucher.')
    books.validate_date(configuration,data.entry_date)
    row=JournalEntry(entry_date=data.entry_date,kind='REVERSAL',narration=data.reason,party=original.party,reference=f'Reversal MDJ{original.id:06d}',status='DRAFT',version=1,created_by=user.id,reversal_of=original.id)
    db.add(row);db.flush()
    for line in db.query(JournalLine).filter_by(entry_id=original.id):
        db.add(JournalLine(entry_id=row.id,account_id=line.account_id,debit=line.credit,credit=line.debit,description=data.reason))
    db.flush();books.validate_post(db,row,configuration)
    row.status='POSTED';row.posted_by=user.id;row.posted_at=datetime.now(timezone.utc);row.version=2
    audit(db,user,'VOUCHER_REVERSE',original.id,{'reversal_id':row.id,'reason':data.reason});db.flush()
    response=books.entry_response(db,row);commit(db);return response


@router.get('/reports')
def reports(as_of:date|None=None,from_date:date|None=None,db:Session=Depends(get_db),user=Depends(require_md)):
    return books.financial_reports(db,as_of or business_date(),from_date)


@router.get('/ledger/{account_id}')
def get_ledger(account_id:int,from_date:date,to_date:date,db:Session=Depends(get_db),user=Depends(require_md)):
    return books.ledger(db,account_id,from_date,to_date)


@router.get('/reports/export')
def export_reports(as_of:date|None=None,from_date:date|None=None,db:Session=Depends(get_db),user=Depends(require_md)):
    report=books.financial_reports(db,as_of or business_date(),from_date)
    output=io.StringIO();writer=csv.writer(output)
    writer.writerow(['Management trial balance — posted books only',str(report['as_of'])])
    writer.writerow(['Code','Account','Section','Debit movement','Credit movement','Debit balance','Credit balance'])
    def safe(value):
        value=str(value)
        return "'"+value if value.lstrip().startswith(('=','+','-','@','\t','\r')) else value
    for row in report['trial_balance']:
        writer.writerow([safe(row[key]) for key in ['code','name','section','debit_movement','credit_movement','debit_balance','credit_balance']])
    writer.writerow([]);writer.writerow(['Profit and loss',str(report['from_date']),str(report['as_of'])])
    writer.writerow(['Type','Account','Group','Amount'])
    for kind in ['income','expenses']:
        for row in report['profit_and_loss'][kind]:writer.writerow([kind,safe(row['name']),safe(row['group']),row['amount']])
    writer.writerow(['Net profit',report['profit_and_loss']['net_profit']])
    writer.writerow([]);writer.writerow(['Balance sheet',str(report['as_of'])])
    writer.writerow(['Classification','Account','Group','Amount'])
    for section,items in report['balance_sheet']['sections'].items():
        if section in {'REVENUE','EXPENSE'}:continue
        for row in items:writer.writerow([section,safe(row['name']),safe(row['group']),row['amount']])
    for key in ['assets','liabilities','recorded_equity','current_fy_earnings','prior_unclosed_earnings','total_equity','difference']:
        writer.writerow([key,report['balance_sheet'][key]])
    writer.writerow([])
    for warning in report['warnings']:writer.writerow([warning])
    audit(db,user,'REPORT_EXPORT',str(report['as_of']));commit(db)
    return Response(output.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="md-financial-reports.csv"'})


def import_rows(db,user,data):
    configuration=books.setup(db,True);account=db.get(LedgerAccount,data.account_id)
    if not account or not account.is_bank or not account.is_active:raise HTTPException(422,'Choose an active bank ledger.')
    seen=set();inserted=0;skipped=0
    for item in data.rows:
        if item.statement_id in seen:raise HTTPException(422,'Duplicate statement IDs in this batch.')
        seen.add(item.statement_id)
        if not configuration.books_start_date<=item.entry_date<=business_date():raise HTTPException(422,'Statement dates must fall within the books and no later than today.')
        existing=db.query(BankStatementLine).filter_by(account_id=account.id,statement_id=item.statement_id).first()
        if existing:
            if any(getattr(existing,key)!=getattr(item,key) for key in ['entry_date','reference','description','debit','credit']):
                raise HTTPException(409,'A statement ID already exists with different data. Verify the import; no rows were committed.')
            skipped+=1;continue
        db.add(BankStatementLine(account_id=account.id,imported_by=user.id,**item.model_dump()));inserted+=1
    audit(db,user,'BANK_IMPORT',account.code,{'inserted':inserted,'skipped':skipped});commit(db)
    return {'inserted':inserted,'skipped':skipped,'notice':'Import does not post bookkeeping entries. Match each bank transaction to a posted voucher.'}


@router.post('/bank/statements',status_code=201)
def import_statement(data:StatementBatch,db:Session=Depends(get_db),user=Depends(require_md)):
    return import_rows(db,user,data)


@router.get('/bank/template')
def bank_template(user=Depends(require_md)):
    return Response('statement_id,date,reference,description,debit,credit\n',media_type='text/csv',headers={'Content-Disposition':'attachment; filename="bank-import-template.csv"'})


@router.post('/bank/import',status_code=201)
async def import_csv(account_id:int=Form(...),file:UploadFile=File(...),db:Session=Depends(get_db),user=Depends(require_md)):
    content=await file.read(2*1024*1024+1)
    if len(content)>2*1024*1024:raise HTTPException(413,'Bank CSV limit is 2 MiB / 5000 rows.')
    try:
        reader=csv.DictReader(io.StringIO(content.decode('utf-8-sig')))
        required={'statement_id','date','debit','credit'};allowed=required|{'reference','description'}
        if not reader.fieldnames or not required.issubset(reader.fieldnames) or set(reader.fieldnames)-allowed:
            raise HTTPException(422,'Use the bank CSV template: statement_id,date,reference,description,debit,credit.')
        rows=[]
        for number,item in enumerate(reader,start=2):
            if number>5001:raise HTTPException(413,'Bank CSV limit is 5000 rows.')
            if None in item or any(value is None for value in item.values()):raise HTTPException(422,f'Invalid CSV columns at row {number}.')
            try:
                rows.append(StatementInput(statement_id=item['statement_id'],entry_date=item['date'],reference=item.get('reference',''),description=item.get('description',''),debit=item['debit'] or '0',credit=item['credit'] or '0'))
            except ValidationError as exc:raise HTTPException(422,f'Invalid bank CSV row {number}: {exc.errors()[0]["msg"]}') from None
        data=StatementBatch(account_id=account_id,rows=rows)
    except (UnicodeDecodeError,csv.Error,ValidationError):raise HTTPException(422,'Use a nonempty UTF-8 CSV in the supplied template format.') from None
    return import_rows(db,user,data)


@router.get('/bank/statements')
def bank_rows(account_id:int,unmatched:bool=False,db:Session=Depends(get_db),user=Depends(require_md)):
    query=db.query(BankStatementLine).filter_by(account_id=account_id)
    if unmatched:query=query.filter(BankStatementLine.matched_line_id.is_(None))
    rows=query.order_by(BankStatementLine.entry_date.desc(),BankStatementLine.id.desc()).limit(501).all()
    return {'has_more':len(rows)>500,'rows':[{key:getattr(row,key) for key in ['id','statement_id','entry_date','reference','description','debit','credit','matched_line_id']} for row in rows[:500]]}


@router.post('/bank/statements/{statement_id}/match')
def match_statement(statement_id:int,data:MatchInput,db:Session=Depends(get_db),user=Depends(require_md)):
    books.setup(db,True);row=db.get(BankStatementLine,statement_id);line=db.get(JournalLine,data.journal_line_id)
    if not row or not line:raise HTTPException(404,'Statement or voucher line not found.')
    entry=db.get(JournalEntry,line.entry_id)
    if row.matched_line_id==line.id:return {'matched':True,'journal_line_id':line.id}
    if row.matched_line_id or db.query(BankStatementLine.id).filter_by(matched_line_id=line.id).first():raise HTTPException(409,'Statement/voucher line is already matched.')
    if entry.status!='POSTED' or entry.kind=='OPENING' or line.account_id!=row.account_id or line.debit!=row.credit or line.credit!=row.debit:
        raise HTTPException(422,'Match the same bank ledger, opposite bank/book sides, and exact amount to a posted non-opening voucher.')
    row.matched_line_id=line.id;row.matched_by=user.id;row.matched_at=datetime.now(timezone.utc)
    audit(db,user,'BANK_MATCH',row.id,{'journal_line_id':line.id});commit(db);return {'matched':True,'journal_line_id':line.id}


@router.post('/bank/statements/{statement_id}/unmatch')
def unmatch_statement(statement_id:int,payload:dict,db:Session=Depends(get_db),user=Depends(require_md)):
    books.setup(db,True)
    if set(payload)!={'reason'} or not isinstance(payload['reason'],str) or not 10<=len(payload['reason'].strip())<=1000:raise HTTPException(422,'Provide a 10–1000 character unmatch reason.')
    row=db.get(BankStatementLine,statement_id)
    if not row:raise HTTPException(404,'Statement line not found.')
    previous=row.matched_line_id;row.matched_line_id=None;row.matched_by=None;row.matched_at=None
    audit(db,user,'BANK_UNMATCH',row.id,{'previous_line_id':previous,'reason':payload['reason']});commit(db);return {'matched':False}


@router.post('/bank/reconciliation')
def bank_reconciliation(data:ReconciliationInput,db:Session=Depends(get_db),user=Depends(require_md)):
    books.setup(db,True);result=books.reconcile(db,data.account_id,data.as_of,data.statement_balance)
    audit(db,user,'BANK_RECONCILIATION',data.reference,result);commit(db);return result


@router.post('/gst/calculate')
def calculate_gst(data:GSTInput,user=Depends(require_md)):
    base=data.taxable_amount
    if data.supply=='INTRA_STATE':
        cgst=(base*data.rate/Decimal('200')).quantize(Decimal('.01'),rounding=ROUND_HALF_UP);sgst=cgst;igst=Decimal('0')
    else:
        cgst=sgst=Decimal('0');igst=(base*data.rate/Decimal('100')).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
    return {'taxable_amount':books.money(base),'rate':str(data.rate),'cgst':books.money(cgst),'sgst':books.money(sgst),'igst':books.money(igst),
            'tax':books.money(cgst+sgst+igst),'total':books.money(base+cgst+sgst+igst),
            'notice':'Arithmetic only. Confirm the applicable rate, place of supply, reverse charge and ITC eligibility; this does not post a voucher or file a return.'}


@router.get('/audit')
def audit_history(limit:int=Query(200,ge=1,le=500),db:Session=Depends(get_db),user=Depends(require_md)):
    return [{key:getattr(row,key) for key in ['id','actor_id','action','reference','details','created_at']} for row in db.query(AccountingAudit).order_by(AccountingAudit.id.desc()).limit(limit)]


@router.get('/ledger/{account_id}/export')
def export_ledger(account_id:int,from_date:date,to_date:date,db:Session=Depends(get_db),user=Depends(require_md)):
    ledger=books.ledger(db,account_id,from_date,to_date)
    output=io.StringIO();writer=csv.writer(output)
    writer.writerow(['Ledger',ledger['code'],ledger['name'],'Debit positive / credit negative'])
    writer.writerow(['Opening balance',ledger['opening_balance']])
    keys=['date','voucher','party','reference','narration','description','debit','credit','balance']
    writer.writerow(keys)
    for row in ledger['entries']:
        values=[]
        for key in keys:
            value=str(row[key]);values.append("'"+value if value.lstrip().startswith(('=','+','-','@','\t','\r')) else value)
        writer.writerow(values)
    writer.writerow(['Closing balance',ledger['closing_balance']])
    audit(db,user,'LEDGER_EXPORT',account_id,{'from_date':from_date,'to_date':to_date});commit(db)
    return Response(output.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="md-ledger.csv"'})
