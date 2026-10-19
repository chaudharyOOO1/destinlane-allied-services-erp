/** Professional overview and navigation: simulated API, no production login. */
import {test} from 'node:test';
import assert from 'node:assert/strict';
import puppeteer from 'puppeteer-core';
const origin=process.env.FRONTEND_TEST_URL||'http://127.0.0.1:5173';
assert.ok(['localhost','127.0.0.1','[::1]'].includes(new URL(origin).hostname));
const day=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Kolkata'}).format(new Date());
const makeSnapshot=()=>({as_of:day,generated_at:new Date().toISOString(),month:day.slice(0,7),month_label:'Current month',sections:{
 workforce:{status:'ready',employee_total:12,employee_active:9,staff_total:3,staff_active:2,access:{employees:true,staff:true}},
 deployment:{status:'ready',active_sites:4,today_shifts:3,upcoming_shifts:2,rosters:[{id:1,date:day,shift_type:'DAY',status:'SCHEDULED',site_name:'Test site',employee_name:'Fictional employee',employee_code:'DASE0070'}]},
 attendance:{status:'ready',recorded:2,present:1,absent:1,leave:0,checked_in:1,awaiting_review:1,scheduled_shifts:3,rostered_records:2,unrecorded_shifts:1},
 billing:{status:'ready',issued_amount:'1250.25',issued_count:1,unpaid_invoice_face_value:'1250.25',output_gst:'190.72',eligible_itc:'0.00',net_gst_estimate:'190.72',collections:null,outstanding_amount:null,collections_status:'unavailable',collection_note:'Receipt allocation is not available. Partial payments are not deducted.',tax_note:'Operational GST estimate; not a tax return.',access:{invoices:true,itc:true},recent_invoices:[{id:1,invoice_number:'TEST-INV-1',company_name:'Fictional client',issue_date:day,due_date:day,total_amount:'1250.25',status:'SENT',clearance_status:'PENDING'}]},
 compliance:{status:'ready',pending_corporate:1,overdue_corporate:1,due30_corporate:0,expiring_documents:0,expired_documents:0,reminders:[{id:1,type:'CORPORATE',title:'Test filing',detail:'Test period',due_date:day,status:'PENDING',overdue:true}],access:{corporate:true,documents:true}},
}});
const modules=['dashboard','employees','staff','rosters','sites','attendance','billing','finance','compliance','company','travel_expenses','md_accounting'];
async function fixture(run){
 const browser=await puppeteer.launch({executablePath:process.env.BROWSER_EXECUTABLE_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  const page=await browser.newPage();const errors=[];page.on('pageerror',error=>errors.push(error.message));
  const state={snapshot:makeSnapshot(),failure:false,authFailure:false,deferAuth:false,releaseAuth:null,pendingAuthResponses:[],permissions:modules,requests:[]};await page.setRequestInterception(true);
  page.on('request',request=>{
   const path=new URL(request.url()).pathname.replace('/api/v1','');if(!new URL(request.url()).pathname.startsWith('/api/v1/'))return request.continue();
   state.requests.push(path);let data={},status=200;
   if(request.method()==='OPTIONS')return request.respond({status:204,headers:{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*','Access-Control-Allow-Methods':'GET, POST, PUT, OPTIONS'}});
   if(path==='/auth/me'&&state.deferAuth){state.pendingAuthResponses.push(()=>request.respond({status:401,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'*'},body:JSON.stringify({detail:'Superseded session'})}));state.releaseAuth=()=>Promise.all(state.pendingAuthResponses.splice(0).map(respond=>respond()));return;}
   if(path==='/auth/login')data={access_token:'fresh-test-only-token',user:{id:1,role:'OWNER',full_name:'Test Management',must_change_password:false}};
   else if(path==='/auth/me'){if(state.authFailure){status=503;data={detail:'Temporary authentication outage'};}else data={id:1,role:'OWNER',full_name:'Test Management',must_change_password:false};}
   else if(path==='/users/1/permissions')data={permissions:Object.fromEntries(state.permissions.flatMap(module=>[['view',true],['create',true]].map(([action,value])=>[`${module}.${action}`,value]))),module_roles:Object.fromEntries(state.permissions.map(module=>[module,['OWNER']]))};
   else if(path==='/erp/company/profile')data={legal_name:'Fictional company',display_name:'DestinLane Test'};
   else if(path==='/erp/dashboard'||path==='/owner/executive-summary'){if(state.failure){status=503;data={detail:'Temporary overview outage'};}else data=state.snapshot;}
   else if(path==='/erp/internal-staff')data={staff:[],has_more:false};
   else if(path.endsWith('/options'))data={roles:[],branches:[],departments:[]};
   else {status=404;data={detail:'Unexpected test route '+path};}
   return request.respond({status,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*'},body:JSON.stringify(data)});
  });
  await page.evaluateOnNewDocument(()=>localStorage.setItem('destinlane_access_token','test-only-token'));
  const text=async value=>page.waitForFunction(value=>document.body.innerText.includes(value),{},value);
  const click=async value=>{await page.waitForFunction(value=>[...document.querySelectorAll('button')].some(b=>b.textContent.trim()===value&&!b.disabled),{},value);await page.evaluate(value=>[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===value).click(),value);};
  await run({page,state,text,click,errors});assert.deepEqual(errors,[]);
 }finally{await browser.close();}
}

test('overview uses real snapshot and permission-scoped working navigation',{timeout:45000},()=>fixture(async({page,state,text,click})=>{
 await page.setViewport({width:1440,height:1000});await page.goto(origin+'/erp');await text('Business overview');await text('Fictional employee');await text('TEST-INV-1');await text('Test Management');
 if(process.env.DASHBOARD_SCREENSHOTS)await page.screenshot({path:'/workspace/.onboarding/erp-overview-desktop.png',fullPage:true});
 const content=await page.$eval('main',el=>el.innerText);assert.match(content,/1,250\.25/);assert.match(content,/1 shift without attendance/);assert.match(content,/Receipt allocation is not available/);
 for(const dummy of ['+12%','98%','Across 3 Client Accounts','LIVE','Dispatch Guard'])assert.ok(!content.includes(dummy));
 assert.equal(await page.$$eval('[aria-label="Notifications"]',nodes=>nodes.length),0);
 assert.equal(await page.$$eval('a[href="/users"],button',nodes=>nodes.some(n=>n.textContent.trim()==='User Management')),false);
 await page.keyboard.down('Control');await page.keyboard.press('k');await page.keyboard.up('Control');
 await page.waitForSelector('[role="dialog"] input');await page.type('[role="dialog"] input','Staff');await page.keyboard.press('Enter');await page.waitForFunction(()=>location.pathname==='/staff');
 assert.ok(!state.requests.includes('/erp/summary'),'The old summary must not power the overview');
}));

test('zero records, partial failure and refresh failure remain distinct',{timeout:45000},()=>fixture(async({page,state,text,click})=>{
 state.snapshot.sections.attendance={...state.snapshot.sections.attendance,recorded:0,present:0,absent:0,checked_in:0,awaiting_review:0,scheduled_shifts:0,rostered_records:0,unrecorded_shifts:0};
 state.snapshot.sections.deployment={status:'error',message:'Deployment records could not load.'};
 state.snapshot.sections.workforce={status:'restricted',message:'No workforce access.'};
 await page.goto(origin+'/dashboard');await text('Business overview');await text('Deployment records could not load.');
 assert.equal(await page.$$eval('main a',nodes=>nodes.some(n=>n.textContent.includes('Active employees'))),false);
 assert.ok(!(await page.$eval('main',el=>el.innerText)).includes('98%'));
 state.failure=true;await click('Refresh overview');await text('Temporary overview outage');await text('The last successful snapshot is still shown below.');await text('TEST-INV-1');
 state.failure=false;state.snapshot.sections.deployment={status:'ready',active_sites:0,today_shifts:0,upcoming_shifts:0,rosters:[]};await click('Refresh overview');await text('No scheduled shifts for today or the next 7 days.');
}));

test('mobile layout and navigation stay usable with limited permissions',{timeout:45000},()=>fixture(async({page,state,text})=>{
 state.permissions=['dashboard','billing','company'];state.snapshot.sections.workforce={status:'restricted',message:'Restricted'};state.snapshot.sections.deployment={status:'restricted',message:'Restricted'};state.snapshot.sections.attendance={status:'restricted',message:'Restricted'};state.snapshot.sections.compliance={status:'restricted',message:'Restricted'};
 await page.setViewport({width:390,height:844});await page.goto(origin+'/erp');await text('Business overview');await text('TEST-INV-1');
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Overview must not overflow horizontally');
 if(process.env.DASHBOARD_SCREENSHOTS)await page.screenshot({path:'/workspace/.onboarding/erp-overview-mobile.png',fullPage:true});
 await page.click('[aria-label="Open navigation"]');await page.waitForSelector('[aria-modal="true"]');
 const nav=await page.$eval('[aria-modal="true"]',el=>el.innerText);assert.ok(nav.includes('Billing & Invoices'));assert.ok(!nav.includes('Staff Master'));
 await page.keyboard.press('Escape');await page.waitForFunction(()=>!document.querySelector('[aria-modal="true"]'));
 assert.ok(await page.$eval('[aria-label="Open navigation"]',el=>el===document.activeElement),'Closing navigation returns keyboard focus');
}));


test('temporary account-check outage retains session and offers a working retry',{timeout:45000},()=>fixture(async({page,state,text,click})=>{
 state.authFailure=true;await page.goto(origin+'/erp');await text('Connection interrupted');
 assert.equal(await page.evaluate(()=>localStorage.getItem('destinlane_access_token')),'test-only-token');
 assert.equal(new URL(page.url()).pathname,'/erp');
 state.authFailure=false;await click('Retry account check');await text('Business overview');await text('TEST-INV-1');
}));


test('management overview uses its own gate and the same source-scoped contract',{timeout:45000},()=>fixture(async({page,state,text})=>{
 state.permissions=[...modules.filter(module=>module!=='dashboard'),'owner'];
 await page.goto(origin+'/owner-executive');await text('Management overview');await text('TEST-INV-1');
 assert.ok(state.requests.includes('/owner/executive-summary'));assert.ok(!state.requests.includes('/erp/dashboard'));
 assert.ok(!(await page.$eval('main',el=>el.innerText)).includes('Net Profit'));
}));


test('a delayed expired-session response cannot revoke a new successful login',{timeout:45000},()=>fixture(async({page,state,text,click})=>{
 state.deferAuth=true;await page.goto(origin+'/login');await page.waitForSelector('#login-id');
 await page.type('#login-id','TEST-MANAGEMENT');await page.type('#login-password','test-only-password');
 await click('Sign in');await text('Business overview');await text('TEST-INV-1');assert.equal(typeof state.releaseAuth,'function');
 const oldResponse=page.waitForResponse(response=>new URL(response.url()).pathname.endsWith('/auth/me'));
 await state.releaseAuth();await oldResponse;await page.waitForNetworkIdle({idleTime:300});
 assert.equal(await page.evaluate(()=>localStorage.getItem('destinlane_access_token')),'fresh-test-only-token');
 assert.equal(new URL(page.url()).pathname,'/erp');assert.ok(!(await page.$eval('body',el=>el.innerText)).includes('Connection interrupted'));
}));
