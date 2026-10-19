"""Everyday actions must preserve MD isolation and accounting classification."""
from datetime import timedelta
import pytest
from test_authentication import client
from test_md_accounting import md_client, confirm, BASE
from app.core.config import settings
from app.models.md_accounting import JournalEntry, LedgerAccount


def payload(accounts, day, **updates):
    return {'transaction_type':'MONEY_OUT','entry_date':str(day),'bank_account_id':accounts['1010'],
            'counter_account_id':accounts['5100'],'category':'EXPENSE','amount':'40.15',
            'party':'Taxi vendor','purpose':'Visit client site','reference':'BANK-REF',**updates}


def test_preview_is_read_only_and_client_cannot_supply_accounting_lines(md_client):
    http,sessions,headers,accounts,_,day=md_client
    data=payload(accounts,day)
    response=http.post(BASE+'/transactions/preview',headers=headers,json=data)
    assert response.status_code==200,response.text
    result=response.json()
    assert result['summary']['amount']=='40.15'
    assert result['journal']['kind']=='PAYMENT'
    assert result['journal']['lines'][0]['account_id']==accounts['5100']
    assert result['journal']['lines'][0]['debit']=='40.15'
    assert result['journal']['lines'][1]['credit']=='40.15'
    with sessions() as db:assert db.query(JournalEntry).count()==0
    assert http.post(BASE+'/transactions',headers=headers,json={**data,'lines':[]}).status_code==422
    draft=http.post(BASE+'/transactions',headers=headers,json=data)
    assert draft.status_code==201,draft.text
    row=draft.json();assert row['status']=='DRAFT'
    assert http.get(BASE+'/transactions/dashboard',headers=headers).json()['profit_and_loss']['expense']=='0.00'
    assert http.post(f"{BASE}/journals/{row['id']}/post",headers=headers,json={'version':row['version']}).status_code==409
    confirm(http,headers)
    assert http.post(f"{BASE}/journals/{row['id']}/post",headers=headers,json={'version':row['version']}).status_code==200
    assert http.post(f"{BASE}/journals/{row['id']}/post",headers=headers,json={'version':row['version']}).status_code==409
    report=http.get(BASE+'/transactions/dashboard',headers=headers).json()
    assert report['profit_and_loss']['expense']=='40.15'
    assert report['bank_cash_total']=='-40.15'


def test_receipts_settlements_and_transfers_do_not_invent_profit(md_client):
    http,sessions,headers,accounts,_,day=md_client
    with sessions() as db:
        cash=LedgerAccount(code='1000',name='Cash',section='CURRENT_ASSET',group_name='Cash',is_bank=False,bank_details={},is_active=True,version=1)
        db.add(cash);db.commit();cash_id=cash.id
    confirm(http,headers)
    def record(**updates):
        response=http.post(BASE+'/transactions',headers=headers,json=payload(accounts,day,**updates));assert response.status_code==201,response.text
        row=response.json();posted=http.post(f"{BASE}/journals/{row['id']}/post",headers=headers,json={'version':row['version']});assert posted.status_code==200,posted.text
        return posted.json()
    # Collection reduces a previously recorded receivable, never books new revenue.
    record(transaction_type='MONEY_IN',category='COLLECTION',counter_account_id=accounts['1100'],amount='100')
    record(transaction_type='MONEY_IN',category='BORROWING',counter_account_id=accounts['2103'],amount='200')
    record(category='SETTLEMENT',counter_account_id=accounts['2103'],amount='50')
    transfer=record(transaction_type='TRANSFER',category='TRANSFER',counter_account_id=cash_id,party='',amount='25')
    assert transfer['kind']=='CONTRA'
    report=http.get(BASE+'/transactions/dashboard',headers=headers).json()
    assert report['profit_and_loss']['net_profit']=='0.00'
    assert report['bank_cash_total']=='250.00'
    assert {row['name']:row['amount'] for row in report['bank_balances']}=={'Cash':'25.00','Current account':'225.00'}
    record(transaction_type='MONEY_IN',category='INCOME',counter_account_id=accounts['4000'],amount='12.34')
    assert http.get(BASE+'/transactions/dashboard',headers=headers).json()['profit_and_loss']['revenue']=='12.34'
    choices=http.get(BASE+'/transactions/options',headers=headers).json()
    assert {row['name']:row['is_bank'] for row in choices['banks']}=={'Cash':False,'Current account':True}


@pytest.mark.parametrize('updates',[
    {'category':'INCOME'}, {'counter_account_id':-1}, {'counter_account_id':999999},
    {'counter_account_id':None}, {'party':' '}, {'amount':'0'}, {'amount':'1.001'},
    {'transaction_type':'TRANSFER','category':'TRANSFER'},
    {'transaction_type':'TRANSFER','category':'TRANSFER','counter_account_id':'BANK_SELF'},
    {'entry_date':'FUTURE'}, {'category':'COLLECTION'},
])
def test_invalid_business_actions_rejected(md_client,updates):
    http,_,headers,accounts,_,day=md_client
    updates=dict(updates)
    if updates.get('counter_account_id')=='BANK_SELF':updates['counter_account_id']=accounts['1010']
    if updates.get('entry_date')=='FUTURE':updates['entry_date']=str(day+timedelta(days=1))
    response=http.post(BASE+'/transactions',headers=headers,json=payload(accounts,day,**updates))
    assert response.status_code==422,response.text


def test_everyday_routes_share_exact_md_boundary(md_client,monkeypatch):
    http,_,headers,accounts,_,day=md_client
    for path in ['/transactions/options','/transactions/dashboard']:
        assert http.get(BASE+path).status_code==401
    monkeypatch.setattr(settings,'MD_ACCOUNTING_USER_ID',999999)
    for path in ['/transactions/options','/transactions/dashboard']:
        assert http.get(BASE+path,headers=headers).status_code==403
    for path in ['/transactions','/transactions/preview']:
        assert http.post(BASE+path,headers=headers,json=payload(accounts,day)).status_code==403
