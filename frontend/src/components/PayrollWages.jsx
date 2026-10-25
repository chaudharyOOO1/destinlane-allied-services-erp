import { useEffect, useRef, useState } from 'react';
import api from '../api/axios';

const failure = error => typeof error.response?.data?.detail === 'string' ? error.response.data.detail : 'Unable to save the wage. Check the fields and retry.';

export default function PayrollWages({ canEdit }) {
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState({ employee_id: '', effective_from: '', daily_rate: '', reason: '' });
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const action = useRef(false);
  useEffect(() => {
    let active = true;
    api.get('/erp/payroll/wages').then(({ data }) => { if (active) setRows(data); }).catch(error => { if (active) setError(failure(error)); });
    return () => { active = false; };
  }, []);
  const employees = [...new Map(rows.map(row => [row.employee_id, row])).values()];
  async function save(event) {
    event.preventDefault();
    if (action.current) return;
    action.current = true; setBusy(true); setError(''); setMessage('');
    try {
      const { data } = await api.post('/erp/payroll/wages', form);
      const employee = employees.find(row => row.employee_id === data.employee_id);
      setRows(current => [{ ...employee, ...data }, ...current.filter(row => row.id)]);
      setMessage('Wage saved. Calculate an unfinalised payroll month to apply the effective rate.');
      setForm(current => ({ ...current, daily_rate: '', reason: '' }));
    } catch (error) { setError(failure(error)); }
    finally { action.current = false; setBusy(false); }
  }
  return <details className="rounded-xl border border-slate-200 bg-white p-4">
    <summary className="cursor-pointer font-semibold text-slate-900">Employee wage setup</summary>
    <p className="mt-2 text-sm text-slate-500">Set wages paid to employees separately from client billing rates. New effective dates preserve wage history.</p>
    {error && <p role="alert" className="mt-3 text-sm text-rose-700">{error}</p>}
    {message && <p role="status" className="mt-3 text-sm text-emerald-700">{message}</p>}
    {canEdit && <form onSubmit={save} className="mt-4 grid gap-3 sm:grid-cols-2">
      <label className="text-sm">Employee<select required aria-label="Wage employee" value={form.employee_id} onChange={e => setForm({ ...form, employee_id: e.target.value })} className="mt-1 w-full rounded-lg border p-2"><option value="">Choose employee</option>{employees.map(row => <option key={row.employee_id} value={row.employee_id}>{row.employee_code} · {row.name}</option>)}</select></label>
      <label className="text-sm">Effective from<input required type="date" value={form.effective_from} onChange={e => setForm({ ...form, effective_from: e.target.value })} className="mt-1 w-full rounded-lg border p-2"/></label>
      <label className="text-sm">Daily wage (₹)<input required type="number" min="0.01" max="99999999" step="0.01" value={form.daily_rate} onChange={e => setForm({ ...form, daily_rate: e.target.value })} className="mt-1 w-full rounded-lg border p-2"/></label>
      <label className="text-sm">Reason / approval reference<input required minLength={5} maxLength={1000} value={form.reason} onChange={e => setForm({ ...form, reason: e.target.value })} className="mt-1 w-full rounded-lg border p-2"/></label>
      <button disabled={busy} className="w-fit rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{busy ? 'Saving…' : 'Save wage'}</button>
    </form>}
    <div className="mt-4 overflow-auto"><table className="w-full text-left text-sm"><thead><tr>{['Employee', 'Effective date', 'Daily wage (₹)', 'Reason'].map(label => <th key={label} className="p-2">{label}</th>)}</tr></thead><tbody>{rows.filter(row => row.id).map(row => <tr key={row.id} className="border-t"><td className="p-2">{row.employee_code} · {row.name}</td><td className="p-2">{row.effective_from}</td><td className="p-2">{row.daily_rate}</td><td className="p-2">{row.reason}</td></tr>)}</tbody></table>{!rows.some(row => row.id) && <p className="p-3 text-sm text-slate-500">No wage rates have been configured.</p>}</div>
  </details>;
}
