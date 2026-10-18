/** Real browser, simulated API: operator journey plus failed-refresh recovery. */
import {test} from 'node:test';
import assert from 'node:assert/strict';
import puppeteer from 'puppeteer-core';
import {mkdtemp, writeFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';

const origin = process.env.FRONTEND_TEST_URL || 'http://127.0.0.1:5173';
assert.ok(['localhost','127.0.0.1','[::1]'].includes(new URL(origin).hostname), 'Only local frontends may be tested');
const actors = {staff:{id:1,role:'OPERATIONS',full_name:'Test coordinator'}, hr:{id:2,role:'HR',full_name:'Test HR'}, accounts:{id:3,role:'ACCOUNTS',full_name:'Test accounts'}};

test('create, attach, submit, HR rejection/resubmission, approval and Accounts reimbursement', {timeout:60000}, async () => {
  const browser=await puppeteer.launch({executablePath:process.env.BROWSER_EXECUTABLE_PATH || '/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
  const directory=await mkdtemp(join(tmpdir(),'travel-browser-'));
  try {
    const page=await browser.newPage();
    const jsErrors=[]; page.on('pageerror',error=>jsErrors.push(error.message));
    await page.setRequestInterception(true);
    let claim=null, creates=0, payments=0, listFailure=false;
    let actorName='staff';
    const day=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Kolkata'}).format(new Date());
    page.on('request',async request=>{
      const url=new URL(request.url());
      if (!url.pathname.startsWith('/api/v1/')) return request.continue();
      const path=url.pathname.replace('/api/v1','');
      const actor=actors[actorName];
      let data={},status=200;
      if (request.method()==='OPTIONS') return request.respond({status:204,headers:{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*','Access-Control-Allow-Methods':'GET, POST, PUT, OPTIONS'}});
      if (path==='/auth/me') data={...actor,must_change_password:false};
      else if (path===`/users/${actor.id}/permissions`) data={permissions:{'travel_expenses.view':true,'travel_expenses.create':true,'travel_expenses.edit':true,'travel_expenses.approve':actorName==='hr','travel_expenses.pay':actorName==='accounts'},module_roles:{travel_expenses:['OPERATIONS','HR','ACCOUNTS']}};
      else if (path==='/erp/company/profile') data={display_name:'Test company'};
      else if (path.endsWith('/options')) data={branches:[]};
      else if (path==='/erp/travel-expenses' && request.method()==='GET') {
        if (listFailure) {status=503;data={detail:'Simulated list outage'};listFailure=false;}
        else data={claims:claim && (url.searchParams.get('scope')==='all' || claim.requester_id===actor.id) ? [claim] : [],has_more:false};
      } else if (path==='/erp/travel-expenses' && request.method()==='POST') {
        creates++;
        claim={...JSON.parse(request.postData()),id:1,claim_code:'TRAVEL000001',requester_id:1,requester_name:actors.staff.full_name,total_amount:'250.25',currency:'INR',status:'DRAFT',version:1,receipts:[],history:[]};
        listFailure=true; data=claim;
      } else if (path.endsWith('/receipts') && request.method()==='POST') {
        claim={...claim,version:claim.version+1,receipts:[{id:1,filename:'ticket.pdf',mime_type:'application/pdf',size_bytes:25}]};data=claim;
      } else if (request.method()==='POST' || request.method()==='PUT') {
        const body=JSON.parse(request.postData());
        assert.equal(body.version,claim.version,'Every write must use the latest acknowledged version');
        if (path.endsWith('/submit')) claim={...claim,status:'SUBMITTED',version:claim.version+1};
        else if (path.endsWith('/decision')) claim={...claim,status:body.decision==='APPROVE'?'APPROVED':'REJECTED',review_remarks:body.remarks,version:claim.version+1};
        else if (path.endsWith('/pay')) {payments++;claim={...claim,status:'PAID',payment_reference:body.payment_reference,payment_date:body.payment_date,version:claim.version+1};}
        else claim={...claim,...body,status:'DRAFT',version:claim.version+1};
        data=claim;
      } else if (path==='/erp/travel-expenses/1') data=claim;
      else {status=404;data={detail:'Unexpected test route '+path};}
      return request.respond({status,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*'},body:JSON.stringify(data)});
    });
    await page.evaluateOnNewDocument(()=>localStorage.setItem('destinlane_access_token','test-only-token'));
    async function click(text) {
      await page.waitForFunction(text=>[...document.querySelectorAll('button')].some(button=>button.textContent.trim()===text && !button.disabled),{},text);
      await page.evaluate(text=>[...document.querySelectorAll('button')].find(button=>button.textContent.trim()===text).click(),text);
    }
    async function settled(text) {await page.waitForFunction(text=>document.body.innerText.includes(text),{},text);}
    async function switchActor(name) {
      actorName=name;
      await page.goto(`${origin}/travel-expenses`);
      await settled('No travel claims found.');
      await page.select('[aria-label="Claim scope"]','all');
      await click('Open');
      await page.waitForSelector('[aria-label="Travel claim details"]');
    }
    await page.goto(`${origin}/travel-expenses`);
    await click('New travel claim');
    for (const [label,value] of [['Business purpose','Client site inspection'],['From','Delhi'],['To','Noida'],['Description 1','Return train ticket'],['Amount 1','250.25']]) await page.type(`[aria-label="${label}"]`,value);
    await click('Save travel draft');
    await settled('Changes saved, but the directory could not refresh.');
    assert.equal(creates,1);
    assert.match(await page.$eval('[aria-label="Travel claim details"]',el=>el.innerText),/TRAVEL000001 · DRAFT/);
    const receiptPath=join(directory,'ticket.pdf');await writeFile(receiptPath,'%PDF-1.4 test-only receipt');
    await (await page.$('[aria-label="Receipt file"]')).uploadFile(receiptPath);
    await click('Attach receipt');await settled('Receipt attached.');
    await click('Submit travel claim');await settled('TRAVEL000001 · SUBMITTED');
    assert.equal(await page.$$eval('button',buttons=>buttons.filter(button=>button.textContent==='Approve claim').length),0);
    await switchActor('hr');
    await page.waitForSelector('[aria-label="Review remarks"]:enabled');
    await page.type('[aria-label="Review remarks"]','Please clarify the visit purpose');
    await click('Reject with remarks');await settled('TRAVEL000001 · REJECTED');
    actorName='staff';await page.goto(`${origin}/travel-expenses`);await click('Open');
    await page.waitForSelector('[aria-label="Business purpose"]:enabled');
    await page.type('[aria-label="Business purpose"]',' and staffing verification');
    await click('Save travel draft');await settled('Travel draft saved.');
    await click('Submit travel claim');await settled('TRAVEL000001 · SUBMITTED');
    await switchActor('hr');await click('Approve claim');await settled('TRAVEL000001 · APPROVED');
    await switchActor('accounts');
    await page.waitForSelector('[aria-label="Payment reference"]:enabled');
    await page.type('[aria-label="Payment reference"]','BANK-TEST-001');
    await click('Record reimbursement');await settled('Reimbursement recorded and posted to Accounts.');
    assert.equal(payments,1);assert.equal(creates,1);
    assert.match(await page.$eval('[aria-label="Travel claim details"]',el=>el.innerText),/BANK-TEST-001/);
    await page.setViewport({width:390,height:844});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'Mobile page must not overflow horizontally');
    assert.deepEqual(jsErrors,[]);
    assert.equal(claim.payment_date,day);
  } finally {await browser.close();await rm(directory,{recursive:true,force:true});}
});
