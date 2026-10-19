"""Convert everyday business actions into validated double-entry drafts."""
from fastapi import HTTPException
from app.models.md_accounting import LedgerAccount
from app.schemas.md_accounting import JournalInput
from app.services import md_accounting as books

CATEGORIES = {
    'MONEY_OUT': [
        ('EXPENSE','Business expense',{'EXPENSE'}),
        ('ASSET','Buy equipment or another asset',{'CURRENT_ASSET','NON_CURRENT_ASSET'}),
        ('SETTLEMENT','Pay a supplier, loan or other amount owed',{'CURRENT_LIABILITY','NON_CURRENT_LIABILITY'}),
    ],
    'MONEY_IN': [
        ('COLLECTION','Collect a client balance',{'CURRENT_ASSET'}),
        ('INCOME','New business income',{'REVENUE'}),
        ('BORROWING','Receive a loan or advance',{'CURRENT_LIABILITY','NON_CURRENT_LIABILITY'}),
        ('CAPITAL','Capital introduced',{'EQUITY'}),
    ],
}


def cash_account(account):
    return account.is_bank or account.code=='1000'


def eligible(account, sections, category):
    return account.is_active and not cash_account(account) and account.section in sections and not(category=='CAPITAL' and account.code=='3100')


def choices(db):
    accounts=db.query(LedgerAccount).filter_by(is_active=True).order_by(LedgerAccount.code).all()
    return {'banks':[{'id':a.id,'name':a.name,'is_bank':a.is_bank} for a in accounts if cash_account(a)],
            'categories':{kind:[{'id':key,'name':label,'accounts':[{'id':a.id,'name':a.name} for a in accounts if eligible(a,sections,key)]}
                                for key,label,sections in categories] for kind,categories in CATEGORIES.items()}}


def build_journal(db, data):
    settings=books.setup(db)
    books.validate_date(settings,data.entry_date)
    bank=db.get(LedgerAccount,data.bank_account_id)
    counter=db.get(LedgerAccount,data.counter_account_id)
    if not bank or not bank.is_active or not cash_account(bank):
        raise HTTPException(422,'Choose an active bank or cash account.')
    if not counter or not counter.is_active or bank.id==counter.id:
        raise HTTPException(422,'Choose a different active destination or category account.')
    if data.transaction_type=='TRANSFER':
        if data.category!='TRANSFER' or not cash_account(counter):
            raise HTTPException(422,'A transfer must go to another bank or cash account.')
        kind='CONTRA';description='Transfer between company accounts'
    else:
        category=next((item for item in CATEGORIES[data.transaction_type] if item[0]==data.category),None)
        if not category or not eligible(counter,category[2],data.category):
            raise HTTPException(422,'Choose an account that matches this business purpose. Use Advanced Accounting for other entries or tax splits.')
        if not data.party:
            raise HTTPException(422,'Enter who received or paid the money.')
        kind='PAYMENT' if data.transaction_type=='MONEY_OUT' else 'RECEIPT';description=category[1]
    debit_id,credit_id=(bank.id,counter.id) if kind=='RECEIPT' else (counter.id,bank.id)
    journal=JournalInput(entry_date=data.entry_date,kind=kind,narration=data.purpose,party=data.party,reference=data.reference,
                         lines=[{'account_id':debit_id,'debit':data.amount,'credit':0},
                                {'account_id':credit_id,'debit':0,'credit':data.amount}])
    return journal,{'transaction_type':data.transaction_type,'amount':books.money(data.amount),'date':data.entry_date,
                    'from_account':bank.name if kind!='RECEIPT' else data.party,
                    'to_account':counter.name if kind=='CONTRA' else (bank.name if kind=='RECEIPT' else data.party),
                    'category':description,'record_as':counter.name,'purpose':data.purpose,'reference':data.reference,
                    'opening_confirmed':settings.opening_confirmed}
