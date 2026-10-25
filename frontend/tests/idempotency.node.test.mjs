import test from 'node:test';
import assert from 'node:assert/strict';
import { retryOperation, attachRetryKey, finishRetry } from '../src/api/idempotency.mjs';

function storage() {
  const map = new Map();
  return {
    map, getItem: (key) => map.has(key) ? map.get(key) : null,
    setItem: (key, value) => map.set(key, value),
    removeItem: (key) => map.delete(key),
  };
}
function request(path, body, method = 'post') {
  return { url: path, method, data: body, headers: {} };
}
const emp = '/erp/employees/workflow/intimations';
const staff = '/erp/internal-staff';
const approval = '/erp/employees/workflow/approvals/case-123/decision';
const payment = '/erp/travel-expenses/42/pay';

test('only the four selected POST operations receive tracking keys', async () => {
  for (const path of [emp, staff, approval, payment]) assert.ok(retryOperation(request(path, {})), path);
  assert.equal(retryOperation(request(emp, {}, 'get')), null);
  assert.equal(retryOperation(request('/erp/payroll/calculate', {})), null);
  assert.equal(retryOperation(request('/erp/travel-expenses/42/decision', {})), null);
});

test('same content, even reordered fields, retains one key following a lost response', async () => {
  const box = storage();
  const a = await attachRetryKey(request(emp, { name: 'Test', phone: '9876543210' }), { storage: box });
  finishRetry(a, undefined, { storage: box });
  const b = await attachRetryKey(request(emp, { phone: '9876543210', name: 'Test' }), { storage: box });
  assert.equal(a.headers['Idempotency-Key'], b.headers['Idempotency-Key']);
  assert.equal(box.map.size, 1);
});

test('changed content uses a different key and cannot replay an old decision', async () => {
  const box = storage();
  const a = await attachRetryKey(request(approval, { decision: 'APPROVE' }), { storage: box });
  const b = await attachRetryKey(request(approval, { decision: 'REJECT', remarks: 'Missing document' }), { storage: box });
  assert.notEqual(a.headers['Idempotency-Key'], b.headers['Idempotency-Key']);
});

test('confirmed server success clears key so the next action is new', async () => {
  const box = storage();
  const a = await attachRetryKey(request(payment, { version: 4, payment_reference: 'QA01' }), { storage: box });
  finishRetry(a, 200, { storage: box });
  assert.equal(box.map.size, 0);
  const b = await attachRetryKey(request(payment, { version: 4, payment_reference: 'QA01' }), { storage: box });
  assert.notEqual(a.headers['Idempotency-Key'], b.headers['Idempotency-Key']);
});

test('HTTP 500, 408 and 429 preserve key; HTTP 422 clears it', async () => {
  const box = storage();
  const req = await attachRetryKey(request(staff, { profile: { name: 'Fictional' } }), { storage: box });
  for (const code of [500, 408, 429]) {
    finishRetry(req, code, { storage: box });
    assert.equal(box.map.size, 1, String(code));
  }
  finishRetry(req, 422, { storage: box });
  assert.equal(box.map.size, 0);
});

test('neither password nor employee identity data is stored in session storage', async () => {
  const box = storage();
  const secret = 'example-super-private-fixture-password';
  await attachRetryKey(request(staff, { account: { temporary_password: secret }, profile: { aadhaar_no: '234567890124' } }), { storage: box });
  const content = [...box.map.entries()].flat().join(' ');
  assert.ok(!content.includes(secret));
  assert.ok(!content.includes('234567890124'));
  assert.equal(box.map.size, 1);
});

test('key expires after 24 hours, rotating for a fresh attempt', async () => {
  const box = storage();
  const t = 1_800_000_000_000;
  const a = await attachRetryKey(request(emp, { first: 1 }), { storage: box, clock: () => t });
  const b = await attachRetryKey(request(emp, { first: 1 }), { storage: box, clock: () => t + 86_400_001 });
  assert.notEqual(a.headers['Idempotency-Key'], b.headers['Idempotency-Key']);
});

test('unsupported crypto is blocked rather than silently losing safe-retry semantics', async () => {
  const box = storage();
  await assert.rejects(() => attachRetryKey(request(emp, {}), { storage: box, cryptography: {} }), /unavailable/);
});

test('unrelated GET requests are unchanged when storage unavailable', async () => {
  const config = request('/erp/clients', undefined, 'get');
  assert.equal(await attachRetryKey(config, { storage: null, cryptography: null }), config);
});
