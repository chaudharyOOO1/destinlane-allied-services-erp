import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import api from '../api/axios';

export default function AdminRecovery() {
  const navigate = useNavigate();
  const [token, setToken] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError('');
    setMessage('');
    if (password.length < 12) return setError('Password must be at least 12 characters.');
    if (password !== confirm) return setError('Passwords do not match.');
    setLoading(true);
    try {
      await api.post('/auth/admin-recover-password', {
        recovery_token: token.trim(),
        login_id: 'ADMIN-001',
        new_password: password,
      });
      setMessage('Administrator password reset successfully. Redirecting to login...');
      setTimeout(() => navigate('/login', { replace: true }), 1200);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Administrator recovery failed.');
    } finally {
      setLoading(false);
    }
  }

  return <main className="min-h-screen bg-slate-50 flex items-center justify-center px-5 py-10">
    <div className="w-full max-w-md">
      <div className="mb-7 text-center">
        <h1 className="text-2xl font-semibold text-slate-900">DestinLane Allied Services Pvt Ltd</h1>
        <p className="mt-2 text-sm text-slate-500">Administrator Recovery</p>
      </div>
      <div className="rounded-2xl border border-slate-200 bg-white p-7 shadow-sm sm:p-9">
        <h2 className="text-xl font-semibold text-slate-900">Reset ADMIN-001 password</h2>
        <p className="mt-2 text-sm text-slate-500">This recovery path does not use email. Enter the administrator recovery token and choose a new password.</p>
        {error && <div className="mt-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
        {message && <div className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{message}</div>}
        <form onSubmit={submit} className="mt-6 space-y-4">
          <label className="block text-sm font-semibold text-slate-700">Administrator recovery token
            <input required type="password" value={token} onChange={e=>setToken(e.target.value)} className="mt-2 h-12 w-full rounded-xl border border-slate-300 px-4 text-sm outline-none focus:border-slate-700" />
          </label>
          <label className="block text-sm font-semibold text-slate-700">New password
            <input required type="password" minLength={12} value={password} onChange={e=>setPassword(e.target.value)} className="mt-2 h-12 w-full rounded-xl border border-slate-300 px-4 text-sm outline-none focus:border-slate-700" />
          </label>
          <label className="block text-sm font-semibold text-slate-700">Confirm new password
            <input required type="password" minLength={12} value={confirm} onChange={e=>setConfirm(e.target.value)} className="mt-2 h-12 w-full rounded-xl border border-slate-300 px-4 text-sm outline-none focus:border-slate-700" />
          </label>
          <button disabled={loading} className="h-12 w-full rounded-xl bg-slate-900 text-sm font-semibold text-white disabled:opacity-60">{loading?'Resetting...':'Reset administrator password'}</button>
        </form>
        <Link to="/login" className="mt-5 block text-center text-sm text-slate-500">Back to login</Link>
      </div>
    </div>
  </main>;
}