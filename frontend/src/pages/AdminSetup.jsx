import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { KeyRound, ShieldCheck, Loader2, ArrowRight } from 'lucide-react';
import api from '../api/axios';

export default function AdminSetup() {
  const navigate = useNavigate();
  const [token, setToken] = useState('');
  const [loginId, setLoginId] = useState('Admin@destinLane');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError('');
    if (!loginId.trim()) return setError('Administrator Login ID is required.');
    if (password !== confirm) return setError('Passwords do not match.');
    if (password.length < 12) return setError('Use at least 12 characters for the administrator password.');
    setLoading(true);
    try {
      await api.post('/auth/setup-admin', {
        email: 'admin@fortelluserp.com',
        login_id: loginId.trim(),
        password,
        setup_token: token,
      });
      setSuccess(true);
    } catch (err) {
      const detail = err.response?.data?.detail;
      const status = err.response?.status;
      if (detail) setError(detail);
      else if (status) setError(`Administrator synchronization failed (HTTP ${status}).`);
      else if (err.code === 'ECONNABORTED') setError('The ERP server took too long to respond. Please wait a few seconds and try again.');
      else if (err.message) setError(`Connection error: ${err.message}`);
      else setError('Administrator synchronization could not be completed.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-white flex items-center justify-center p-5">
      <div className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-8 sm:p-10 shadow-sm space-y-7">
        <div className="text-center">
          <div className="mx-auto w-14 h-14 rounded-2xl bg-teal-50 border border-teal-200 flex items-center justify-center text-teal-700 mb-4">
            <ShieldCheck className="w-8 h-8" />
          </div>
          <p className="text-xs font-semibold uppercase tracking-[.18em] text-slate-500">DestinLane ERP</p>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">Administrator Synchronization</h1>
          <p className="text-sm text-slate-500 mt-2">Synchronize the administrator Login ID and password with Supabase Auth.</p>
        </div>

        {success ? (
          <div className="space-y-4 text-center">
            <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm font-semibold">
              Administrator synchronized successfully. You can now sign in using your Login ID and password.
            </div>
            <button onClick={() => navigate('/login')} className="w-full h-11 rounded-xl bg-teal-700 text-white font-bold flex items-center justify-center gap-2">
              Go to login <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1">Administrator Login ID</label>
              <input required minLength={3} value={loginId} onChange={e => setLoginId(e.target.value)} className="w-full h-12 rounded-xl border border-slate-300 bg-white px-4 text-sm outline-none focus:border-slate-900 focus:ring-4 focus:ring-slate-900/5" />
            </div>
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1">Administrator password</label>
              <input required minLength={12} type="password" value={password} onChange={e => setPassword(e.target.value)} className="w-full h-12 rounded-xl border border-slate-300 bg-white px-4 text-sm outline-none focus:border-slate-900 focus:ring-4 focus:ring-slate-900/5" />
            </div>
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1">Confirm password</label>
              <input required minLength={12} type="password" value={confirm} onChange={e => setConfirm(e.target.value)} className="w-full h-12 rounded-xl border border-slate-300 bg-white px-4 text-sm outline-none focus:border-slate-900 focus:ring-4 focus:ring-slate-900/5" />
            </div>
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1">One-time setup token</label>
              <input required type="password" value={token} onChange={e => setToken(e.target.value)} className="w-full h-12 rounded-xl border border-slate-300 bg-white px-4 text-sm outline-none focus:border-slate-900 focus:ring-4 focus:ring-slate-900/5" />
            </div>
            {error && <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs font-semibold">{error}</div>}
            <button disabled={loading} className="w-full h-12 rounded-xl bg-slate-950 hover:bg-slate-800 text-white font-semibold flex items-center justify-center gap-2 disabled:opacity-50">
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <><KeyRound className="w-4 h-4" /> Synchronize Administrator</>}
            </button>
          </form>
        )}
        <p className="text-center text-xs text-slate-500">This does not use email password recovery. The password is synchronized directly with Supabase Auth.</p>
      </div>
    </div>
  );
}