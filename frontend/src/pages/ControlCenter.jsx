import { useCallback, useEffect, useMemo, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import MainLayout from '../layouts/MainLayout';
import api from '../api/axios';

const config = {
  payroll: { title: 'Payroll & Salary', endpoint: '/erp/payroll' },
  accounts: { title: 'Accounts & GST', endpoint: '/erp/accounts' },
  compliance: { title: 'Compliance', endpoint: '/erp/compliance' },
  risks: { title: 'Risk & Controls', endpoint: '/erp/risks' },
};
const money = value => value == null ? '—' : Number(value).toLocaleString('en-IN', { maximumFractionDigits: 2 });
const failure = error => typeof error.response?.data?.detail === 'string' ? error.response.data.detail : 'The records could not be loaded. Please retry.';

export default function ControlCenter({ type }) {
  const cfg = config[type] || config.payroll;
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    setLoading(true); setError('');
    try { setData((await api.get(cfg.endpoint)).data); }
    catch (err) { setError(failure(err)); }
    finally { setLoading(false); }
  }, [cfg.endpoint]);
  useEffect(() => { setData(null); load(); }, [load]);
  const sections = useMemo(() => {
    if (!data) return [];
    if (type === 'accounts') return [{ title: 'Invoices', rows: data.invoices || [] }, { title: 'Expenses', rows: data.expenses || [] }, { title: 'GST collection ledger', rows: data.gst_collection || [] }, { title: 'GST ITC ledger', rows: data.gst_itc || [] }];
    if (type === 'compliance') return [{ title: 'Employee documents', rows: data.employee_documents || [] }, { title: 'Corporate compliance', rows: data.corporate || [] }];
    return [{ title: type === 'risks' ? 'Risk register' : 'Salary records', rows: Array.isArray(data) ? data : (data.salary_records || data.risks || []) }];
  }, [data, type]);

  return <MainLayout><div className="space-y-5">
    <header className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Company records</p><h1 className="mt-1 text-2xl font-semibold text-slate-900">{cfg.title}</h1><p className="mt-2 text-sm text-slate-500">Review the saved operational records available to your account.</p></div>
      <button disabled={loading} onClick={load} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 disabled:opacity-50"><RefreshCw size={16}/>Refresh</button></header>
    {type === 'accounts' && <p className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs leading-5 text-slate-600">These operational registers do not represent the complete general ledger or a filed GST return. The designated MD account can review posted bookkeeping and financial statements in Company Money.</p>}
    {error && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{error}{data ? ' Previously loaded records remain below.' : ''}</p>}
    {loading && !data && <p role="status" className="rounded-xl border border-slate-200 bg-white p-10 text-center text-sm text-slate-500">Loading records…</p>}
    {sections.map(section => <section key={section.title} className="overflow-hidden rounded-xl border border-slate-200 bg-white">
      <div className="flex justify-between gap-3 border-b border-slate-200 px-4 py-4"><h2 className="text-sm font-semibold text-slate-900">{section.title}</h2><span className="text-xs text-slate-500">{section.rows.length} records</span></div>
      <div className="overflow-auto"><table className="w-full text-left text-xs"><thead className="bg-slate-50 text-slate-500"><tr>{['Record', 'Status', 'Date / month', 'Amount / detail'].map(label => <th key={label} className="px-4 py-3 font-medium">{label}</th>)}</tr></thead><tbody>
        {section.rows.map((row, index) => <tr key={row.id || index} className="border-t border-slate-100"><td className="px-4 py-4 font-medium text-slate-900">{row.name || row.company_name || row.employee_code || row.invoice_number || row.category || row.compliance_type || row.description || row.account_type || row.document_type || row.trigger_code || 'Record'}</td><td className="px-4 py-4 text-slate-600">{row.lifecycle_status || row.status || row.reconciliation_status || row.clearance_status || row.severity || '—'}</td><td className="px-4 py-4 text-slate-500">{row.payroll_month || row.month || row.due_date || row.expense_date || row.issue_date || row.entry_date || row.expiry_date || row.detected_at || '—'}</td><td className="px-4 py-4 text-slate-600">{row.net_pay != null ? money(row.net_pay) : row.total_amount != null ? money(row.total_amount) : row.amount != null ? money(row.amount) : row.gst_amount != null ? money(row.gst_amount) : row.description || row.reason || '—'}</td></tr>)}
        {!section.rows.length && <tr><td colSpan="4" className="p-8 text-center text-slate-500">No saved records in this register.</td></tr>}
      </tbody></table></div>
    </section>)}
  </div></MainLayout>;
}
