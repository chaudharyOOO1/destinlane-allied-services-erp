// Optional safe replay keys for confirmed high-risk ERP writes.
// Only operation names and SHA-256 fingerprints are stored in sessionStorage.
// No password, Aadhaar, or request body is persisted.
const PREFIX = 'das_retry_v1:';
const MAX_AGE_MS = 24 * 60 * 60 * 1000;

export function retryOperation(config) {
  if ((config.method || 'get').toLowerCase() !== 'post') return null;
  const path = (config.url || '').split('?')[0].replace(/\/$/, '');
  if (path === '/erp/employees/workflow/intimations') return 'employee-intimation';
  if (path === '/erp/internal-staff') return 'staff-creation';
  if (/^\/erp\/employees\/workflow\/approvals\/[^/]+\/decision$/.test(path)) return 'employee-approval';
  if (/^\/erp\/travel-expenses\/\d+\/pay$/.test(path)) return 'travel-payment';
  return null;
}

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])]));
  }
  return value;
}

export async function attachRetryKey(config, { storage = globalThis.sessionStorage, cryptography = globalThis.crypto, clock = Date.now } = {}) {
  const operation = retryOperation(config);
  if (!operation) return config;
  // Never silently send an unsafe mutation without the promised retry protection.
  if (!storage || !cryptography?.subtle?.digest || !cryptography?.randomUUID) {
    throw new Error('Safe request tracking is unavailable in this browser.');
  }
  const body = typeof config.data === 'string' ? JSON.parse(config.data) : config.data;
  const canonicalInput = JSON.stringify({ operation, data: canonical(body) });
  const hash = new Uint8Array(await cryptography.subtle.digest('SHA-256', new TextEncoder().encode(canonicalInput)));
  const fingerprint = Array.from(hash, b => b.toString(16).padStart(2, '0')).join('');
  const storageKey = PREFIX + operation + ':' + fingerprint;
  let entry;
  try { entry = JSON.parse(storage.getItem(storageKey) || 'null'); } catch { entry = null; }
  if (!entry || typeof entry.key !== 'string' || !Number.isFinite(entry.when) || clock() - entry.when > MAX_AGE_MS || clock() < entry.when) {
    entry = { key: cryptography.randomUUID(), when: clock() };
    storage.setItem(storageKey, JSON.stringify(entry));
  }
  if (typeof config.headers?.set === 'function') config.headers.set('Idempotency-Key', entry.key);
  else config.headers = { ...config.headers, 'Idempotency-Key': entry.key };
  config.__dasRetryStorageKey = storageKey;
  return config;
}

export function finishRetry(config, status, { storage = globalThis.sessionStorage } = {}) {
  const key = config?.__dasRetryStorageKey;
  if (!key || !storage) return;
  // Preserve the key on timeout, lost response, and server 5xx.
  // On confirmed success or terminal validation/authorization errors, clear it.
  if ((status >= 200 && status < 300) ||
      (status >= 400 && status < 500 && status !== 408 && status !== 429)) {
    storage.removeItem(key);
  }
}
