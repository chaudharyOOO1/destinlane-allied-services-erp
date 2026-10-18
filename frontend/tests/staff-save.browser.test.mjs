/** Browser contract test with a simulated API. No production credentials/data. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import puppeteer from 'puppeteer-core';

const origin = process.env.FRONTEND_TEST_URL || 'http://127.0.0.1:5173';
assert.ok(['localhost', '127.0.0.1', '[::1]'].includes(new URL(origin).hostname), 'Tests must target a local frontend');
const rights = {'staff.view': true, 'staff.create': true, 'staff.edit': true};
const profile = {name:'Test Coordinator',phone:'9876543210',email:'staff@example.invalid',department:'Operations',designation:'Coordinator',branch:'',joining_date:'',employment_type:'FULL_TIME',notes:''};

for (const scenario of ['detail refresh fails', 'directory refresh fails', 'edit refresh fails', 'access refresh fails', 'status refresh fails', 'save rejected', 'normal save']) {
  test(scenario, async () => {
    const browser = await puppeteer.launch({executablePath:process.env.BROWSER_EXECUTABLE_PATH || '/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
    try {
      const page = await browser.newPage();
      let writes = 0;
      const existing = ['edit refresh fails','access refresh fails','status refresh fails'].includes(scenario);
      let record = {id:1,staff_code:'DASS0010',name:profile.name,phone:profile.phone,department:profile.department,status:'ACTIVE',version:1,profile,account:{id:2,login_id:'DASS0010',role:'OPERATIONS',is_active:true,must_change_password:true}};
      await page.setRequestInterception(true);
      page.on('request', request => {
        const path = new URL(request.url()).pathname.replace('/api/v1','');
        if (!new URL(request.url()).pathname.startsWith('/api/v1/')) return request.continue();
        let data = {}, status = 200;
        if (request.method() === 'OPTIONS') return request.respond({status:204,headers:{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*','Access-Control-Allow-Methods':'GET, POST, PUT, OPTIONS'}});
        if (path === '/auth/me') data = {id:1,role:'OWNER',full_name:'Test Management',must_change_password:false};
        else if (path === '/users/1/permissions') data = {permissions:rights,module_roles:{staff:['OWNER']}};
        else if (path === '/erp/company/profile') data = {display_name:'Test Company'};
        else if (path.endsWith('/office-options')) data = {branches:[],login_roles:['OPERATIONS'],permissions:{OPERATIONS:{'employees.view':true}},supported:{OPERATIONS:{'employees.view':true}}};
        else if (request.method() === 'POST' || request.method() === 'PUT') {
          writes++;
          if (scenario === 'save rejected') { status = 422; data = {detail:'This phone number is invalid.'}; }
          else { const body = JSON.parse(request.postData()); if (request.method() === 'PUT') assert.equal(body.version,record.version,'Edits must use the acknowledged version'); record = {...record,profile:body.profile || record.profile,status:body.status || record.status,version:writes + (existing ? 1 : 0)}; data = record; }
        } else if (path === '/erp/internal-staff/1') {
          if (writes && ['detail refresh fails','edit refresh fails','access refresh fails','status refresh fails'].includes(scenario)) {status=503;data={detail:'Simulated read outage'};}
          else data={...record,permissions:{'employees.view':true}};
        } else if (path === '/erp/internal-staff') {
          if (writes && scenario === 'directory refresh fails') {status=503;data={detail:'Simulated list outage'};}
          else data = existing || writes && scenario !== 'save rejected' ? [record] : [];
        } else {status=404;data={detail:`Unexpected test request: ${path}`};}
        return request.respond({status,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*'},body:JSON.stringify(data)});
      });
      await page.evaluateOnNewDocument(() => localStorage.setItem('destinlane_access_token','local-test-token'));
      await page.goto(`${origin}/staff`);
      async function clickButton(text) {
        await page.waitForFunction(text => [...document.querySelectorAll('button')].some(b=>b.textContent.trim()===text), {}, text);
        await page.evaluate(text => [...document.querySelectorAll('button')].find(b=>b.textContent.trim()===text).click(), text);
      }
      await clickButton(existing ? 'Open' : 'Add staff');
      await page.waitForSelector('[role="dialog"]');
      if (!existing) {
        for (const [index,value] of [profile.name,profile.phone,profile.email,profile.department,profile.designation].entries()) {
          const inputs=await page.$$('[role="dialog"] form:first-of-type fieldset:first-of-type input');
          await inputs[index].type(value);
        }
        await page.type('input[type="password"]','test-only-temporary-password');
      } else if (scenario === 'edit refresh fails') {
        const input=await page.$('[role="dialog"] form input'); await input.type(' Updated');
      } else if (scenario === 'status refresh fails') {
        await page.type('input[maxlength="1000"]','Test leave');
      }
      await clickButton(scenario === 'access refresh fails' ? 'Save ERP access' : scenario === 'status refresh fails' ? 'Mark inactive' : existing ? 'Save staff details' : 'Create staff and login');
      await page.waitForFunction(() => ![...document.querySelectorAll('button')].some(b=>b.textContent==='Saving…'));
      const state=await page.evaluate(()=>({text:document.body.innerText,heading:document.querySelector('#staff-title')?.textContent, password:document.querySelector('input[type="password"]')?.value}));
      assert.equal(writes,1);
      if (scenario === 'save rejected') {
        assert.match(state.text,/This phone number is invalid/);
        assert.match(state.heading,/Create staff/);
        assert.equal(state.password,'test-only-temporary-password');
        assert.doesNotMatch(state.text,/Saved DASS0010/);
      } else {
        assert.equal(state.heading,'DASS0010','A confirmed write must leave creation mode even if a subsequent GET fails');
        assert.match(state.text,scenario === 'access refresh fails' ? /ERP access saved/ : scenario === 'status refresh fails' ? /Staff marked inactive/ : /Saved DASS0010/);
        assert.equal(state.password,undefined,'A confirmed write must clear the temporary password');
        if (scenario.includes('fails')) assert.match(state.text,/saved.*refresh|refresh.*saved/is);
        // Repeat the edit with the version returned by the first write, even after a failed refresh.
        const input=await page.$('[role="dialog"] form input'); await input.type(' Again');
        await clickButton('Save staff details');
        await page.waitForFunction(()=>![...document.querySelectorAll('button')].some(b=>b.textContent==='Saving…'));
        assert.equal(writes,2);
        assert.equal((await page.$eval('#staff-title',el=>el.textContent)),'DASS0010');
      }
    } finally { await browser.close(); }
  });
}
