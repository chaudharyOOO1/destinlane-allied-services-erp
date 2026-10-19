/** MD operator journey with simulated APIs; exact accounting is tested server-side. */
import {test} from 'node:test';
import assert from 'node:assert/strict';
import puppeteer from 'puppeteer-core';
import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
const origin=process.env.FRONTEND_TEST_URL||'http://127.0.0.1:5173';
assert.ok(['localhost','127.0.0.1','[::1]'].includes(new URL(origin).hostname));

test('simple payments, receipts, transfers, bank review and safe recovery',{timeout:60000},async()=>{
 const browser=await puppeteer.launch({executablePath:process.env.BROWSER_EXECUTABLE_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 const temp=await mkdtemp(join(tmpdir(),'md-books-'));
 try{
  const page=await browser.newPage();const errors=[];page.on('pageerror',error=>errors.push(error.message));
  const day=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Kolkata'}).format(new Date());
  let setup={books_start_date:day,financial_year_start_month:4,closed_through:null,opening_confirmed:true,opening_reason:'',version:1,company_name:'Test Company',sections:['CURRENT_ASSET','NON_CURRENT_ASSET','EQUITY','CURRENT_LIABILITY','NON_CURRENT_LIABILITY','REVENUE','EXPENSE']};
  const accounts=[{id:1,code:'1010',name:'Current account',section:'CURRENT_ASSET',is_bank:true},{id:2,code:'5100',name:'Travel expense',section:'EXPENSE',is_bank:false},{id:3,code:'3000',name:'Capital',section:'EQUITY',is_bank:false},{id:4,code:'4000',name:'Revenue',section:'REVENUE',is_bank:false},{id:5,code:'1000',name:'Cash',section:'CURRENT_ASSET',is_bank:false}].map(row=>({...row,group_name:row.name,bank_details:{},is_active:true,version:1}));
  let journals=[],statement=[],failedRefresh=false,failMatch=false,creates=0;const businessRequests=[];
  function journalDetails(body,id){return {...body,id,voucher:`MDJ${String(id).padStart(6,'0')}`,status:'DRAFT',version:1,debit_total:String(body.lines.reduce((sum,line)=>sum+Number(line.debit),0)),credit_total:String(body.lines.reduce((sum,line)=>sum+Number(line.credit),0)),difference:'0.00',reversal_of:null,reversed_by:null,lines:body.lines.map((line,index)=>({...line,id:id*10+index,account_code:accounts.find(account=>account.id===line.account_id).code,account_name:accounts.find(account=>account.id===line.account_id).name}))};}
  function ledger(id){let balance=0;const entries=[];for(const journal of journals.filter(row=>row.status==='POSTED'))for(const line of journal.lines.filter(row=>row.account_id===id)){balance+=Number(line.debit)-Number(line.credit);entries.push({line_id:line.id,entry_id:journal.id,voucher:journal.voucher,date:journal.entry_date,party:journal.party,reference:journal.reference,narration:journal.narration,description:line.description,debit:line.debit,credit:line.credit,balance:String(balance)});}return {account_id:id,name:accounts.find(a=>a.id===id).name,opening_balance:'0',closing_balance:String(balance),entries};}
  function reports(){const bank=ledger(1).closing_balance;const expense=ledger(2).closing_balance;const equity=-Number(ledger(3).closing_balance);return {as_of:day,from_date:day,opening_confirmed:setup.opening_confirmed,trial_balance:[],trial_debits:'1000',trial_credits:'1000',trial_difference:'0',profit_and_loss:{income:[],expenses:[{name:'Travel expense',group:'Other expenses',amount:expense}],revenue:'0',expense,net_profit:String(-Number(expense))},balance_sheet:{sections:{CURRENT_ASSET:[{name:'Current account',group:'Cash and cash equivalents',amount:bank}],EQUITY:[{name:'Capital',group:'Capital',amount:String(equity)}]},assets:bank,liabilities:'0',current_fy_earnings:String(-Number(expense)),prior_unclosed_earnings:'0',total_equity:String(equity-Number(expense)),difference:'0'},warnings:[]};}
  await page.setRequestInterception(true);
  page.on('request',request=>{
   const url=new URL(request.url());if(!url.pathname.startsWith('/api/v1/'))return request.continue();
   const path=url.pathname.replace('/api/v1','');let data={},status=200;
   if(request.method()==='OPTIONS')return request.respond({status:204,headers:{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*','Access-Control-Allow-Methods':'GET, POST, PUT, OPTIONS'}});
   if(path==='/auth/me')data={id:1,role:'OWNER',full_name:'Test MD',must_change_password:false};
   else if(path==='/users/1/permissions')data={permissions:Object.fromEntries(['view','create','edit','approve','export'].map(action=>[`md_accounting.${action}`,true])),module_roles:{md_accounting:['OWNER']}};
   else if(path==='/erp/company/profile')data={display_name:'Test Company'};
   else if(path.endsWith('/setup')){if(request.method()==='PUT'){const body=JSON.parse(request.postData());setup={...setup,...body,opening_confirmed:body.confirm_opening,version:setup.version+1};}data=setup;}
   else if(path.endsWith('/transactions/options'))data={banks:[accounts[0],{id:5,name:'Cash',is_bank:false}],categories:{MONEY_OUT:[{id:'EXPENSE',name:'Business expense',accounts:[accounts[1]]}],MONEY_IN:[{id:'COLLECTION',name:'Collect a client balance',accounts:[accounts[3]]}]}};
   else if(path.endsWith('/transactions/preview')||path.endsWith('/transactions')){
    const input=JSON.parse(request.postData());businessRequests.push(input);assert.equal(input.lines,undefined);assert.equal(input.status,undefined);
    const incoming=input.transaction_type==='MONEY_IN';
    if(path.endsWith('/preview'))data={summary:{amount:input.amount,category:input.category,from_account:'Current account',to_account:input.party||'Cash',record_as:input.category,purpose:input.purpose}};
    else {creates++;const generated={kind:incoming?'RECEIPT':input.transaction_type==='TRANSFER'?'CONTRA':'PAYMENT',entry_date:input.entry_date,narration:input.purpose,party:input.party,reference:input.reference,lines:[{account_id:incoming?input.bank_account_id:input.counter_account_id,debit:input.amount,credit:'0'},{account_id:incoming?input.counter_account_id:input.bank_account_id,debit:'0',credit:input.amount}]};data=journalDetails(generated,journals.length+1);journals.push(data);if(creates===1)failedRefresh=true;}
   }
   else if(path.endsWith('/transactions/dashboard'))data={...reports(),bank_balances:[{id:1,name:'Current account',amount:ledger(1).closing_balance}],bank_cash_total:ledger(1).closing_balance};
   else if(path.endsWith('/accounts'))data=accounts;
   else if(path.endsWith('/journals')&&request.method()==='POST'){const body=JSON.parse(request.postData());data=journalDetails(body,journals.length+1);journals.push(data);}
   else if(path.endsWith('/journals')){if(failedRefresh){failedRefresh=false;status=503;data={detail:'Simulated refresh failure'};}else data=[...journals].reverse();}
   else if(/\/journals\/\d+\/post$/.test(path)){const row=journals.find(row=>row.id===Number(path.split('/').at(-2)));assert.equal(JSON.parse(request.postData()).version,row.version);Object.assign(row,{status:'POSTED',version:row.version+1});data=row;}
   else if(/\/journals\/\d+$/.test(path))data=journals.find(row=>row.id===Number(path.split('/').at(-1)));
   else if(path.endsWith('/reports'))data=reports();
   else if(path.includes('/ledger/'))data=ledger(Number(path.split('/').at(-1)));
   else if(path.endsWith('/bank/import')){statement=[{id:1,statement_id:'BANK-1',entry_date:day,reference:'BANK-REF',description:'Taxi to site',debit:'40',credit:'0',matched_line_id:null}];data={inserted:1,skipped:0};}
   else if(path.endsWith('/bank/statements'))data={rows:statement,has_more:false};
   else if(path.endsWith('/match')){if(failMatch){status=503;data={detail:'Simulated match failure'};}else {statement[0].matched_line_id=JSON.parse(request.postData()).journal_line_id;data={matched:true};}}
   else if(path.endsWith('/bank/reconciliation'))data={status:'RECONCILED',difference:'0',unbooked_count:0,book_balance:'960',statement_balance:'960',outstanding_payments:'0',deposits_in_transit:'0',unbooked_statement_debits:'0',unbooked_statement_credits:'0',expected_statement_balance:'960',formula:'Book balance + outstanding payments - deposits in transit + unbooked credits - unbooked debits'};
   else {status=404;data={detail:'Unexpected test route '+path};}
   return request.respond({status,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*'},body:JSON.stringify(data)});
  });
  await page.evaluateOnNewDocument(()=>localStorage.setItem('destinlane_access_token','test-only-token'));
  async function click(text){await page.waitForFunction(text=>[...document.querySelectorAll('button')].some(button=>(button.textContent.trim()===text||button.getAttribute('aria-label')===text)&&!button.disabled),{},text);await page.evaluate(text=>[...document.querySelectorAll('button')].find(button=>(button.textContent.trim()===text||button.getAttribute('aria-label')===text)).click(),text);}
  async function text(value){await page.waitForFunction(value=>document.body.innerText.includes(value),{},value);}
  async function type(label,value){await page.waitForSelector(`[aria-label="${label}"]:enabled`);await page.type(`[aria-label="${label}"]`,value);}
  await page.goto(`${origin}/md-accounting`);await page.waitForSelector('[aria-label="Money account"]');
  assert.equal(await page.$('[aria-label="Voucher debit 1"]'),null,'Everyday workflow must hide accounting lines');
  async function details({type='MONEY_OUT',amount='40',party='Taxi vendor',description='Taxi to client site'}={}){
   if(type!=='MONEY_OUT')await click(type==='TRANSFER'?'Transfer':'Money In');
   await page.select('[aria-label="Money account"]','1');
   if(type==='TRANSFER')await page.select('[aria-label="Transfer destination"]','5');
   else {await page.select('[aria-label="Money purpose type"]',type==='MONEY_OUT'?'EXPENSE':'COLLECTION');await page.select('[aria-label="Money category"]',type==='MONEY_OUT'?'2':'4');await typeField('Money party',party);}
   await typeField('Money amount',amount);await typeField('Money description',description);await typeField('Money reference','BANK-REF');
  }
  async function typeField(label,value){await type(label,value);}
  await details();await click('Review record');await text('Nothing has been saved yet.');assert.equal(creates,0);
  await click('Save draft');await text('Your draft is saved, but the list could not refresh.');assert.equal(creates,1);
  await click('Adjust draft in Advanced');await page.waitForSelector('[aria-label="Voucher debit 1"]');
  await click('Post balanced voucher');await text('MDJ000001 · POSTED');
  await click('Back to everyday records');await text('Saved in the books. Use Reports or Bank Review to see the result.');
  assert.equal(await page.$('[aria-label="Voucher debit 1"]'),null);

  assert.equal(await page.$$eval('button',buttons=>buttons.filter(b=>b.textContent==='Confirm and record').length),0);
  await click('Reports');await text('Your business at a glance');await text('Balance sheet');
  await page.setViewport({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
  await click('Record Money');await click('Record another transaction');
  await details({type:'MONEY_IN',amount:'100',party:'Client',description:'Collect invoice balance'});await click('Review record');await click('Save draft');await click('Confirm and record');await text('MDJ000002 is recorded in the books.');
  await click('Record another transaction');await details({type:'TRANSFER',amount:'10',description:'Move to company cash'});await click('Review record');await click('Save draft');await click('Confirm and record');await text('MDJ000003 is recorded in the books.');
  assert.equal(journals[2].kind,'CONTRA');assert.equal(journals[2].party,'');
  await click('Bank Review');await page.select('[aria-label="Review bank account"]','1');
  assert.equal(await page.$$eval('[aria-label="Review bank account"] option',items=>items.some(i=>i.textContent==='Cash')),false);
  const filename=join(temp,'bank.csv');await writeFile(filename,`statement_id,date,reference,description,debit,credit\nBANK-1,${day},BANK-REF,Taxi to site,40,0\n`);
  await (await page.$('[aria-label="Review bank CSV"]')).uploadFile(filename);await click('Upload statement');await text('Taxi to site');
  await page.select('[aria-label="Match bank row BANK-1"]','11');await click('Match BANK-1');await text('Matched to a recorded transaction');
  await type('Review closing balance','50');await type('Review statement reference','BANK-CLOSING');await click('Check bank balance');await text('Bank reconciled');
  // Simulate a second unbooked row; recording succeeds even when matching fails.
  statement=[{id:2,statement_id:'BANK-2',entry_date:day,reference:'NEW-REF',description:'Second taxi visit',debit:'40',credit:'0',matched_line_id:null}];failMatch=true;
  await click('Refresh bank rows');await text('Record BANK-2');await click('Record BANK-2');
  assert.equal(await page.$eval('[aria-label="Money amount"]',el=>el.value),'40');
  await page.select('[aria-label="Money purpose type"]','EXPENSE');await page.select('[aria-label="Money category"]','2');await type('Money party','Second vendor');
  await click('Review record');await click('Save draft');await click('Confirm and record');await text('The transaction is recorded, but bank matching was not confirmed.');
  assert.equal(creates,4);assert.equal(journals.filter(row=>row.status==='POSTED').length,4);
  assert.equal(await page.$$eval('button',buttons=>buttons.filter(b=>b.textContent==='Save draft'||b.textContent==='Confirm and record').length),0);
  assert.equal(businessRequests.filter(input=>input.transaction_type==='MONEY_IN')[0].category,'COLLECTION');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'Everyday money form must fit mobile');
  assert.deepEqual(errors,[]);
 }finally{await browser.close();await rm(temp,{recursive:true,force:true});}
});
