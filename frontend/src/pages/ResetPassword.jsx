import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import api from '../api/axios';

function recoveryTokenFromUrl() {
  const hash = new URLSearchParams(window.location.hash.replace(/^#/, ''));
  const query = new URLSearchParams(window.location.search);
  return hash.get('access_token') || query.get('access_token');
}

export default function ResetPassword() {
  const navigate = useNavigate();
  const [accessToken] = useState(recoveryTokenFromUrl);
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState(accessToken ? '' : 'This password reset link is missing or has expired.');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError('');
    setMessage('');
    if (!accessToken) return setError('This password reset link is missing or has expired.');
    if (password.length < 12) return setError('Password must be at least 12 characters.');
    if (password !== confirm) return setError('Passwords do not match.');
    setLoading(true);
    try {
      await api.post('/auth/reset-password', { access_token: accessToken, new_password: password });
      window.history.replaceState(null, '', '/reset-password');
      setPassword('');
      setConfirm('');
      setMessage('ERP password updated successfully. You can now sign in with the new password.');
      setTimeout(() => navigate('/login', { replace: true }), 1200);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Unable to update the password.');
    } finally {
      setLoading(false);
    }
  }

  return <main className="min-h-screen bg-slate-50 flex items-center justify-center px-5 py-10">
    <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-7 shadow-sm sm:p-9">
      <p className="text-sm text-slate-500">DestinLane Allied Services Pvt Ltd</p>
      <h1 className="mt-2 text-xl font-semibold text-slate-900">Set a new ERP password</h1>
      <p className="mt-2 text-sm text-slate-500">Your new password must be at least 12 characters.</p>
      {error && <div role="alert" className="mt-5 rounded-xl bg-red-50 p-4 text-sm text-red-700">{error}</div>}
      {message && <div role="status" className="mt-5 rounded-xl bg-emerald-50 p-4 text-sm text-emerald-700">{message}</div>}
      {!message && <form onSubmit={submit} className="mt-6 space-y-4">
        <label className="block text-sm font-semibold text-slate-700" htmlFor="new-password">New password</label>
        <input id="new-password" required minLength={12} autoComplete="new-password" type="password" value={password} onChange={event => setPassword(event.target.value)} className="h-12 w-full rounded-xl border border-slate-300 px-4 text-sm" />
        <label className="block text-sm font-semibold text-slate-700" htmlFor="confirm-password">Confirm new password</label>
        <input id="confirm-password" required minLength={12} autoComplete="new-password" type="password" value={confirm} onChange={event => setConfirm(event.target.value)} className="h-12 w-full rounded-xl border border-slate-300 px-4 text-sm" />
        <button disabled={loading || !accessToken} className="h-12 w-full rounded-xl bg-slate-900 text-sm font-semibold text-white disabled:opacity-60">{loading ? 'Updating…' : 'Update password'}</button>
      </form>}
      <Link to="/login" className="mt-5 block text-center text-sm text-slate-500">Back to login</Link>
    </div>
  </main>;
}
