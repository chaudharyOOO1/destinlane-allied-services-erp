import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import api from '../api/axios';

const AuthContext = createContext(null);
const TOKEN_KEY = 'destinlane_access_token';

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = async () => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) { setUser(null); setLoading(false); return null; }
    try {
      const response = await api.get('/auth/me');
      setUser(response.data);
      return response.data;
    } catch {
      localStorage.removeItem(TOKEN_KEY);
      setUser(null);
      return null;
    } finally { setLoading(false); }
  };

  useEffect(() => { refreshUser(); }, []);

  const login = async (loginId, password) => {
    const response = await api.post('/auth/login', { login_id: loginId.trim(), password });
    localStorage.setItem(TOKEN_KEY, response.data.access_token);
    setUser(response.data.user);
    return response.data.user;
  };

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);
    setUser(null);
    window.location.assign('/login');
  };

  const value = useMemo(() => ({ user, loading, login, logout, refreshUser }), [user, loading]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth must be used inside AuthProvider');
  return value;
}

export { TOKEN_KEY };
