import test from 'node:test';
import assert from 'node:assert/strict';
import puppeteer from 'puppeteer-core';
import { createServer } from 'vite';

test('real browser Axios interceptor retains the retry key over a 503 and clears on success', async () => {
  const vite = await createServer({
    server: { host: '127.0.0.1', port: 5187, strictPort: true },
    logLevel: 'silent',
  });
  await vite.listen();
  let browser;
  try {
    browser = await puppeteer.launch({
      executablePath: process.env.BROWSER_EXECUTABLE_PATH || '/usr/bin/chromium',
      headless: true,
      args: ['--no-sandbox', '--disable-dev-shm-usage'],
      timeout: 25000,
    });
    const page = await browser.newPage();
    const seen = new Map();
    await page.setRequestInterception(true);
    page.on('request', async (req) => {
      const url = req.url();
      if (!url.startsWith('http://localhost:8000/api/v1/')) {
        await req.continue();
        return;
      }
      const cors = {
        'Access-Control-Allow-Origin': 'http://127.0.0.1:5187',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, OPTIONS',
        'Access-Control-Allow-Headers': 'authorization, content-type, idempotency-key',
        'Access-Control-Allow-Credentials': 'true',
        'Content-Type': 'application/json',
      };
      if (req.method() === 'OPTIONS') {
        await req.respond({ status: 204, headers: cors });
        return;
      }
      const path = new URL(url).pathname;
      const requests = seen.get(path) || [];
      requests.push({ key: req.headers()['idempotency-key'], authorization: req.headers().authorization });
      seen.set(path, requests);
      await req.respond({
        status: requests.length === 1 ? 503 : 200,
        headers: cors,
        body: JSON.stringify({ ok: true, tested: path }),
      });
    });
    await page.goto('http://127.0.0.1:5187/', { waitUntil: 'domcontentloaded', timeout: 20000 });
    await page.evaluate(() => localStorage.setItem('destinlane_access_token', 'qa-browser-only-token'));
    for (const path of [
      '/erp/employees/workflow/intimations',
      '/erp/internal-staff',
      '/erp/employees/workflow/approvals/0000-qa/decision',
      '/erp/travel-expenses/42/pay',
    ]) {
      const result = await page.evaluate(async (route) => {
        const api = (await import('/src/api/axios.js')).default;
        const body = { version: 1, approval: 'QA', name: 'Fictional employee' };
        let first;
        try { await api.post(route, body); first = 200; }
        catch (error) { first = error.response?.status ?? 'no-response'; }
        const second = await api.post(route, body);
        const third = await api.post(route, body);
        return { first, second: second.status, third: third.status };
      }, path);
      assert.deepEqual(result, { first: 503, second: 200, third: 200 }, path);
      const reqs = seen.get('/api/v1' + path) || [];
      assert.equal(reqs.length, 3, path);
      assert.ok(reqs[0].key?.length >= 8, path);
      assert.equal(reqs[0].key, reqs[1].key, path);
      assert.notEqual(reqs[1].key, reqs[2].key, path);
      assert.ok(reqs.every(x => x.authorization === 'Bearer qa-browser-only-token'));
    }
    await page.close();
  } finally {
    await browser?.close();
    await vite.close();
  }
});
