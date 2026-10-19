import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Eye, EyeOff, LockKeyhole, ArrowRight, AlertCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import CompanyLogo from '../components/CompanyLogo';

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [loginId, setLoginId] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => { const hash = new URLSearchParams(window.location.hash.replace(/^#/, '')); const query = new URLSearchParams(window.location.search); if (hash.get('access_token') && hash.get('type') === 'recovery') { window.location.replace('/reset-password' + window.location.hash); return; } if (query.get('access_token') && query.get('type') === 'recovery') { window.location.replace('/reset-password' + window.location.search); return; } if (user) navigate('/erp', { replace: true }); }, [user, navigate]);

  async function submit(event) {
    event.preventDefault();
    if (submitting) return;
    setError('');
    setSubmitting(true);
    try {
      await login(loginId.trim(), password);
      navigate(location.state?.from || '/erp', { replace: true });
    } catch (err) {
      setError(err?.response?.data?.detail || 'Invalid Login ID or password');
    } finally { setSubmitting(false); }
  }

  return (
    <div className="min-h-screen bg-slate-50 px-5 py-8 text-slate-900 sm:px-10">
      <div className="mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-6xl flex-col">
        <header><CompanyLogo /></header>
        <main className="grid flex-1 items-center gap-12 py-12 lg:grid-cols-2 lg:gap-24">
          <section className="hidden max-w-lg lg:block" aria-label="Company workspace">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Company workspace</p>
            <h1 className="mt-5 text-4xl font-semibold leading-tight tracking-tight text-slate-950">A clear view of your business.</h1>
            <p className="mt-5 text-base leading-7 text-slate-600">Manage people, sites and daily operations. Keep your records and company finances together.</p>
            <p className="mt-8 border-l-2 border-slate-300 pl-4 text-sm leading-6 text-slate-500">Sign in with your assigned account. Your role determines the information and actions available to you.</p>
          </section>
          <section className="mx-auto w-full max-w-md rounded-2xl border border-slate-200 bg-white p-7 shadow-sm sm:p-9" aria-labelledby="login-title">
            <div className="mb-8">
              <h2 id="login-title" className="text-2xl font-semibold tracking-tight text-slate-950">Sign in</h2>
              <p className="mt-2 text-sm leading-6 text-slate-500">Enter your details to access the DestinLane ERP.</p>
            </div>
          <form onSubmit={submit} className="space-y-5" aria-busy={submitting}>
            <div>
              <label htmlFor="login-id" className="block text-sm font-medium text-slate-700 mb-1.5">Login ID</label>
              <input id="login-id" name="username" value={loginId} onChange={e => setLoginId(e.target.value)} placeholder="Staff ID, employee ID or email" autoComplete="username" autoCapitalize="none" spellCheck={false} disabled={submitting} aria-describedby={error ? 'login-error' : undefined} autoFocus required className="w-full h-11 px-3 rounded-xl border border-slate-300 bg-white text-slate-900 outline-none focus:ring-2 focus:ring-slate-900/10 focus:border-slate-500 disabled:bg-slate-50" />
            </div>
            <div>
              <label htmlFor="login-password" className="block text-sm font-medium text-slate-700 mb-1.5">Password</label>
              <div className="relative">
                <LockKeyhole className="absolute left-3 top-3.5 w-4 h-4 text-slate-400" />
                <input id="login-password" name="password" value={password} onChange={e => setPassword(e.target.value)} type={showPassword ? 'text' : 'password'} autoComplete="current-password" disabled={submitting} aria-describedby={error ? 'login-error' : undefined} required className="w-full h-11 pl-10 pr-11 rounded-xl border border-slate-300 bg-white text-slate-900 outline-none focus:ring-2 focus:ring-slate-900/10 focus:border-slate-500 disabled:bg-slate-50" />
                <button type="button" onClick={() => setShowPassword(v => !v)} className="absolute right-0 top-0 flex h-11 w-11 items-center justify-center rounded-r-xl text-slate-400 hover:text-slate-700 focus-visible:outline-2 focus-visible:outline-slate-500" aria-label={showPassword ? 'Hide password' : 'Show password'} aria-pressed={showPassword}>{showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}</button>
              </div>
            </div>
            {error && <div id="login-error" role="alert" className="flex gap-2 items-start rounded-xl bg-rose-50 border border-rose-200 p-3 text-sm text-rose-700"><AlertCircle className="w-4 h-4 mt-0.5 shrink-0" /><span>{typeof error === 'string' ? error : 'Unable to sign in. Check your details and try again.'}</span></div>}
            <button disabled={submitting} className="w-full h-11 rounded-xl bg-slate-950 text-white font-semibold text-sm hover:bg-slate-800 disabled:opacity-60 flex items-center justify-center gap-2">{submitting ? 'Signing in…' : <>Sign in <ArrowRight className="w-4 h-4" /></>}</button>
          </form>
          <div className="mt-6 border-t border-slate-100 pt-5 text-center"><Link to="/forgot-password" className="text-sm font-medium text-slate-600 hover:text-slate-900">Forgot password?</Link></div>
          </section>
        </main>
        <footer className="text-center text-xs leading-5 text-slate-400">DestinLane Allied Services Pvt Ltd · Internal business system</footer>
      </div>
    </div>
  );
}
