import { useCallback, useEffect, useRef, useState } from 'react';
import api from '../api/axios';
import { useAuth } from '../context/AuthContext';
import { useAccess } from '../context/AccessContext';

const blank = () => ({staff_id:'',gross_pay:'',deductions:'0.00',work_note:''});
const input = 'mt-1 w-full rounded-lg border border-slate-200 p-2 text-sm';
const failure = error => typeof error.response?.data?.detail === 'string' ? error.response.data.detail : 'Unable to complete this request. Check the fields and retry.';
export default function StaffMonthlyPay({month,onBusyChange}) {
  const {user} = useAuth();
  const {can} = useAccess();
  const [data,setData] = useState({staff:[],proposals:[]});
  const [form,setForm] = useState(blank);
  const [editing,setEditing] = useState(null);
  const [decision,setDecision] = useState(null);
  const [note,setNote] = useState('');
  const [paidOn,setPaidOn] = useState('');
  const [reference,setReference] = useState('');
  const [error,setError] = useState('');
  const [message,setMessage] = useState('');
  const [busy,setBusy] = useState(false);
  const guard = useRef(false);
  const generation = useRef(0);
  const load = useCallback(async()=>{
    const request=++generation.current;
    const {data}=await api.get('/erp/payroll/staff-monthly',{params:{month}});
    if(request===generation.current)setData(data);
  },[month]);
  useEffect(()=>{setEditing(null);setForm(blank());setData({staff:[],proposals:[]});setDecision(null);setError('');setMessage('');load().catch(error=>setError(failure(error)));return()=>{generation.current++};},[load]);
  async function save(work){
    if(guard.current)return;
    guard.current=true;setBusy(true);onBusyChange?.(true);setError('');setMessage('');
    try{
      const saved=await work();
      if(saved?.id)setData(current=>{
        const staff=current.staff.find(row=>row.id===saved.staff_id);
        const previous=current.proposals.find(row=>row.id===saved.id);
        return {...current,proposals:[{...staff,...previous,...saved},...current.proposals.filter(row=>row.id!==saved.id)]};
      });
      setDecision(null);setMessage('Saved.');
      try{await load()}catch{setMessage('Saved. Use Refresh staff pay to reload the latest proposals.')}
    }catch(error){setError(failure(error))}finally{guard.current=false;setBusy(false);onBusyChange?.(false)}
  }
  function propose(event){
    event.preventDefault();
    save(async()=>{
      const payload={...form,staff_id:Number(form.staff_id),month};
      const {data}=editing
        ? await api.put(`/erp/payroll/staff-monthly/${editing.id}`,{...payload,version:editing.version})
        : await api.post('/erp/payroll/staff-monthly',payload);
      setForm(blank());setEditing(null);return data;
    });
  }
  function act(event){
    event.preventDefault();const target=decision;
    save(async()=>{
      const {data}=await api.post(`/erp/payroll/staff-monthly/${target.row.id}/${target.type==='PAY'?'pay':'decision'}`,
        target.type==='PAY'?{version:target.row.version,paid_on:paidOn,reference}:{version:target.row.version,decision:target.type,note});
      setNote('');setReference('');setPaidOn('');return data;
    });
  }
  const management = ['OWNER','SUPER_ADMIN'].includes(user?.role);
  return <details className="rounded-xl border border-slate-200 bg-white p-4"><summary className="cursor-pointer font-semibold text-slate-900">Internal staff · monthly Management approval</summary>
    <p className="mt-2 text-sm text-slate-500">No staff salary is generated automatically. Propose the amount for branch work this month; Management must approve each proposal. Deductions require review. Recording payment records a completed payment reference.</p>
    <button type="button" disabled={busy} onClick={()=>{setError('');load().catch(error=>setError(failure(error)))}} className="mt-3 rounded-lg border px-3 py-2 text-sm disabled:opacity-50">Refresh staff pay</button>
    {error&&<p role="alert" className="mt-3 text-sm text-rose-700">{error}</p>}{message&&<p role="status" className="mt-3 text-sm text-emerald-700">{message}</p>}
    {(can('payroll.create')||can('payroll.edit'))&&<form onSubmit={propose} className="mt-4 grid gap-3 sm:grid-cols-2"><fieldset disabled={busy} className="contents">
      <label className="text-sm">Staff<select required disabled={Boolean(editing)} value={form.staff_id} onChange={e=>setForm({...form,staff_id:e.target.value})} className={input}><option value="">Choose active staff</option>{data.staff.map(row=><option key={row.id} value={row.id}>{row.staff_code} · {row.name} · {row.branch||'No branch'}</option>)}</select></label>
      <label className="text-sm">Gross proposal (₹)<input required type="number" min="0.01" max="99999999" step="0.01" value={form.gross_pay} onChange={e=>setForm({...form,gross_pay:e.target.value})} className={input}/></label>
      <label className="text-sm">Reviewed deductions (₹)<input required type="number" min="0" max={form.gross_pay||'99999999'} step="0.01" value={form.deductions} onChange={e=>setForm({...form,deductions:e.target.value})} className={input}/></label>
      <label className="text-sm">Branch work and calculation note<textarea required minLength={10} maxLength={2000} value={form.work_note} onChange={e=>setForm({...form,work_note:e.target.value})} className={input}/></label>
      <button disabled={busy} className="w-fit rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">{editing?'Save revised proposal':`Propose for ${month}`}</button>{editing&&<button type="button" disabled={busy} onClick={()=>{setEditing(null);setForm(blank())}} className="w-fit rounded-lg border px-4 py-2 text-sm">Cancel editing</button>}</fieldset></form>}
    <div className="mt-4 overflow-auto"><table className="w-full text-left text-sm"><thead><tr>{['Staff / branch','Gross (₹)','Deductions (₹)','Net (₹)','Status','Actions'].map(label=><th key={label} className="p-2">{label}</th>)}</tr></thead><tbody>{data.proposals.map(row=><tr key={row.id} className="border-t"><td className="p-2">{row.staff_code} · {row.name}<p className="text-xs text-slate-500">{row.branch} · {row.work_note}</p>{row.decision_note&&<p className="text-xs text-slate-500">Decision: {row.decision_note}</p>}</td>{['gross_pay','deductions','net_pay'].map(key=><td key={key} className="p-2 tabular-nums">{Number(row[key]).toLocaleString('en-IN',{minimumFractionDigits:2})}</td>)}<td className="p-2">{row.status}{row.payment_reference&&<p className="text-xs">{row.paid_on} · {row.payment_reference}</p>}</td><td className="p-2"><div className="flex gap-2">{can('payroll.edit')&&['DRAFT','REJECTED'].includes(row.status)&&<button disabled={busy} onClick={()=>{setEditing(row);setForm({staff_id:String(row.staff_id),gross_pay:String(row.gross_pay),deductions:String(row.deductions),work_note:row.work_note})}} className="rounded-lg border px-3 py-2 text-xs">Revise</button>}{management&&can('payroll.approve')&&row.status==='DRAFT'&&['APPROVE','REJECT'].map(type=><button key={type} disabled={busy} onClick={()=>{setDecision({row,type});setNote('')}} className="rounded-lg border px-3 py-2 text-xs">{type==='APPROVE'?'Approve':'Reject'}</button>)}{can('payroll.pay')&&row.status==='APPROVED'&&<button disabled={busy} onClick={()=>setDecision({row,type:'PAY'})} className="rounded-lg border px-3 py-2 text-xs">Record payment</button>}</div></td></tr>)}</tbody></table>{!data.proposals.length&&<p className="p-4 text-sm text-slate-500">No staff pay proposed for {month}. Active staff alone do not generate salary.</p>}</div>
    {decision&&<form onSubmit={act} className="mt-4 space-y-3 rounded-lg bg-slate-50 p-4"><h3 className="font-semibold">{decision.type==='PAY'?'Record completed payment':decision.type==='APPROVE'?'Approve monthly staff pay':'Reject monthly staff pay'} · {decision.row.staff_code}</h3>{decision.type==='PAY'?<><label className="block text-sm">Payment date<input required type="date" value={paidOn} onChange={e=>setPaidOn(e.target.value)} className={input}/></label><label className="block text-sm">Bank / payment reference<input required minLength={3} maxLength={200} value={reference} onChange={e=>setReference(e.target.value)} className={input}/></label></>:<label className="block text-sm">Management review note<textarea required minLength={10} maxLength={2000} value={note} onChange={e=>setNote(e.target.value)} className={input}/></label>}<div className="flex gap-2"><button disabled={busy} className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">Confirm</button><button disabled={busy} type="button" onClick={()=>setDecision(null)} className="rounded-lg border px-4 py-2 text-sm">Cancel</button></div></form>}
  </details>;
}
