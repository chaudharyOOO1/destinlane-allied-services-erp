import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { updateRecoveredPassword } from '../lib/supabaseAuth';

function accessTokenFromUrl() {
  const hash = new URLSearchParams(window.location.hash.replace(/^#/, ''));
  return hash.get('access_token');
}

export default function ResetPassword() {
  const navigate = useNavigate();
  const accessToken = useMemo(accessTokenFromUrl, []);
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
      await updateRecoveredPassword(accessToken, password);
      setMessage('Password updated successfully. You can now sign in with the new password.');
      setTimeout(() => navigate('/login', { replace: true }), 1200);
    } catch (err) {
      setError(err.message || 'Unable to update the password.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 flex items-center justify-center px-5 py-10">
      <div className="w-full max-w-md">
        <div className="mb-7 text-center">
          <h1 className="text-2xl font-semibold text-slate-900">DestinLane Allied Services Pvt Ltd</h1>
          <p className="mt-2 text-sm text-slate-500">Reset Password</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-7 shadow-sm sm:p-9">
          <h2 className="text-xl font-semibold text-slate-900">Set a new password</h2>
          <p className="mt-2 text-sm text-slate-500">Your new password must be at least 12 characters.</p>
          {error && <div className="mt-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
          {message && <div className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{message}</div>}
          {!message && (
            <form onSubmit={submit} className="mt-6 space-y-4">
              <div>
                <label className="mb-2 block text-sm font-semibold text-slate-700" htmlFor="new-password">New password</label>
                <input id="new-password" required minLength={12} type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="h-12 w-full rounded-xl border border-slate-300 px-4 text-sm outline-none focus:border-slate-700" />
              </div>
              <div>
                <label className="mb-2 block text-sm font-semibold text-slate-700" htmlFor="confirm-password">Confirm password</label>
                <input id="confirm-password" required minLength={12} type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} className="h-12 w-full rounded-xl border border-slate-300 px-4 text-sm outline-none focus:border-slate-700" />
              </div>
              <button disabled={loading} className="h-12 w-full rounded-xl bg-slate-900 text-sm font-semibold text-white disabled:opacity-60">
                {loading ? 'Updating...' : 'Update password'}
              </button>
            </form>
          )}
          <Link to="/login" className="mt-5 block text-center text-sm text-slate-500">Back to login</Link>
        </div>
      </div>
    </main>
  );
}
