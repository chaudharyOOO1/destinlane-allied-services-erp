import {test} from 'node:test';
import assert from 'node:assert/strict';
import puppeteer from 'puppeteer-core';
const origin=process.env.FRONTEND_TEST_URL||'http://127.0.0.1:5173';
assert.ok(['127.0.0.1','localhost','[::1]'].includes(new URL(origin).hostname));
const launch=()=>puppeteer.launch({executablePath:process.env.BROWSER_EXECUTABLE_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
async function click(page,text){await page.waitForFunction(t=>[...document.querySelectorAll('button')].some(b=>b.textContent.trim()===t&&!b.disabled),{},text);await page.evaluate(t=>[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===t).click(),text)}
async function intercept(page,handler){
 await page.setRequestInterception(true);
 page.on('request',async request=>{
  const path=new URL(request.url()).pathname.replace('/api/v1','');
  if(!new URL(request.url()).pathname.startsWith('/api/v1/'))return request.continue();
  if(request.method()==='OPTIONS')return request.respond({status:204,headers:{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*','Access-Control-Allow-Methods':'GET,POST,PUT,PATCH,OPTIONS'}});
  let data;
  if(path==='/auth/me')data={id:1,role:'OWNER',full_name:'Local Management',must_change_password:false};
  else if(path==='/users/1/permissions')data={permissions:Object.fromEntries(['user_management.view','user_management.edit','user_management.create','payroll.view','payroll.create','payroll.edit','payroll.approve','payroll.pay'].map(key=>[key,true])),module_roles:{payroll:['OWNER'],user_management:['OWNER']}};
  else if(path==='/erp/company/profile')data={display_name:'Local company'};
  else data=await handler(request,path);
  request.respond({status:data?.__status||200,headers:{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*'},contentType:'application/json',body:JSON.stringify(data?.__data??data??[])});
 });
 await page.evaluateOnNewDocument(()=>localStorage.setItem('destinlane_access_token','local-only-token'));
}
test('Custom account permissions save once as an atomic batch',async()=>{
 const browser=await launch();try{
  const page=await browser.newPage();let writes=0;
  const account={id:2,role:'HR',full_name:'Local HR',login_id:'LOCAL-HR',email:'hr@example.test',is_active:true};
  let snapshot={permissions:{'employees.create':false},supported:{'employees.create':true},revision:'a'.repeat(64)};
  await intercept(page,(request,path)=>{
   if(path==='/users/')return [account];
   if(path==='/users/2/permissions')return snapshot;
   if(path==='/users/2/access'){
    writes++;const body=JSON.parse(request.postData());assert.deepEqual(body,{revision:'a'.repeat(64),changes:{'employees.create':true}});
    snapshot={...snapshot,permissions:{'employees.create':true},revision:'b'.repeat(64)};return snapshot;
   }
  });
  await page.goto(origin+'/users');await page.waitForFunction(()=>document.body.textContent.includes('LOCAL-HR'));
  await page.evaluate(()=>[...document.querySelectorAll('button')].find(b=>b.textContent.includes('Local HR')).click());
  await page.waitForSelector('summary');
  await page.evaluate(()=>[...document.querySelectorAll('summary')].find(b=>b.textContent.includes('Custom permissions')).click());
  await page.waitForFunction(()=>!document.querySelector('[aria-label="employees create"]').disabled);
  await page.click('[aria-label="employees create"]');assert.equal(writes,0);
  await click(page,'Save access');await page.waitForFunction(()=>document.body.textContent.includes('Access saved.'));assert.equal(writes,1);
 }finally{await browser.close()}
});
test('Monthly staff pay preserves a saved proposal through refresh failure and locks its month',async()=>{
 const browser=await launch();try{
  const page=await browser.newPage();let writes=0;const proposals=[];let release;let seen;const postSeen=new Promise(resolve=>{seen=resolve});
  await intercept(page,(request,path)=>{
   if(path==='/erp/payroll/staff-monthly'){
    if(request.method()==='POST'){
     writes++;const body=JSON.parse(request.postData());assert.equal(body.staff_id,10);
     const row={...body,id:1,version:1,staff_code:'DASS0010',name:'Local staff',branch:'BR-1',net_pay:9500,status:'DRAFT'};proposals.push(row);return new Promise(resolve=>{release=()=>resolve(row);seen()});
    }
    if(writes)return {__status:503,__data:{detail:'Simulated staff list refresh outage'}};
    return {staff:[{id:10,staff_code:'DASS0010',name:'Local staff',branch:'BR-1'}],proposals};
   }
  });
  await page.goto(origin+'/payroll');await page.waitForFunction(()=>document.body.textContent.includes('Internal staff'));
  assert.equal(writes,0);
  await page.evaluate(()=>[...document.querySelectorAll('summary')].find(b=>b.textContent.includes('Internal staff')).click());
  await page.waitForFunction(()=>document.querySelector('select option[value="10"]'));
  const section=await page.$('details');
  await (await section.$('select')).select('10');
  const inputs=await section.$$('input[type="number"]');await inputs[0].type('10000');await inputs[1].focus();await page.keyboard.down('Control');await page.keyboard.press('KeyA');await page.keyboard.up('Control');await inputs[1].press('Backspace');await inputs[1].type('500');
  await (await section.$('textarea')).type('Branch work reviewed for this month');
  await page.evaluate(()=>document.querySelector('details form').requestSubmit());
  await postSeen;
  await page.waitForFunction(()=>document.querySelector('input[type="month"]').disabled);
  release();
  try { await page.waitForFunction(()=>document.body.textContent.includes('DRAFT')&&document.body.textContent.includes('9,500'),{timeout:5000}); } catch { assert.fail(JSON.stringify({writes,text:await page.evaluate(()=>document.body.innerText.slice(-4500)),values:await page.evaluate(()=>[...document.querySelectorAll('details form input')].map(x=>({value:x.value,valid:x.checkValidity()})))})); }
  assert.equal(writes,1);
 }finally{await browser.close()}
});
