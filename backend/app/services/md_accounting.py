"""Exact-decimal ledger calculations. Operational dashboard totals are not books."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException
from sqlalchemy import func
from app.core.business_time import business_date
from app.models.md_accounting import AccountingSetup, LedgerAccount, JournalEntry, JournalLine, BankStatementLine

ZERO = Decimal('0.00')
SECTIONS = ['NON_CURRENT_ASSET','CURRENT_ASSET','EQUITY','NON_CURRENT_LIABILITY','CURRENT_LIABILITY','REVENUE','EXPENSE']


def amount(value):
    return Decimal(value or 0).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def money(value):
    return format(amount(value), '.2f')


def setup(db, lock=False):
    query = db.query(AccountingSetup).filter_by(id=1)
    row = (query.with_for_update() if lock else query).first()
    if not row:
        raise HTTPException(503, 'Accounting migration/setup is not installed.')
    return row


def validate_date(settings, day, future=False):
    if day < settings.books_start_date:
        raise HTTPException(422, 'Date is before the books start date.')
    if not future and day > business_date():
        raise HTTPException(422, 'Posting date cannot be in the future.')
    if settings.closed_through and day <= settings.closed_through:
        raise HTTPException(409, 'This accounting period is closed. Reopen it with an audit reason before editing/posting.')


def entry_response(db, row):
    lines = db.query(JournalLine,LedgerAccount).join(LedgerAccount,LedgerAccount.id==JournalLine.account_id).filter(JournalLine.entry_id==row.id).order_by(JournalLine.id).all()
    debit = sum((line.debit for line,_ in lines), ZERO)
    credit = sum((line.credit for line,_ in lines), ZERO)
    reverse = db.query(JournalEntry.id).filter_by(reversal_of=row.id).first()
    return {'id':row.id,'voucher':f'MDJ{row.id:06d}','entry_date':row.entry_date,'kind':row.kind,'narration':row.narration,
            'party':row.party,'reference':row.reference,'status':row.status,'version':row.version,'posted_at':row.posted_at,
            'created_by':row.created_by,'posted_by':row.posted_by,'reversal_of':row.reversal_of,'reversed_by':reverse.id if reverse else None,
            'debit_total':money(debit),'credit_total':money(credit),'difference':money(debit-credit),
            'lines':[{'id':line.id,'account_id':line.account_id,'account_code':account.code,'account_name':account.name,
                      'debit':money(line.debit),'credit':money(line.credit),'description':line.description} for line,account in lines]}


def validate_post(db, row, settings):
    validate_date(settings,row.entry_date)
    lines = db.query(JournalLine,LedgerAccount).join(LedgerAccount,LedgerAccount.id==JournalLine.account_id).filter(JournalLine.entry_id==row.id).all()
    debit = sum((line.debit for line,_ in lines), ZERO)
    credit = sum((line.credit for line,_ in lines), ZERO)
    if len(lines)<2 or debit<=0 or debit!=credit:
        raise HTTPException(422, 'Posting requires equal nonzero debits and credits.')
    if any(not account.is_active for _,account in lines):
        raise HTTPException(422, 'All voucher accounts must be active.')
    if row.kind=='OPENING':
        if settings.opening_confirmed or row.entry_date!=settings.books_start_date:
            raise HTTPException(409, 'Opening vouchers must use the books start date before opening confirmation.')
        if any(account.section in {'REVENUE','EXPENSE'} for _,account in lines):
            raise HTTPException(422, 'Opening vouchers use balance-sheet accounts; prior earnings belong in equity.')
    elif not settings.opening_confirmed and row.kind!='REVERSAL':
        raise HTTPException(409, 'Confirm opening balances before posting operating vouchers.')
    cash_lines = [(line,account) for line,account in lines if account.is_bank or account.code=='1000']
    if row.kind=='PAYMENT' and (not any(line.credit>0 for line,_ in cash_lines) or any(line.debit>0 for line,_ in cash_lines)):
        raise HTTPException(422, 'A payment must credit a bank/cash ledger. Use Contra for transfers.')
    if row.kind=='RECEIPT' and (not any(line.debit>0 for line,_ in cash_lines) or any(line.credit>0 for line,_ in cash_lines)):
        raise HTTPException(422, 'A receipt must debit a bank/cash ledger. Use Contra for transfers.')
    if row.kind=='CONTRA' and len(cash_lines)!=len(lines):
        raise HTTPException(422, 'Contra vouchers can use only bank/cash ledgers.')


def financial_reports(db, as_of, from_date=None):
    settings = setup(db)
    if not settings.books_start_date <= as_of <= business_date():
        raise HTTPException(422, 'Report date must be within the books and no later than today.')
    month = settings.financial_year_start_month
    fy_start = date(as_of.year-(as_of.month<month),month,1)
    start = from_date or max(fy_start,settings.books_start_date)
    if not settings.books_start_date <= start <= as_of:
        raise HTTPException(422, 'Report start date must be between the books start date and report date.')
    accounts = db.query(LedgerAccount).order_by(LedgerAccount.code).all()
    by_id = {account.id:account for account in accounts}
    sums = {account.id:[ZERO,ZERO,ZERO,ZERO] for account in accounts}
    rows = db.query(JournalLine,JournalEntry.entry_date).join(JournalEntry,JournalEntry.id==JournalLine.entry_id).filter(JournalEntry.status=='POSTED',JournalEntry.entry_date<=as_of).all()
    for line,day in rows:
        if line.account_id not in sums:
            account=db.get(LedgerAccount,line.account_id);accounts.append(account);by_id[account.id]=account;sums[account.id]=[ZERO,ZERO,ZERO,ZERO]
        values=sums[line.account_id]
        values[0]+=line.debit;values[1]+=line.credit
        if day>=start:values[2]+=line.debit;values[3]+=line.credit
    trial=[];balance={key:[] for key in SECTIONS};income=[];expenses=[];all_profit=ZERO;period_profit=ZERO
    for account in accounts:
        dr,cr,period_dr,period_cr=sums[account.id]; net=dr-cr
        trial.append({'account_id':account.id,'code':account.code,'name':account.name,'section':account.section,
                      'debit_movement':money(dr),'credit_movement':money(cr),'debit_balance':money(max(net,ZERO)),'credit_balance':money(max(-net,ZERO))})
        if account.section in {'REVENUE','EXPENSE'}:
            all_profit-=net
            value=(period_cr-period_dr) if account.section=='REVENUE' else (period_dr-period_cr)
            target=income if account.section=='REVENUE' else expenses
            target.append({'code':account.code,'name':account.name,'group':account.group_name,'amount':money(value)})
            period_profit += value if account.section=='REVENUE' else -value
        else:
            value=net if account.section.endswith('ASSET') else -net
            balance[account.section].append({'code':account.code,'name':account.name,'group':account.group_name,'amount':money(value)})
    total=lambda values:sum((Decimal(item['amount']) for item in values),ZERO)
    assets=total(balance['CURRENT_ASSET'])+total(balance['NON_CURRENT_ASSET'])
    liabilities=total(balance['CURRENT_LIABILITY'])+total(balance['NON_CURRENT_LIABILITY'])
    equity=total(balance['EQUITY'])+all_profit
    td=sum((Decimal(item['debit_balance']) for item in trial),ZERO);tc=sum((Decimal(item['credit_balance']) for item in trial),ZERO)
    # FY earnings are distinct from a user-selected P&L range.
    fy_profit=ZERO
    for line,day in rows:
        if day>=fy_start:
            account=by_id[line.account_id]
            if account.section in {'REVENUE','EXPENSE'}:fy_profit+=line.credit-line.debit
    warnings=['Management books only: statutory presentation, tax treatment and supporting schedules need accountant review.',
              'Operational invoices, payroll, expenses and receipts are not silently imported. Record/reconcile their vouchers; avoid duplicate recognition.',
              'Bank statement completeness and actual bank balances must be supplied and reconciled.']
    if not settings.opening_confirmed:warnings.insert(0,'Opening balances are not confirmed. Reports are provisional.')
    return {'as_of':as_of,'from_date':start,'currency':'INR','basis':'ACCRUAL_DOUBLE_ENTRY','opening_confirmed':settings.opening_confirmed,
            'trial_balance':trial,'trial_debits':money(td),'trial_credits':money(tc),'trial_difference':money(td-tc),
            'profit_and_loss':{'income':income,'expenses':expenses,'revenue':money(total(income)),'expense':money(total(expenses)),'net_profit':money(period_profit)},
            'balance_sheet':{'sections':balance,'assets':money(assets),'liabilities':money(liabilities),'recorded_equity':money(total(balance['EQUITY'])),
                             'current_fy_earnings':money(fy_profit),'prior_unclosed_earnings':money(all_profit-fy_profit),'total_equity':money(equity),
                             'liabilities_and_equity':money(liabilities+equity),'difference':money(assets-liabilities-equity)},
            'warnings':warnings}


def ledger(db, account_id, start, end):
    account=db.get(LedgerAccount,account_id)
    if not account:raise HTTPException(404,'Ledger account not found.')
    settings=setup(db)
    if not settings.books_start_date<=start<=end<=business_date():raise HTTPException(422,'Choose a valid ledger date range.')
    rows=db.query(JournalLine,JournalEntry).join(JournalEntry,JournalEntry.id==JournalLine.entry_id).filter(JournalLine.account_id==account_id,JournalEntry.status=='POSTED',JournalEntry.entry_date<=end).order_by(JournalEntry.entry_date,JournalEntry.id,JournalLine.id).all()
    running=sum((line.debit-line.credit for line,entry in rows if entry.entry_date<start),ZERO)
    opening=running;result=[]
    for line,entry in rows:
        if entry.entry_date<start:continue
        running+=line.debit-line.credit
        result.append({'line_id':line.id,'entry_id':entry.id,'voucher':f'MDJ{entry.id:06d}','date':entry.entry_date,
                       'party':entry.party,'reference':entry.reference,'narration':entry.narration,'description':line.description,
                       'debit':money(line.debit),'credit':money(line.credit),'balance':money(running)})
    return {'account_id':account.id,'code':account.code,'name':account.name,'from_date':start,'to_date':end,
            'opening_balance':money(opening),'closing_balance':money(running),'balance_convention':'Debit positive / credit negative','entries':result}


def reconcile(db, account_id, as_of, statement_balance):
    account=db.get(LedgerAccount,account_id)
    if not account or not account.is_bank:raise HTTPException(422,'Choose a bank ledger.')
    settings=setup(db)
    if not settings.books_start_date<=as_of<=business_date():raise HTTPException(422,'Invalid reconciliation date.')
    posted=db.query(JournalLine,JournalEntry).join(JournalEntry,JournalEntry.id==JournalLine.entry_id).filter(JournalLine.account_id==account_id,JournalEntry.status=='POSTED',JournalEntry.entry_date<=as_of).all()
    statements=db.query(BankStatementLine).filter(BankStatementLine.account_id==account_id,BankStatementLine.entry_date<=as_of).all()
    matched={row.matched_line_id for row in statements if row.matched_line_id}
    book=sum((line.debit-line.credit for line,_ in posted),ZERO)
    # Opening balances are carried balances, not uncleared transactions.
    outstanding_pay=sum((line.credit for line,entry in posted if line.id not in matched and entry.kind!='OPENING'),ZERO)
    outstanding_receipts=sum((line.debit for line,entry in posted if line.id not in matched and entry.kind!='OPENING'),ZERO)
    posted_ids={line.id for line,_ in posted}
    unbooked=[row for row in statements if row.matched_line_id not in posted_ids]
    unbooked_debits=sum((row.debit for row in unbooked),ZERO);unbooked_credits=sum((row.credit for row in unbooked),ZERO)
    expected=book+outstanding_pay-outstanding_receipts+unbooked_credits-unbooked_debits
    difference=amount(statement_balance)-expected
    return {'account_id':account.id,'account_name':account.name,'as_of':as_of,'book_balance':money(book),
            'statement_balance':money(statement_balance),'outstanding_payments':money(outstanding_pay),'deposits_in_transit':money(outstanding_receipts),
            'unbooked_statement_debits':money(unbooked_debits),'unbooked_statement_credits':money(unbooked_credits),'unbooked_count':len(unbooked),
            'expected_statement_balance':money(expected),'difference':money(difference),
            'status':'RECONCILED' if difference==0 and not unbooked and settings.opening_confirmed else 'REVIEW_REQUIRED',
            'formula':'Book balance + outstanding payments - deposits in transit + unbooked credits - unbooked debits'}
