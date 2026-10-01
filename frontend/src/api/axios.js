import axios from 'axios';

// Resolve base API URL:
// 1. If VITE_API_BASE_URL is explicitly configured (set in Vercel project settings), use it.
// 2. Otherwise, in production, use a relative path (same-origin backend, see root vercel.json).
// 3. In local development without env var, use http://localhost:8000/api/v1.
const envApiUrl = import.meta.env.VITE_API_BASE_URL;

// The production site is a single combined Vercel deployment where
// /api/* is routed internally to the FastAPI backend (see root vercel.json).
// A relative path avoids cross-origin/CORS/auth issues entirely.
const productionBackend = ['https://', 'backend-fortellus.vercel.app', '/api/v1'].join('');
let API_BASE_URL = import.meta.env.PROD
  ? productionBackend
  : 'http://localhost:8000/api/v1';

if (envApiUrl) {
  API_BASE_URL = envApiUrl.endsWith('/api/v1')
    ? envApiUrl
    : `${envApiUrl.replace(/\/$/, '')}/api/v1`;
}

export { API_BASE_URL };

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  // Fast timeout (4s) so if backend is unreachable on client presentations,
  // the app transitions seamlessly to the offline mock dataset without freezing.
  timeout: 20000, // Administrator setup may hit a cold FastAPI function; allow enough time for first startup
});

// Request interceptor — attach JWT
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor — handle 401 and reject HTML responses (from SPA rewrites)
api.interceptors.response.use(
  (response) => {
    // If the server returned an HTML document (e.g. Vercel SPA rewrite fallback for an unhosted API route)
    const contentType = response.headers?.['content-type'] || '';
    if (
      (typeof response.data === 'string' && response.data.trim().toLowerCase().startsWith('<!doctype')) ||
      contentType.includes('text/html')
    ) {
      return Promise.reject(new Error('Backend API endpoint returned HTML instead of JSON. Backend service unavailable.'));
    }
    return response;
  },
  (error) => {
    if (error.response?.status === 401) {
      const hasToken = localStorage.getItem('access_token');
      if (hasToken && hasToken !== 'undefined') {
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);
export default api;
