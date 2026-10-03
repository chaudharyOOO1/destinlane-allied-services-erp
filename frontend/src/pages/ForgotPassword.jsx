import { useState } from 'react';
import { Link } from 'react-router-dom';
import { requestPasswordRecovery } from '../lib/supabaseAuth';

export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError('');
    setMessage('');
    setLoading(true);
    try {
      await requestPasswordRecovery(email.trim(), `${window.location.origin}/reset-password`);
      setMessage('If this email is registered, a password reset link has been sent. Check your inbox and spam folder.');
    } catch (err) {
      setError(err.message || 'Unable to start password recovery.');
    } finally {
      setLoading(false);
    }
  }

  return <main className="min-h-screen bg-slate-50 flex items-center justify-center px-5 py-10">
    <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-7 shadow-sm sm:p-9">
      <p className="text-sm text-slate-500">DestinLane Allied Services Pvt Ltd</p>
      <h1 className="mt-2 text-xl font-semibold text-slate-900">Reset your ERP password</h1>
      <p className="mt-2 text-sm text-slate-500">Enter the email registered to your ERP account.</p>
      {error && <div role="alert" className="mt-5 rounded-xl bg-red-50 p-4 text-sm text-red-700">{error}</div>}
      {message && <div role="status" className="mt-5 rounded-xl bg-emerald-50 p-4 text-sm text-emerald-700">{message}</div>}
      <form onSubmit={submit} className="mt-6 space-y-4">
        <label className="block text-sm font-semibold text-slate-700" htmlFor="recovery-email">Registered email</label>
        <input id="recovery-email" type="email" autoComplete="email" required value={email} onChange={event => setEmail(event.target.value)} className="h-12 w-full rounded-xl border border-slate-300 px-4 text-sm" />
        <button disabled={loading} className="h-12 w-full rounded-xl bg-slate-900 text-sm font-semibold text-white disabled:opacity-60">{loading ? 'Sending…' : 'Send reset link'}</button>
      </form>
      <Link to="/login" className="mt-5 block text-center text-sm text-slate-500">Back to login</Link>
      <Link to="/admin-recovery" className="mt-3 block text-center text-sm text-slate-500">Administrator token recovery</Link>
    </div>
  </main>;
}
