import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/axios';

export default function AdminSetup() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ setup_token:'', login_id:'ADMIN-001', password:'', confirm:'' });
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const update = e => setForm(f => ({ ...f, [e.target.name]: e.target.value }));
  async function submit(e) {
    e.preventDefault(); setError(''); setMessage('');
    if (form.password !== form.confirm) return setError('Passwords do not match.');
    if (form.password.length < 12) return setError('Password must be at least 12 characters.');
    setSaving(true);
    try { await api.post('/auth/setup-admin', { setup_token:form.setup_token, login_id:form.login_id, password:form.password }); setMessage('Administrator activated. You can now sign in.'); setTimeout(() => navigate('/login'), 900); }
    catch(err){ setError(err?.response?.data?.detail || 'Administrator setup failed.'); }
    finally{ setSaving(false); }
  }
  return <div className="min-h-screen bg-slate-50 flex items-center justify-center px-4"><form onSubmit={submit} className="w-full max-w-md bg-white border border-slate-200 rounded-2xl shadow-sm p-7 space-y-5"><div><p className="text-xs uppercase tracking-[0.18em] text-slate-400">DestinLane Allied Services</p><h1 className="text-2xl font-bold text-slate-950 mt-2">Administrator activation</h1></div><input name="setup_token" value={form.setup_token} onChange={update} placeholder="Setup token" required className="w-full h-11 px-3 rounded-xl border border-slate-300"/><input name="login_id" value={form.login_id} onChange={update} placeholder="Login ID" required className="w-full h-11 px-3 rounded-xl border border-slate-300"/><input name="password" type="password" value={form.password} onChange={update} placeholder="New password (12+ characters)" required className="w-full h-11 px-3 rounded-xl border border-slate-300"/><input name="confirm" type="password" value={form.confirm} onChange={update} placeholder="Confirm password" required className="w-full h-11 px-3 rounded-xl border border-slate-300"/>{error&&<p className="text-sm text-rose-600">{error}</p>}{message&&<p className="text-sm text-emerald-600">{message}</p>}<button disabled={saving} className="w-full h-11 rounded-xl bg-slate-950 text-white font-semibold disabled:opacity-60">{saving?'Activating…':'Activate administrator'}</button><button type="button" onClick={()=>navigate('/login')} className="w-full text-sm text-slate-500">Back to login</button></form></div>;
}
