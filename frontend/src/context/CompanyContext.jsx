import { createContext, useContext, useEffect, useState } from 'react';
import { useAuth } from './AuthContext';
import api from '../api/axios';

const defaultCompany = { legal_name: 'DestinLane Allied Services Pvt Ltd', display_name: 'DestinLane Allied Services' };
const CompanyContext = createContext(null);

export function CompanyProvider({ children }) {
  const { user } = useAuth();
  const userId = user?.id;
  const [state, setState] = useState({ userId: null, company: defaultCompany, error: '' });
  useEffect(() => {
    if (!userId) return;
    const controller = new AbortController();
    api.get('/erp/company/profile', { signal: controller.signal })
      .then(({ data }) => setState({ userId, company: data, error: '' }))
      .catch(err => {
        if (!controller.signal.aborted) setState({ userId, company: defaultCompany, error: err?.response?.data?.detail || 'Unable to load company details.' });
      });
    return () => controller.abort();
  }, [userId]);
  const loading = Boolean(userId && state.userId !== userId);
  const company = state.userId === userId ? state.company : defaultCompany;
  function updateCompany(value) { setState({ userId, company: value, error: '' }); }
  return <CompanyContext.Provider value={{ company, loading, error: state.userId === userId ? state.error : '', updateCompany }}>{children}</CompanyContext.Provider>;
}

export function useCompany() {
  const value = useContext(CompanyContext);
  if (!value) throw new Error('useCompany must be used inside CompanyProvider.');
  return value;
}
