import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useAccess } from '../context/AccessContext';

export default function ProtectedRoute() {
  const {user,loading}=useAuth();
  const {ready,canPage,home,error,refresh}=useAccess();
  const location=useLocation();
  if (loading || (user&&!ready)) return <div className="min-h-screen bg-slate-50 flex items-center justify-center text-sm text-slate-500">Loading DestinLane Portal…</div>;
  if (!user) return <Navigate to="/login" replace state={{from:location.pathname}}/>;
  if (user.must_change_password && location.pathname!=='/account') return <Navigate to="/account" replace/>;
  if (error && location.pathname!=='/account') return <div className="p-6 text-sm"><p role="alert">{error}</p><button onClick={refresh} className="mt-3 rounded-lg border px-3 py-2">Retry</button></div>;
  if (!canPage(location.pathname)) return <Navigate to={home} replace/>;
  return <Outlet/>;
}
