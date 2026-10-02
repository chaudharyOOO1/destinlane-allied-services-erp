import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Eye, EyeOff, LockKeyhole, ArrowRight, AlertCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

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
    setError('');
    setSubmitting(true);
    try {
      await login(loginId, password);
      navigate(location.state?.from || '/erp', { replace: true });
    } catch (err) {
      setError(err?.response?.data?.detail || 'Invalid Login ID or password');
    } finally { setSubmitting(false); }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-7 sm:p-9">
          <div className="mb-8">
            <p className="text-xs font-semibold tracking-[0.18em] uppercase text-slate-400">DestinLane Allied Services Pvt Ltd</p>
            <h1 className="mt-2 text-2xl font-bold text-slate-950">DestinLane Portal</h1>
            <p className="mt-1 text-sm text-slate-500">Sign in to continue to the ERP.</p>
          </div>
          <form onSubmit={submit} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Login ID</label>
              <input value={loginId} onChange={e => setLoginId(e.target.value)} placeholder="enter your emp id" autoComplete="username" autoFocus required className="w-full h-11 px-3 rounded-xl border border-slate-300 bg-white text-slate-900 outline-none focus:ring-2 focus:ring-slate-900/10 focus:border-slate-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Password</label>
              <div className="relative">
                <LockKeyhole className="absolute left-3 top-3.5 w-4 h-4 text-slate-400" />
                <input value={password} onChange={e => setPassword(e.target.value)} type={showPassword ? 'text' : 'password'} autoComplete="current-password" required className="w-full h-11 pl-10 pr-11 rounded-xl border border-slate-300 bg-white text-slate-900 outline-none focus:ring-2 focus:ring-slate-900/10 focus:border-slate-500" />
                <button type="button" onClick={() => setShowPassword(v => !v)} className="absolute right-3 top-3.5 text-slate-400 hover:text-slate-700" aria-label="Toggle password visibility">{showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}</button>
              </div>
            </div>
            {error && <div className="flex gap-2 items-start rounded-xl bg-rose-50 border border-rose-200 p-3 text-sm text-rose-700"><AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />{error}</div>}
            <button disabled={submitting} className="w-full h-11 rounded-xl bg-slate-950 text-white font-semibold text-sm hover:bg-slate-800 disabled:opacity-60 flex items-center justify-center gap-2">{submitting ? 'Signing in…' : <>Sign in <ArrowRight className="w-4 h-4" /></>}</button>
          </form>
          <div className="mt-5 text-center"><Link to="/forgot-password" className="text-sm text-slate-500 hover:text-slate-900">Forgot password?</Link></div>
        </div>
      </div>
    </div>
  );
}
