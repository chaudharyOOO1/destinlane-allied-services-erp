const API_BASE = '/api/v1';

async function request(path, options = {}) {
  const token = localStorage.getItem('emp_access_token');
  const headers = new Headers(options.headers || {});
  if (!(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const contentType = response.headers.get('content-type') || '';
  const body = contentType.includes('application/json') ? await response.json() : await response.text();

  if (!response.ok) {
    throw new Error(typeof body === 'object' ? body.detail || 'Request failed' : 'Request failed');
  }
  return body;
}

export const mobileApi = {
  login: (phone) => request('/mobile/login', {
    method: 'POST',
    body: JSON.stringify({ phone }),
  }),
  me: () => request('/mobile/me'),
  attendance: () => request('/mobile/me/attendance'),
  salary: () => request('/mobile/me/salary'),
  uploadSelfie: (file, kind) => {
    const form = new FormData();
    form.append('file', file, file.name || `${kind}.jpg`);
    return request(`/mobile/selfie?kind=${encodeURIComponent(kind)}`, { method: 'POST', body: form });
  },
  punch: (payload) => request('/mobile/punch', {
    method: 'POST',
    body: JSON.stringify(payload),
  }),
};
