import { useCallback, useEffect, useRef, useState } from 'react';
import MainLayout from '../layouts/MainLayout';
import { useAuth } from '../context/AuthContext';
import { useAccess } from '../context/AccessContext';
import api from '../api/axios';

const base = '/erp/travel-expenses';
const inputClass = 'mt-1 w-full rounded-lg border border-slate-300 bg-white p-2 text-sm';
const today = () => new Intl.DateTimeFormat('en-CA', {timeZone:'Asia/Kolkata'}).format(new Date());
const newItem = () => ({date:today(), category:'TRANSPORT', description:'', amount:'', bill_number:''});
const newClaim = () => ({purpose:'', origin:'', destination:'', start_date:today(), end_date:today(), branch:'', missing_receipt_reason:'', items:[newItem()]});
const money = value => new Intl.NumberFormat('en-IN', {style:'currency', currency:'INR'}).format(Number(value || 0));
function errorText(error) {
  const detail = error?.response?.data?.detail;
  if (Array.isArray(detail)) return detail.map(item => item.msg).join(' ');
  return typeof detail === 'string' ? detail : 'Unable to confirm this action. Check the existing claim before retrying.';
}
function editableProfile(row) {
  return Object.fromEntries(Object.keys(newClaim()).map(key => [key, row[key]]));
}

export default function TravelExpenses() {
  const {user} = useAuth();
  const {can} = useAccess();
  const [rows, setRows] = useState([]);
  const [hasMore, setHasMore] = useState(false);
  const [scope, setScope] = useState('mine');
  const [status, setStatus] = useState('');
  const [options, setOptions] = useState({branches:[]});
  const [record, setRecord] = useState(null);
  const [form, setForm] = useState(null);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const listRequestRef = useRef(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [warning, setWarning] = useState('');
  const [remarks, setRemarks] = useState('');
  const [payment, setPayment] = useState({payment_date:today(), payment_reference:''});
  const [file, setFile] = useState(null);
  const fileRef = useRef(null);
  const own = !record || record.requester_id === user.id;
  const editable = own && (!record || ['DRAFT','REJECTED'].includes(record.status)) && can(record ? 'travel_expenses.edit' : 'travel_expenses.create');
  const reviewer = can('travel_expenses.approve') || can('travel_expenses.pay');
  const total = form?.items.reduce((sum, item) => sum + Math.round(Number(item.amount || 0) * 100), 0) / 100;

  const loadList = useCallback(async () => {
    const request = ++listRequestRef.current;
    const {data} = await api.get(base, {params:{scope, status}});
    if (request === listRequestRef.current) {
      setRows(data.claims); setHasMore(data.has_more);
    }
  }, [scope, status]);
  useEffect(() => {
    let active = true;
    loadList().catch(err => {if (active) setError(errorText(err));}).finally(() => {if (active) setLoading(false);});
    return () => {active = false;};
  }, [loadList]);
  useEffect(() => {api.get(`${base}/options`).then(({data}) => setOptions(data)).catch(err => setError(errorText(err)));}, []);

  function show(data) {
    setRecord(data); setForm(editableProfile(data)); setDirty(false); setRemarks(''); setFile(null);
    if (fileRef.current) fileRef.current.value = '';
  }
  function update(key, value) {setForm(previous => ({...previous, [key]:value})); setDirty(true);}
  function updateItem(index, key, value) {update('items', form.items.map((item, i) => i === index ? {...item, [key]:value} : item));}
  function discardAllowed() {return !dirty || window.confirm('Discard unsaved travel claim changes?');}
  function create() {
    if (busyRef.current || !discardAllowed()) return;
    setRecord(null); setForm(newClaim()); setDirty(false); setFile(null); setError(''); setMessage(''); setWarning('');
  }
  async function open(id) {
    if (busyRef.current || !discardAllowed()) return;
    busyRef.current = true; setBusy(true); setError(''); setMessage(''); setWarning('');
    try {show((await api.get(`${base}/${id}`)).data);} catch(err) {setError(errorText(err));}
    finally {busyRef.current = false; setBusy(false);}
  }
  async function mutate(request, success) {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true); setError(''); setMessage(''); setWarning('');
    try {
      const {data} = await request();
      // Keep the confirmed response even when a later directory refresh fails.
      show(data); setMessage(success);
      try {await loadList();} catch {setWarning('Changes saved, but the directory could not refresh. Refresh the list before relying on it.');}
    } catch(err) {setError(errorText(err));}
    finally {busyRef.current = false; setBusy(false);}
  }
  function save(event) {
    event.preventDefault();
    return mutate(() => record ? api.put(`${base}/${record.id}`, {...form, version:record.version}) : api.post(base, form), 'Travel draft saved.');
  }
  function submit() {return mutate(() => api.post(`${base}/${record.id}/submit`, {version:record.version}), 'Travel claim submitted for approval.');}
  function decide(decision) {return mutate(() => api.post(`${base}/${record.id}/decision`, {version:record.version, decision, remarks}), decision === 'APPROVE' ? 'Travel claim approved.' : 'Claim rejected with remarks. The requester can correct and resubmit it.');}
  function pay(event) {
    event.preventDefault();
    return mutate(() => api.post(`${base}/${record.id}/pay`, {...payment, version:record.version}), 'Reimbursement recorded and posted to Accounts.');
  }
  function upload(event) {
    event.preventDefault();
    const body = new FormData(); body.append('version', record.version); body.append('file', file);
    return mutate(() => api.post(`${base}/${record.id}/receipts`, body, {headers:{'Content-Type':'multipart/form-data'}}), 'Receipt attached.');
  }
  async function viewReceipt(id) {
    setError('');
    try {
      const {data} = await api.get(`${base}/${record.id}/receipts/${id}/sign`);
      window.open(data.url, '_blank', 'noopener,noreferrer');
    } catch(err) {setError(errorText(err));}
  }

  return <MainLayout><div className="space-y-5">
    <header className="flex flex-wrap items-center justify-between gap-3"><div><h1 className="text-2xl font-semibold">Travel Expenses</h1><p className="text-sm text-slate-500">Travel claims, receipts, approvals and reimbursement · INR</p></div>{can('travel_expenses.create') && <button disabled={busy} onClick={create} className="rounded-lg bg-slate-900 px-4 py-2 text-white">New travel claim</button>}</header>
    {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
    {message && <p role="status" className="rounded-lg bg-teal-50 p-3 text-sm text-teal-800">{message}</p>}
    {warning && <p role="status" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">{warning}</p>}
    <section className="rounded-xl border bg-white p-4">
      <div className="mb-4 flex flex-wrap gap-3"><label className="text-sm">Claims<select aria-label="Claim scope" disabled={busy} value={scope} onChange={event => {setLoading(true);setError('');setScope(event.target.value);}} className={inputClass}><option value="mine">My claims</option>{reviewer && <option value="all">All claims / approval and payment queue</option>}</select></label><label className="text-sm">Status<select aria-label="Claim status" disabled={busy} value={status} onChange={event => {setLoading(true);setError('');setStatus(event.target.value);}} className={inputClass}><option value="">All statuses</option>{['DRAFT','SUBMITTED','APPROVED','REJECTED','PAID'].map(value => <option key={value}>{value}</option>)}</select></label><button disabled={busy || loading} onClick={() => {setError('');loadList().catch(err => setError(errorText(err)));}} className="self-end rounded-lg border px-3 py-2 text-sm">Refresh list</button></div>
      {loading ? <p>Loading travel claims…</p> : <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr>{['Claim / requester','Travel','Amount','Status',''].map((label, i) => <th key={i} className="p-2">{label}</th>)}</tr></thead><tbody>{rows.map(row => <tr key={row.id} className="border-t"><td className="p-2">{row.claim_code}<p className="text-xs text-slate-500">{row.requester_name}</p></td><td className="p-2">{row.origin} → {row.destination}<p className="text-xs text-slate-500">{row.start_date} – {row.end_date}</p></td><td className="p-2">{money(row.total_amount)}</td><td className="p-2">{row.status}</td><td className="p-2"><button disabled={busy} onClick={() => open(row.id)} className="text-teal-700">Open</button></td></tr>)}</tbody></table>{!rows.length && <p className="py-4 text-sm text-slate-500">No travel claims found.</p>}</div>}
      {hasMore && <p className="mt-3 text-sm text-amber-800">Showing the latest 200 matching claims. Filter by status to narrow the list.</p>}
    </section>
    {form && <section className="space-y-5 rounded-xl border bg-white p-5" aria-label="Travel claim details">
      <h2 className="text-lg font-semibold">{record ? `${record.claim_code} · ${record.status}` : 'New travel claim'}</h2>
      {record && <p className="text-sm text-slate-500">Requested by {record.requester_name}. Total: {money(record.total_amount)}</p>}
      <form onSubmit={save} className="space-y-4"><fieldset disabled={busy || !editable} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">{[['purpose','Business purpose',500],['origin','From',150],['destination','To',150]].map(([key,label,max]) => <label key={key} className="text-sm">{label}<input aria-label={label} required minLength={key === 'purpose' ? 3 : 2} maxLength={max} value={form[key]} onChange={event => update(key,event.target.value)} className={inputClass}/></label>)}
          {[['start_date','Travel start'],['end_date','Travel end']].map(([key,label]) => <label key={key} className="text-sm">{label}<input aria-label={label} required type="date" value={form[key]} onChange={event => update(key,event.target.value)} className={inputClass}/></label>)}
          <label className="text-sm">Company branch<select aria-label="Company branch" value={form.branch} onChange={event => update('branch',event.target.value)} className={inputClass}><option value="">Head office / no branch</option>{options.branches.map(branch => <option key={branch.code} value={branch.code}>{branch.name}</option>)}{form.branch && !options.branches.some(branch => branch.code === form.branch) && <option value={form.branch}>{form.branch} (not active)</option>}</select></label>
        </div>
        <h3 className="font-medium">Expense items</h3>
        {form.items.map((item,index) => <div key={index} className="grid gap-3 rounded-lg border bg-slate-50 p-3 sm:grid-cols-2 lg:grid-cols-3">
          <label className="text-sm">Expense date<input aria-label={`Expense date ${index+1}`} type="date" required value={item.date} onChange={event => updateItem(index,'date',event.target.value)} className={inputClass}/></label>
          <label className="text-sm">Category<select aria-label={`Category ${index+1}`} value={item.category} onChange={event => updateItem(index,'category',event.target.value)} className={inputClass}>{['TRANSPORT','LODGING','MEALS','OTHER'].map(value => <option key={value}>{value}</option>)}</select></label>
          <label className="text-sm">Description<input aria-label={`Description ${index+1}`} required minLength={2} maxLength={300} value={item.description} onChange={event => updateItem(index,'description',event.target.value)} className={inputClass}/></label>
          <label className="text-sm">Amount (INR)<input aria-label={`Amount ${index+1}`} required type="number" min="0.01" max="9999999999.99" step="0.01" value={item.amount} onChange={event => updateItem(index,'amount',event.target.value)} className={inputClass}/></label>
          <label className="text-sm">Bill / ticket number<input aria-label={`Bill number ${index+1}`} maxLength={100} value={item.bill_number} onChange={event => updateItem(index,'bill_number',event.target.value)} className={inputClass}/></label>
          <button type="button" disabled={form.items.length === 1} onClick={() => update('items',form.items.filter((_,i) => i !== index))} className="self-end rounded-lg border px-3 py-2 text-sm">Remove item {index+1}</button>
        </div>)}
        <button type="button" disabled={form.items.length >= 100} onClick={() => update('items',[...form.items,{...newItem(),date:form.start_date}])} className="rounded-lg border px-3 py-2 text-sm">Add expense item</button>
        <p className="font-semibold">Claim total: {money(total)}</p>
        <label className="block text-sm">If receipts are unavailable, explain why<textarea aria-label="Missing receipt reason" maxLength={1000} value={form.missing_receipt_reason} onChange={event => update('missing_receipt_reason',event.target.value)} className={inputClass}/></label>
      </fieldset>{editable && <button disabled={busy} className="rounded-lg bg-slate-900 px-4 py-2 text-white">{busy ? 'Saving…' : 'Save travel draft'}</button>}</form>
      {record && <>
        <section className="space-y-3 border-t pt-4"><h3 className="font-medium">Receipts</h3><p className="text-xs text-slate-500">PDF, JPG or PNG, up to 3 MiB each; maximum 10. Receipts are private and retained with the claim.</p>{record.receipts.map(receipt => <button key={receipt.id} type="button" onClick={() => viewReceipt(receipt.id)} className="mr-3 text-sm text-teal-700 underline">{receipt.filename}</button>)}{!record.receipts.length && <p className="text-sm text-slate-500">No receipts attached.</p>}
          {editable && <form onSubmit={upload} className="flex flex-wrap gap-3"><input ref={fileRef} aria-label="Receipt file" required type="file" accept="application/pdf,image/jpeg,image/png" disabled={busy || dirty} onChange={event => {setFile(event.target.files[0] || null);}}/><button disabled={busy || dirty || !file} className="rounded-lg border px-3 py-2 text-sm">Attach receipt</button></form>}
        </section>
        {editable && <div className="border-t pt-4"><p className="mb-2 text-xs text-slate-500">Save changes before attaching receipts or submitting. Submission locks the claim until reviewed.</p><button disabled={busy || dirty} onClick={submit} className="rounded-lg bg-teal-700 px-4 py-2 text-white">Submit travel claim</button></div>}
        {record.review_remarks && <p className="rounded-lg bg-slate-50 p-3 text-sm">Review remarks: {record.review_remarks}</p>}
        {!own && record.status === 'SUBMITTED' && can('travel_expenses.approve') && <section className="space-y-3 border-t pt-4"><h3 className="font-medium">Review travel claim</h3><label className="block text-sm">Review remarks<textarea aria-label="Review remarks" disabled={busy} maxLength={1000} value={remarks} onChange={event => setRemarks(event.target.value)} className={inputClass}/></label><div className="flex gap-3"><button disabled={busy} onClick={() => decide('APPROVE')} className="rounded-lg bg-teal-700 px-4 py-2 text-white">Approve claim</button><button disabled={busy || !remarks.trim()} onClick={() => decide('REJECT')} className="rounded-lg border px-4 py-2 text-rose-700">Reject with remarks</button></div></section>}
        {!own && record.status === 'APPROVED' && can('travel_expenses.pay') && <form onSubmit={pay} className="space-y-3 border-t pt-4"><h3 className="font-medium">Record reimbursement</h3><p className="text-xs text-slate-500">Record a payment already made. This does not transfer money. The full approved amount is posted to Accounts once.</p><label className="block text-sm">Payment date<input aria-label="Payment date" disabled={busy} required type="date" max={today()} value={payment.payment_date} onChange={event => setPayment({...payment,payment_date:event.target.value})} className={inputClass}/></label><label className="block text-sm">Payment reference<input aria-label="Payment reference" disabled={busy} required minLength={3} maxLength={150} value={payment.payment_reference} onChange={event => setPayment({...payment,payment_reference:event.target.value})} className={inputClass}/></label><button disabled={busy} className="rounded-lg bg-slate-900 px-4 py-2 text-white">Record reimbursement</button></form>}
        {record.status === 'PAID' && <p className="rounded-lg bg-teal-50 p-3 text-sm">Paid {money(record.total_amount)} on {record.payment_date}. Reference: {record.payment_reference}</p>}
        <section className="border-t pt-4"><h3 className="font-medium">Claim history</h3><ol className="mt-2 space-y-2 text-sm text-slate-600">{record.history.map((entry,index) => <li key={index}>{entry.action} · version {entry.version} · user #{entry.actor_id} · {new Date(entry.created_at).toLocaleString('en-IN')}{entry.details.remarks ? ` · ${entry.details.remarks}` : ''}</li>)}</ol></section>
      </>}
    </section>}
  </div></MainLayout>;
}
