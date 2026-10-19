/** Simulated API contract checks. No real business data or external services. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import puppeteer from 'puppeteer-core';

const origin = process.env.FRONTEND_TEST_URL || 'http://127.0.0.1:5173';
assert.ok(['localhost', '127.0.0.1', '[::1]'].includes(new URL(origin).hostname));
const launch = () => puppeteer.launch({ executablePath: process.env.BROWSER_EXECUTABLE_PATH || '/usr/bin/chromium', headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
const record = () => ({ id: 'test-employee', employee_code: 'DASE0070', name: 'Local Employee', phone: '9876543210', branch: 'BR1', status: 'DRAFT', joining_status: 'DRAFT', version: 1, intimation_id: 'LOCAL-INTIMATION', profile: { name: 'Local Employee', father_name: 'Local Parent', phone: '9876543210', aadhaar_no: '123456789012', client_id: 1, branch: 'BR1' }, readiness: { missing_fields: [], missing_documents: [] } });
async function button(page, label) {
  await page.waitForFunction(label => [...document.querySelectorAll('button')].some(el => el.textContent.trim() === label && !el.disabled), {}, label);
  await page.evaluate(label => [...document.querySelectorAll('button')].find(el => el.textContent.trim() === label).click(), label);
}
async function intercept(page, module, handler) {
  await page.setRequestInterception(true);
  page.on('request', request => {
    const url = new URL(request.url());
    if (!url.pathname.startsWith('/api/v1/')) return request.continue();
    const path = url.pathname.replace('/api/v1', '');
    let response = { status: 200, data: {} };
    if (request.method() === 'OPTIONS') return request.respond({ status: 204, headers: { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': 'GET, POST, PATCH, PUT, OPTIONS' } });
    if (path === '/auth/me') response.data = { id: 1, role: 'OWNER', full_name: 'Local Management', must_change_password: false };
    else if (path === '/users/1/permissions') response.data = { permissions: { ...Object.fromEntries(['view', 'create', 'edit'].map(action => [`${module}.${action}`, true])), ...(module === 'billing' ? { 'clients.view': true } : {}) }, module_roles: { [module]: ['OWNER'] } };
    else if (path === '/erp/company/profile') response.data = { display_name: 'Local Company' };
    else response = handler(request, path) || { status: 404, data: { detail: `Unexpected request: ${path}` } };
    return request.respond({ status: response.status || 200, contentType: 'application/json', headers: { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*' }, body: JSON.stringify(response.data) });
  });
  await page.evaluateOnNewDocument(() => localStorage.setItem('destinlane_access_token', 'local-test-token'));
}

for (const scenario of ['draft survives a directory outage', 'intimation survives a directory outage']) {
  test(`Employee ${scenario}`, async () => {
    const browser = await launch();
    try {
      const page = await browser.newPage();
      let saved = record(), writes = 0;
      const creation = scenario.startsWith('intimation');
      await intercept(page, 'employees', (request, path) => {
        if (request.method() === 'PATCH') {
          const body = JSON.parse(request.postData());
          assert.equal(body.version, saved.version, 'Draft edits use the last confirmed version');
          writes++;
          saved = { ...saved, version: saved.version + 1, profile: body.profile };
          return { data: saved };
        }
        if (path === '/erp/employees/workflow/intimations' && request.method() === 'POST') { writes++; saved = { ...saved, profile: JSON.parse(request.postData()) }; return { status: 201, data: saved }; }
        if (path === '/erp/employees') return writes ? { status: 503, data: { detail: 'Read outage' } } : { data: creation ? [] : [saved] };
        if (path === '/erp/employees/options') return { data: { clients: [{ id: 1, company_name: 'Local Client' }], branches: [{ code: 'BR1', name: 'Local Branch' }], sites: [], approvers: [] } };
        if (path.endsWith('/approvals') || path.endsWith('/approval-categories') || path.endsWith('/compliance') || path.endsWith('/documents') || path.endsWith('/history')) return { data: [] };
        if (path === '/erp/employees/workflow/joining/test-employee') return { data: saved };
      });
      await page.goto(`${origin}/employees`);
      if (creation) {
        await button(page, 'Employee Creation');
        for (const [name, value] of Object.entries(saved.profile)) {
          const input = await page.$(`input[name="${name}"]`);
          if (input) await input.type(value);
        }
        await page.select('select[name="client_id"]', '1');
        await page.select('select[name="branch"]', 'BR1');
        await button(page, 'Submit intimation & generate employee ID');
      } else {
        await button(page, 'Open file');
        await page.waitForSelector('[role="dialog"]');
        await page.type('[role="dialog"] input[name="name"]', ' Updated');
        await button(page, 'Save draft');
      }
      await page.waitForFunction(() => document.body.innerText.includes('could not refresh'));
      let text = await page.$eval('[role="dialog"]', element => element.innerText);
      assert.match(text, /DASE0070/);
      assert.match(text, creation ? /Intimation submitted/ : /Employee draft saved/);
      assert.equal(writes, 1);
      await page.type('[role="dialog"] input[name="name"]', ' Again');
      await button(page, 'Save draft');
      const version = creation ? 2 : 3;
      await page.waitForFunction(version => document.querySelector('[role="dialog"]').innerText.includes(`Version ${version}`), {}, version);
      assert.equal(writes, 2);
      text = await page.$eval('[role="dialog"]', element => element.innerText);
      assert.match(text, /Employee draft saved/);
    } finally { await browser.close(); }
  });
}

test('Billing saves server-generated drafts and uses numeric persisted totals', async () => {
  const browser = await launch();
  try {
    const page = await browser.newPage();
    let writes = 0;
    const invoice = { id: 7, client_id: 1, client_name: 'Local Client', invoice_number: 'AUTO-202610-1', billing_month: '2026-10', issue_date: '2026-10-19', due_date: '2026-10-31', subtotal: '1000.00', tax_amount: '180.00', tax_rate: '18.00', total_amount: '1180.00', status: 'DRAFT' };
    await intercept(page, 'billing', (request, path) => {
      if (path === '/erp/billing/invoices') return { data: [invoice, { ...invoice, id: 8, invoice_number: 'AUTO-202609-1', total_amount: '20.00' }] };
      if (path === '/erp/clients') return { data: [{ id: 1, company_name: 'Local Client' }] };
      if (path === '/erp/billing/generate') {
        writes++;
        const body = JSON.parse(request.postData());
        assert.deepEqual(Object.keys(body).sort(), ['client_id', 'month']);
        assert.equal(body.client_id, 1);
        return { data: { month: body.month, invoices_created: 1, invoices: [{ ...invoice, id: 9, invoice_number: 'SERVER-INVOICE-9' }] } };
      }
    });
    await page.goto(`${origin}/billing`);
    await page.waitForFunction(() => document.body.innerText.includes('₹1,200'));
    assert.doesNotMatch(await page.$eval('body', el => el.innerText), /Mark Paid|\+18% YoY|Estimated Monthly Shift Count/);
    await button(page, 'Generate Client Invoice');
    await page.select('select[aria-label="Invoice client"]', '1');
    await button(page, 'Generate drafts');
    await page.waitForFunction(() => document.body.innerText.includes('1 invoice draft(s) saved'));
    assert.equal(writes, 1);
    assert.match(await page.$eval('body', el => el.innerText), /SERVER-INVOICE-9/);
    await button(page, 'Done');
    await page.reload();
    await page.waitForFunction(() => document.body.innerText.includes('AUTO-202610-1'));
    assert.equal(writes, 1, 'Reloading reads the server without manufacturing invoices');
  } finally { await browser.close(); }
});

test('Employee submission remains confirmed after a lost file refresh and recovers without resubmission', async () => {
  const browser = await launch();
  try {
    const page = await browser.newPage();
    let saved = record(), writes = 0, recovered = false;
    await intercept(page, 'employees', (request, path) => {
      if (path.endsWith('/submit') && request.method() === 'POST') {
        assert.equal(JSON.parse(request.postData()).version, 1);
        writes++;
        saved = { ...saved, version: 2, status: 'ACTIVE', joining_status: 'APPROVED' };
        return { data: { employee_id: saved.id, status: 'APPROVED', final: true } };
      }
      if (path === '/erp/employees') return { data: [saved] };
      if (path === '/erp/employees/options') return { data: { clients: [{ id: 1, company_name: 'Local Client' }], branches: [{ code: 'BR1', name: 'Local Branch' }], sites: [], approvers: [] } };
      if (path.endsWith('/approvals') || path.endsWith('/approval-categories') || path.endsWith('/compliance') || path.endsWith('/documents') || path.endsWith('/history')) return { data: [] };
      if (path === '/erp/employees/workflow/joining/test-employee') return writes && !recovered ? { status: 503, data: { detail: 'Read outage' } } : { data: saved };
    });
    await page.goto(`${origin}/employees`);
    await button(page, 'Open file');
    await page.waitForSelector('[role="dialog"]');
    await button(page, 'Submit & activate');
    await page.waitForFunction(() => document.querySelector('[role="dialog"]').innerText.includes('could not fully refresh'));
    const text = await page.$eval('[role="dialog"]', element => element.innerText);
    assert.match(text, /Employee approved and activated/);
    assert.match(text, /DASE0070/);
    assert.match(text, /APPROVED/);
    assert.doesNotMatch(text, /Submit & activate/);
    const writable = await page.$$eval('[role="dialog"] button', elements => elements.filter(element => ['Update status', 'Upload document', 'Verify', 'Approve'].includes(element.textContent.trim()) && !element.matches(':disabled')).length);
    assert.equal(writable, 0, 'An unknown current version cannot enable another file mutation');
    assert.equal(writes, 1);
    recovered = true;
    await button(page, 'Refresh employee file');
    await page.waitForFunction(() => document.querySelector('[role="dialog"]').innerText.includes('Version 2'));
    assert.match(await page.$eval('[role="dialog"]', element => element.innerText), /latest saved version is loaded/);
    assert.equal(writes, 1, 'Recovery reads the saved file instead of repeating the submission');
  } finally { await browser.close(); }
});

test('Roster cancellation keeps the returned status and version when the list refresh fails', async () => {
  const browser = await launch();
  try {
    const page = await browser.newPage();
    const day = new Date().toISOString().slice(0, 10);
    let writes = 0;
    const row = { id: 17, guard_id: 1, site_id: 2, name: 'Local Employee', employee_code: 'DASE0070', site_name: 'Local Site', client_name: 'Local Client', branch: 'BR1', date: day, shift_type: 'DAY', status: 'SCHEDULED', version: 3 };
    await intercept(page, 'rosters', (request, path) => {
      if (path === '/erp/rosters/17/cancel') {
        const body = JSON.parse(request.postData());
        assert.equal(body.version, 3);
        assert.equal(body.reason, 'Client requested cancellation');
        writes++;
        return { data: { id: 17, status: 'CANCELLED', version: 4 } };
      }
      if (path === '/erp/rosters') return writes ? { status: 503, data: { detail: 'Read outage' } } : { data: [row] };
      if (path === '/erp/rosters/options') return { data: { sites: [] } };
      if (path.endsWith('/shortfall-analysis') || path.endsWith('/employees')) return { data: [] };
    });
    page.on('dialog', dialog => dialog.accept('Client requested cancellation'));
    await page.goto(`${origin}/rosters`);
    await button(page, 'Cancel');
    await page.waitForFunction(() => document.body.innerText.includes('cancellation was saved'));
    const text = await page.$eval('body', element => element.innerText);
    assert.match(text, /Assignment cancelled and retained in history/);
    assert.match(text, /CANCELLED/);
    assert.equal(await page.$$eval('button', buttons => buttons.filter(button => button.textContent.trim() === 'Cancel').length), 0);
    assert.equal(writes, 1);
  } finally { await browser.close(); }
});

test('Billing honours both persisted paid markers and excludes cancelled invoices from unpaid totals', async () => {
  const browser = await launch();
  try {
    const page = await browser.newPage();
    const invoice = { client_id: 1, client_name: 'Local Client', billing_month: '2026-10', issue_date: '2026-10-19', subtotal: '10.00', tax_amount: '0.00', tax_rate: '0.00', due_date: '2026-10-31' };
    const invoices = [
      { ...invoice, id: 1, invoice_number: 'LEGACY-PAID', total_amount: '10.00', status: 'PAID', clearance_status: 'PENDING' },
      { ...invoice, id: 2, invoice_number: 'CLEARED', total_amount: '20.00', status: 'SENT', clearance_status: 'PAID' },
      { ...invoice, id: 3, invoice_number: 'UNPAID', total_amount: '30.00', status: 'SENT', clearance_status: 'PENDING' },
      { ...invoice, id: 4, invoice_number: 'CANCELLED', total_amount: '40.00', status: 'CANCELLED', clearance_status: 'PENDING' },
    ];
    await intercept(page, 'billing', (request, path) => path === '/erp/billing/invoices' ? { data: invoices } : path === '/erp/clients' ? { data: [] } : undefined);
    await page.goto(`${origin}/billing`);
    await page.waitForFunction(() => document.body.innerText.includes('LEGACY-PAID'));
    const values = await page.evaluate(() => Object.fromEntries([...document.querySelectorAll('.erp-panel')].flatMap(panel => {
      const labels = [...panel.querySelectorAll('p')];
      return labels.length >= 2 ? [[labels[0].textContent, labels[1].textContent]] : [];
    })));
    assert.match(values['Invoices marked paid'], /₹30(?:\.00)?$/);
    assert.match(values['Unpaid invoices'], /₹30(?:\.00)?$/);
  } finally { await browser.close(); }
});
