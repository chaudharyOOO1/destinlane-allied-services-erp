import { useState, useEffect } from 'react';
import axios from 'axios';
import { AuthContext } from './auth-context-base';
import api from '../api/axios';
import { INITIAL_USERS } from '../api/mockData';

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try { const stored = localStorage.getItem('user'); return stored && stored !== 'undefined' ? JSON.parse(stored) : null; } catch { return null; }
  });
  const [token, setToken] = useState(() => localStorage.getItem('access_token') || null);
  const [permissions, setPermissions] = useState(() => {
    try { return JSON.parse(localStorage.getItem('permissions') || '{}'); } catch { return {}; }
  });
  const [permissionsLoading, setPermissionsLoading] = useState(!!token);
  const [loading, setLoading] = useState(false);
  const [apiConnected, setApiConnected] = useState(false);

  async function loadPermissions() {
    if (!token) { setPermissions({}); setPermissionsLoading(false); return; }
    setPermissionsLoading(true);
    try {
      const response = await api.get('/auth/permissions');
      const next = response.data?.permissions || {};
      setPermissions(next);
      localStorage.setItem('permissions', JSON.stringify(next));
    } catch { setPermissions({}); }
    finally { setPermissionsLoading(false); }
  }

  useEffect(() => {
    let isMounted = true;
    const base = api.defaults.baseURL || '';
    const healthUrl = base.includes('/api/v1') ? base.replace(/\/api\/v1\/?$/, '/health') : (base ? base + '/health' : '/health');
    axios.get(healthUrl, { timeout: 3000 })
      .then((res) => { if (isMounted) setApiConnected(!!(res.data && res.data.status === 'healthy')); })
      .catch(() => { if (isMounted) setApiConnected(false); });
    return () => { isMounted = false; };
  }, []);

  useEffect(() => { if (token) loadPermissions(); }, [token]);

  const isAuthenticated = !!user && !!token;

  async function login(loginId, password) {
    setLoading(true);
    try {
      const response = await api.post('/auth/login', { login_id: loginId, password });
      if (!response.data?.access_token) throw new Error('Invalid authentication response from server');
      const { access_token, user: userData } = response.data;
      localStorage.setItem('access_token', access_token);
      localStorage.setItem('user', JSON.stringify(userData));
      setToken(access_token); setUser(userData); setApiConnected(true);
      return { success: true };
    } catch (error) {
      return { success: false, error: error.response?.data?.detail || 'Invalid Login ID or password.' };
    } finally { setLoading(false); }
  }

  async function switchPersona(role) {
    const matched = INITIAL_USERS.find(u => u.role === role);
    if (!matched?.email || !matched?.personaPassword) return { success: false, error: 'Persona credentials are not configured.' };
    return login(matched.email, matched.personaPassword);
  }

  function logout() {
    localStorage.removeItem('access_token'); localStorage.removeItem('user'); localStorage.removeItem('permissions');
    setToken(null); setUser(null); setPermissions({});
  }

  function can(permission) { return !!permissions[permission]; }

  const value = { user, token, permissions, permissionsLoading, isAuthenticated, loading, apiConnected, login, logout, switchPersona, can, refreshPermissions: loadPermissions };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export { useAuth } from './useAuth';
export default AuthProvider;
