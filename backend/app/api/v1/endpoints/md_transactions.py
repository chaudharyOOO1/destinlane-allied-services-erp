"""Simple MD workflow over the existing identity, posting and ledger controls."""
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.business_time import business_date
from app.models.md_accounting import LedgerAccount
from app.schemas.md_transactions import MoneyRecord
from app.services import md_accounting as books, md_transactions as business
from app.api.v1.endpoints.md_accounting import require_md, create_journal

router=APIRouter()


@router.get('/transactions/options')
def transaction_options(db:Session=Depends(get_db),user=Depends(require_md)):
    return business.choices(db)


@router.post('/transactions/preview')
def preview_transaction(data:MoneyRecord,db:Session=Depends(get_db),user=Depends(require_md)):
    journal,summary=business.build_journal(db,data)
    return {'summary':summary,'journal':journal.model_dump(mode='json')}


@router.post('/transactions',status_code=201)
def create_transaction(data:MoneyRecord,db:Session=Depends(get_db),user=Depends(require_md)):
    # Serialize validation with account/setup changes; existing creation retains
    # the confirmed response and creates only a draft. Posting is a separate step.
    books.setup(db,True)
    journal,_=business.build_journal(db,data)
    return create_journal(journal,db,user)


@router.get('/transactions/dashboard')
def transaction_dashboard(as_of:date|None=None,from_date:date|None=None,db:Session=Depends(get_db),user=Depends(require_md)):
    report=books.financial_reports(db,as_of or business_date(),from_date)
    balances={row['account_id']:books.amount(row['debit_balance'])-books.amount(row['credit_balance']) for row in report['trial_balance']}
    accounts=db.query(LedgerAccount).order_by(LedgerAccount.code).all()
    bank_balances=[{'id':a.id,'name':a.name,'amount':books.money(balances.get(a.id,0))} for a in accounts if business.cash_account(a)]
    return {**report,'bank_balances':bank_balances,'bank_cash_total':books.money(sum((books.amount(row['amount']) for row in bank_balances),books.ZERO))}
