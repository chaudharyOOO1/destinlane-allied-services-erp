import axios from 'axios';
import { attachRetryKey, finishRetry } from './idempotency.mjs';
const TOKEN_KEY = 'destinlane_access_token';
const envApiUrl = import.meta.env.VITE_API_BASE_URL;
const API_BASE_URL = envApiUrl
  ? (envApiUrl.endsWith('/api/v1') ? envApiUrl : `${envApiUrl.replace(/\/$/, '')}/api/v1`)
  : (import.meta.env.PROD ? '/api/v1' : 'http://localhost:8000/api/v1');

export { API_BASE_URL };

const api = axios.create({ baseURL: API_BASE_URL, headers: { 'Content-Type': 'application/json' }, timeout: 20000 });

api.interceptors.request.use(async (config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return attachRetryKey(config);
});

api.interceptors.response.use(
  (response) => {
    const contentType = response.headers?.['content-type'] || '';
    if ((typeof response.data === 'string' && response.data.trim().toLowerCase().startsWith('<!doctype')) || contentType.includes('text/html')) {
      return Promise.reject(new Error('Backend API endpoint returned HTML instead of JSON. Backend service unavailable.'));
    }
    finishRetry(response.config, response.status);
    return response;
  },
  (error) => {
    finishRetry(error?.config, error?.response?.status);
    const publicAuthRequest = ['/auth/login', '/auth/reset-password', '/auth/admin-recover-password', '/auth/setup-admin'].includes(error?.config?.url);
    // An old request must not revoke a newer session established while it ran.
    const currentToken = localStorage.getItem(TOKEN_KEY);
    const requestAuthorization = error?.config?.headers?.Authorization || error?.config?.headers?.get?.('Authorization');
    if (error?.response?.status === 401 && !publicAuthRequest && currentToken && requestAuthorization === `Bearer ${currentToken}` && !window.location.pathname.startsWith('/login')) {
      localStorage.removeItem(TOKEN_KEY);
      window.location.assign('/login');
    }
    return Promise.reject(error);
  }
);

export default api;
