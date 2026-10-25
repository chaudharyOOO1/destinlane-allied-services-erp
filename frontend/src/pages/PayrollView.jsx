import { useCallback, useEffect, useRef, useState } from 'react';
import StaffMonthlyPay from '../components/StaffMonthlyPay';
import PayrollWages from '../components/PayrollWages';
import MainLayout from '../layouts/MainLayout';
import api from '../api/axios';
import { useAccess } from '../context/AccessContext';
import { Calculator, Download, Lock, RefreshCw } from 'lucide-react';

const money = value => value == null ? '—' : Number(value).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const failure = error => typeof error.response?.data?.detail === 'string' ? error.response.data.detail : 'Unable to complete the request. Check your connection and retry.';
const thisMonth = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata', year: 'numeric', month: '2-digit' }).format(new Date()).slice(0, 7);

export default function PayrollView() {
  const { can } = useAccess();
  const [month, setMonth] = useState(thisMonth);
  const [rows, setRows] = useState([]);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [warning, setWarning] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [staffBusy,setStaffBusy] = useState(false);
  const [wageBusy,setWageBusy] = useState(false);
  const working = busy || staffBusy || wageBusy;
  const action = useRef(false);
  const generation = useRef(0);
  const load = useCallback(async () => {
    const requestId = ++generation.current;
    setLoading(true);
    try {
      const { data } = await api.get('/erp/payroll', { params: { month } });
      if (requestId === generation.current) setRows(data || []);
    } finally { if (requestId === generation.current) setLoading(false); }
  }, [month]);
  useEffect(() => {
    setRows([]); setError(''); setMessage(''); setWarning('');
    load().catch(err => setError(failure(err)));
    return () => { generation.current++; };
  }, [load]);
  async function act(work) {
    if (action.current) return;
    action.current = true; setBusy(true); setError(''); setMessage(''); setWarning('');
    try { await work(); }
    catch (err) { setError(failure(err)); }
    finally { action.current = false; setBusy(false); }
  }
  async function refreshSaved() {
    try { await load(); }
    catch { setWarning('The change was saved. Payroll records could not refresh; use Refresh to load the latest status.'); }
  }
  const calculate = () => act(async () => {
    const { data } = await api.post('/erp/payroll/calculate', { month });
    setMessage(`${data.employees_processed} employee(s) calculated; ${data.salary_holds} held.`);
    await refreshSaved();
  });
  function hold(id) {
    const reason = window.prompt('Salary hold reason', 'Manual Flag');
    if (!reason?.trim()) return;
    const note = window.prompt('Required audit note');
    if (!note?.trim()) return;
    act(async () => {
      await api.post(`/erp/payroll/${id}/hold`, { reason: reason.trim(), audit_note: note.trim() });
      setRows(current => current.map(row => row.id === id ? { ...row, lifecycle_status: 'HELD' } : row));
      setMessage('Salary hold saved with the audit note.');
      await refreshSaved();
    });
  }
  const pdf = (id, code) => act(async () => {
    const { data } = await api.get(`/erp/payroll/slips/${id}/pdf`, { responseType: 'blob' });
    const url = URL.createObjectURL(data);
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = `salary-slip-${code}.pdf`; anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  return <MainLayout><div className="space-y-5">
    <header className="flex flex-wrap items-start justify-between gap-4"><div><h1 className="text-2xl font-semibold text-slate-900">Payroll</h1><p className="mt-2 text-sm text-slate-500">Review attendance-based salary, configured deductions, salary holds and payslips.</p></div>
      <div className="flex flex-wrap gap-2"><input aria-label="Payroll month" type="month" value={month} disabled={working} onChange={event => setMonth(event.target.value)} className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm"/>
        {can('payroll.create') && <button onClick={calculate} disabled={working || loading || !month} className="inline-flex h-10 items-center gap-2 rounded-lg bg-slate-900 px-4 text-sm font-semibold text-white disabled:opacity-50"><Calculator size={16}/>{working ? 'Working…' : 'Calculate payroll'}</button>}
        <button onClick={() => act(async () => { await load(); })} disabled={working || loading} aria-label="Refresh payroll" className="rounded-lg border border-slate-200 bg-white p-2 disabled:opacity-50"><RefreshCw size={18}/></button>
      </div></header>
    {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
    {message && <p role="status" className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">{message}</p>}
    {warning && <p role="status" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800">{warning}</p>}
    <p className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs leading-5 text-slate-600">Calculations use completed, verified attendance and the current payroll rules. Accounts must review wages, deductions and statutory treatment before salary payment. A calculated payslip does not confirm a bank payment.</p>
    <StaffMonthlyPay month={month} onBusyChange={setStaffBusy}/>
    <PayrollWages canEdit={can('payroll.create')} onBusyChange={setWageBusy}/>
    <div className="overflow-auto rounded-xl border border-slate-200 bg-white"><table className="w-full text-left text-xs"><thead className="bg-slate-50 text-slate-500"><tr>{['Employee', 'Present', 'OT hours', 'Gross (₹)', 'PF (₹)', 'ESIC (₹)', 'LWF (₹)', 'Uniform (₹)', 'Net (₹)', 'Status', 'Actions'].map(label => <th key={label} className="whitespace-nowrap p-3 font-medium">{label}</th>)}</tr></thead><tbody>
      {rows.map(row => <tr key={row.id} className="border-t border-slate-100 text-slate-700"><td className="p-3"><strong className="text-slate-900">{row.name}</strong><p className="mt-1 text-xs text-slate-500">{row.employee_code}</p></td><td className="p-3">{row.present_days}</td><td className="p-3">{row.overtime_hours}</td>{['gross_pay', 'pf', 'esic', 'lwf', 'uniform_emi', 'net_pay'].map(key => <td key={key} className={`whitespace-nowrap p-3 tabular-nums ${key === 'net_pay' ? 'font-semibold' : ''}`}>{money(row[key])}</td>)}<td className="p-3"><span className={row.lifecycle_status === 'HELD' ? 'font-semibold text-rose-700' : 'text-slate-600'}>{row.lifecycle_status}</span></td><td className="p-3"><div className="flex gap-1"><button onClick={() => pdf(row.id, row.employee_code)} disabled={working} title="Download payslip" aria-label={`Download payslip for ${row.employee_code}`} className="rounded-lg border border-slate-200 p-2 disabled:opacity-50"><Download size={15}/></button>{can('payroll.create') && <button onClick={() => hold(row.id)} disabled={working || ['HELD','APPROVED','DISBURSED','PAID'].includes(row.lifecycle_status)} title="Place salary hold" aria-label={`Place salary hold for ${row.employee_code}`} className="rounded-lg border border-slate-200 p-2 disabled:opacity-50"><Lock size={15}/></button>}</div></td></tr>)}
      {!rows.length && <tr><td colSpan="11" className="p-10 text-center text-sm text-slate-500">{loading ? 'Loading payroll…' : error ? 'Payroll records are unavailable. Use Refresh to retry.' : 'No payroll slips have been calculated for this month.'}</td></tr>}
    </tbody></table></div>
  </div></MainLayout>;
}
