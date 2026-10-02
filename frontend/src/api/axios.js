import axios from 'axios';

const envApiUrl = import.meta.env.VITE_API_BASE_URL;
const API_BASE_URL = envApiUrl
  ? (envApiUrl.endsWith('/api/v1')
      ? envApiUrl
      : `${envApiUrl.replace(/\/$/, '')}/api/v1`)
  : (import.meta.env.PROD ? '/api/v1' : 'http://localhost:8000/api/v1');

export { API_BASE_URL };

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 20000,
});

api.interceptors.response.use(
  (response) => {
    const contentType = response.headers?.['content-type'] || '';
    if (
      (typeof response.data === 'string' && response.data.trim().toLowerCase().startsWith('<!doctype')) ||
      contentType.includes('text/html')
    ) {
      return Promise.reject(new Error('Backend API endpoint returned HTML instead of JSON. Backend service unavailable.'));
    }
    return response;
  },
  (error) => Promise.reject(error)
);

export default api;
