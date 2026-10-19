import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useAccess } from '../context/AccessContext';

export default function ProtectedRoute() {
  const {user,loading,authError,refreshUser,logout}=useAuth();
  const {ready,canPage,home,error,refresh}=useAccess();
  const location=useLocation();
  if (loading || (user&&!ready)) return <div className="min-h-screen bg-slate-50 flex items-center justify-center text-sm text-slate-500">Loading DestinLane Portal…</div>;
  if (authError) return <div className="flex min-h-screen items-center justify-center bg-slate-50 px-5"><main className="w-full max-w-lg rounded-xl border border-slate-200 bg-white p-7"><h1 className="text-xl font-semibold text-slate-900">Connection interrupted</h1><p role="alert" className="mt-3 text-sm leading-6 text-slate-600">{authError}</p><div className="mt-5 flex gap-3"><button onClick={refreshUser} className="rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-medium text-white">Retry account check</button><button onClick={logout} className="rounded-lg border border-slate-300 px-4 py-2.5 text-sm text-slate-700">Sign out</button></div></main></div>;
  if (!user) return <Navigate to="/login" replace state={{from:location.pathname}}/>;
  if (user.must_change_password && location.pathname!=='/account') return <Navigate to="/account" replace/>;
  if (error && location.pathname!=='/account') return <div className="p-6 text-sm"><p role="alert">{error}</p><button onClick={refresh} className="mt-3 rounded-lg border px-3 py-2">Retry</button></div>;
  if (!canPage(location.pathname)) return <Navigate to={home} replace/>;
  return <Outlet/>;
}
