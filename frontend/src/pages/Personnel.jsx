import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, RefreshCw, Search } from 'lucide-react';
import MainLayout from '../layouts/MainLayout';
import { useAccess } from '../context/AccessContext';
import api from '../api/axios';

const verticals = ['SECURITY', 'HOUSEKEEPING', 'NURSING'];
const categories = {
  SECURITY: ['GUARD', 'GUNMAN', 'SUPERVISOR', 'FIELD_OFFICER'],
  HOUSEKEEPING: ['JANITOR', 'CLEANER', 'FACILITY_ATTENDANT'],
  NURSING: ['GDA', 'NURSE_ASSISTANT', 'HOSPITAL_ATTENDANT'],
};
const empty = () => ({ full_name: '', phone: '', vertical: 'SECURITY', category: 'GUARD' });
const input = 'mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm';
const button = 'inline-flex items-center justify-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50';
const failure = error => typeof error.response?.data?.detail === 'string' ? error.response.data.detail : 'Unable to complete the request. Check your connection and retry.';

export default function Personnel() {
  const { can } = useAccess();
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [warning, setWarning] = useState('');
  const [form, setForm] = useState(empty);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('ALL');
  const action = useRef(false);
  const load = useCallback(async () => {
    const { data } = await api.get('/erp/recruitment');
    setCandidates(data || []);
  }, []);
  const refresh = useCallback(async () => {
    setLoading(true);
    setError('');
    try { await load(); } catch (err) { setError(failure(err)); }
    finally { setLoading(false); }
  }, [load]);
  useEffect(() => { refresh(); }, [refresh]);

  async function mutate(work, success) {
    if (action.current) return;
    action.current = true;
    setBusy(true);
    setError(''); setMessage(''); setWarning('');
    try {
      const saved = await work();
      setCandidates(current => [saved, ...current.filter(row => row.id !== saved.id)]);
      setMessage(success);
      try { await load(); }
      catch { setWarning('The change was saved. The recruitment list could not refresh; use Refresh when the connection recovers.'); }
    } catch (err) { setError(failure(err)); }
    finally { action.current = false; setBusy(false); }
  }
  function create(event) {
    event.preventDefault();
    mutate(async () => {
      const { data } = await api.post('/erp/recruitment', form);
      setForm(empty());
      return data;
    }, 'Candidate added to the applied stage.');
  }
  const filtered = candidates.filter(candidate => (status === 'ALL' || candidate.status === status)
    && [candidate.full_name, candidate.phone, candidate.candidate_id].join(' ').toLowerCase().includes(search.toLowerCase()));

  return <MainLayout><div className="space-y-6">
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div><p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Workforce</p>
        <h1 className="mt-1 text-2xl font-semibold text-slate-900">Recruitment</h1>
        <p className="mt-2 text-sm text-slate-500">Register candidates, record verification and continue approved joining in Employee Master.</p>
      </div>
      <div className="flex flex-wrap gap-2"><button className={button} onClick={refresh} disabled={loading || busy}><RefreshCw size={16}/>Refresh</button>
        {can('employees.view') && <Link to="/employees" className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700">Employee Master</Link>}</div>
    </header>
    {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
    {message && <p role="status" className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">{message}</p>}
    {warning && <p role="status" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800">{warning}</p>}
    <div className="grid gap-4 sm:grid-cols-3">{[['Candidates', candidates.length], ['Applied', candidates.filter(row => row.status === 'APPLIED').length], ['Verified', candidates.filter(row => row.status === 'VERIFIED').length]].map(([label, value]) => <div key={label} className="rounded-xl border border-slate-200 bg-white p-4"><p className="text-xs text-slate-500">{label}</p><p className="mt-2 text-2xl font-semibold text-slate-900">{loading || error ? '—' : value}</p></div>)}</div>
    <div className={`grid items-start gap-5 ${can('recruitment.create') ? 'xl:grid-cols-[320px_minmax(0,1fr)]' : ''}`}>
      {can('recruitment.create') && <form onSubmit={create} className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="font-semibold text-slate-900">New candidate</h2>
        <fieldset disabled={busy} className="space-y-4">
          <label className="block text-sm text-slate-700">Full name<input required name="full_name" value={form.full_name} onChange={event => setForm({ ...form, full_name: event.target.value })} className={input}/></label>
          <label className="block text-sm text-slate-700">Phone<input required name="phone" type="tel" value={form.phone} onChange={event => setForm({ ...form, phone: event.target.value })} className={input}/></label>
          <label className="block text-sm text-slate-700">Service<select value={form.vertical} onChange={event => setForm({ ...form, vertical: event.target.value, category: categories[event.target.value][0] })} className={input}>{verticals.map(value => <option key={value} value={value}>{value === 'NURSING' ? 'HEALTHCARE' : value}</option>)}</select></label>
          <label className="block text-sm text-slate-700">Category<select value={form.category} onChange={event => setForm({ ...form, category: event.target.value })} className={input}>{categories[form.vertical].map(value => <option key={value}>{value}</option>)}</select></label>
        </fieldset>
        <button className={button + ' w-full'} disabled={busy}><Plus size={16}/>{busy ? 'Saving…' : 'Add candidate'}</button>
      </form>}
      <section className="min-w-0 overflow-hidden rounded-xl border border-slate-200 bg-white">
        <div className="flex flex-wrap gap-3 border-b border-slate-200 p-4"><label className="flex min-w-40 flex-1 items-center gap-2"><Search size={16} className="text-slate-400"/><input aria-label="Search candidates" placeholder="Search name, ID or phone" value={search} onChange={event => setSearch(event.target.value)} className="w-full bg-white text-sm outline-none"/></label>
          <select aria-label="Candidate status" value={status} onChange={event => setStatus(event.target.value)} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm">{['ALL', 'APPLIED', 'VERIFIED', 'ONBOARDED'].map(value => <option key={value}>{value}</option>)}</select></div>
        <div className="overflow-auto"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-xs text-slate-500"><tr>{['Candidate', 'Service / category', 'Status', 'Next step'].map(value => <th key={value} className="px-4 py-3">{value}</th>)}</tr></thead><tbody>
          {filtered.map(candidate => <tr key={candidate.id} className="border-t border-slate-100"><td className="px-4 py-4 font-medium text-slate-900">{candidate.full_name}<p className="mt-1 text-xs text-slate-500">{candidate.candidate_id} · {candidate.phone}</p></td><td className="px-4 py-4 text-xs text-slate-600">{candidate.vertical}<p>{candidate.category || 'Not specified'}</p></td><td className="px-4 py-4 text-xs text-slate-600">{candidate.status}</td><td className="px-4 py-4">
            {candidate.status === 'APPLIED' && can('recruitment.edit') && <button disabled={busy} className="text-sm font-semibold text-teal-700 disabled:opacity-50" onClick={() => mutate(async () => (await api.patch(`/erp/recruitment/${candidate.candidate_id}`, { status: 'VERIFIED' })).data, 'Candidate marked verified.')}>Mark verified</button>}
            {candidate.status === 'VERIFIED' && can('employees.create') && <Link to="/employees" state={{candidate}} className="text-sm font-semibold text-teal-700">{candidate.employee_id?'Continue joining file':'Start joining'}</Link>}
          </td></tr>)}
          {!filtered.length && <tr><td colSpan="4" className="p-8 text-center text-sm text-slate-500">{loading ? 'Loading candidates…' : error ? 'Candidate records are unavailable. Use Refresh to retry.' : candidates.length ? 'No candidates match these filters.' : 'No candidates recorded yet.'}</td></tr>}
        </tbody></table></div>
        <p className="border-t border-slate-200 p-4 text-xs leading-5 text-slate-500">Verification here records the recruitment stage. Employee IDs, documents and activation use the separate Employee Creation and joining approval workflow; recruitment does not bypass those checks.</p>
      </section>
    </div>
  </div></MainLayout>;
}
