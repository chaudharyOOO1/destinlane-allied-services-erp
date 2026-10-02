import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import api from '../api/axios';
import MainLayout from '../layouts/MainLayout';

export default function AccountSettings() {
  const { user, logout } = useAuth();
  const [form, setForm] = useState({ current_password:'', new_password:'', confirm:'' });
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const update = e => setForm(f => ({...f, [e.target.name]:e.target.value}));
  async function submit(e){
    e.preventDefault(); setMessage(''); setError('');
    if(form.new_password.length < 12) return setError('New password must be at least 12 characters.');
    if(form.new_password !== form.confirm) return setError('New passwords do not match.');
    try { await api.post('/auth/change-password',{current_password:form.current_password,new_password:form.new_password}); setMessage('Password changed successfully.'); setForm({current_password:'',new_password:'',confirm:''}); }
    catch(err){ setError(err?.response?.data?.detail || 'Unable to change password.'); }
  }
  return <MainLayout><div className="max-w-xl"><h1 className="text-2xl font-bold text-slate-950">Account</h1><p className="mt-1 text-sm text-slate-500">Manage your DestinLane Portal credentials.</p><div className="mt-6 bg-white border border-slate-200 rounded-2xl p-6"><div className="mb-6"><p className="text-sm font-semibold text-slate-900">{user?.full_name}</p><p className="text-xs text-slate-500 mt-1">{user?.login_id} · {user?.role}</p></div><form onSubmit={submit} className="space-y-4"><input name="current_password" type="password" value={form.current_password} onChange={update} placeholder="Current password" required className="w-full h-11 px-3 rounded-xl border border-slate-300"/><input name="new_password" type="password" value={form.new_password} onChange={update} placeholder="New password (12+ characters)" required className="w-full h-11 px-3 rounded-xl border border-slate-300"/><input name="confirm" type="password" value={form.confirm} onChange={update} placeholder="Confirm new password" required className="w-full h-11 px-3 rounded-xl border border-slate-300"/>{error&&<p className="text-sm text-rose-600">{error}</p>}{message&&<p className="text-sm text-emerald-600">{message}</p>}<button className="h-11 px-5 rounded-xl bg-slate-950 text-white text-sm font-semibold">Change password</button></form><button onClick={logout} className="mt-5 text-sm text-rose-600">Sign out</button></div></div></MainLayout>;
}
