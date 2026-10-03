import { useEffect, useState } from 'react';
import MainLayout from '../layouts/MainLayout';
import GlassCard from '../components/GlassCard';
import api from '../api/axios';
import { useCompany } from '../context/CompanyContext';
import { ReceiptText, IndianRupee, Landmark, AlertTriangle, ShieldCheck, BellRing } from 'lucide-react';

const money=(value)=>new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:0}).format(Number(value||0));
export default function ERPModules(){
 const { company } = useCompany();
 const [summary,setSummary]=useState(null),[loading,setLoading]=useState(true),[error,setError]=useState('');
 useEffect(()=>{api.get('/erp/summary').then(({data})=>setSummary(data||{})).catch(e=>setError(e.response?.data?.detail||'Unable to load dashboard summary.')).finally(()=>setLoading(false))},[]);
 const cards=[['Monthly Billing Pending',summary?.monthly_billing_pending,ReceiptText],['Total Amount Received',summary?.total_amount_received,IndianRupee],['GST Collected',summary?.gst_collected,Landmark],['Pending to Collect',summary?.pending_to_collect,ReceiptText],['GST to be Paid',summary?.gst_to_be_paid,Landmark],['Pending Compliance',summary?.pending_compliance,ShieldCheck]];
 return <MainLayout><div className="space-y-6">
  <section className="bg-white border border-slate-200 rounded-2xl p-5 sm:p-6 shadow-sm"><p className="text-[11px] font-semibold tracking-[0.18em] text-teal-700 uppercase">{company.display_name} • Dashboard</p><h1 className="text-2xl sm:text-3xl font-bold text-slate-900 mt-2">Management Dashboard</h1><p className="text-sm text-slate-500 mt-1.5">Financial and compliance position for {summary?.month||'the current month'}.</p></section>
  {error&&<div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
  <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">{cards.map(([label,value,Icon])=><div key={label} className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm"><div className="w-10 h-10 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-center text-teal-700"><Icon className="w-5 h-5"/></div><p className="text-xs font-medium text-slate-500 mt-4">{label}</p><p className="text-2xl font-bold text-slate-900 mt-1">{loading?'—':label==='Pending Compliance'?Number(value||0):money(value)}</p></div>)}</section>
  <section className="bg-white border border-slate-200 rounded-2xl shadow-sm"><div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between"><div><h2 className="text-base font-bold text-slate-900">Compliance Reminders</h2><p className="text-xs text-slate-500 mt-1">Due or expiring within the next 30 days.</p></div><BellRing className="w-5 h-5 text-amber-500"/></div><div className="p-5">{loading?<p className="text-sm text-slate-400">Loading reminders...</p>:!summary?.compliance_reminders?.length?<p className="text-sm text-slate-500">No compliance reminders for the next 30 days.</p>:<div className="space-y-2">{summary.compliance_reminders.map(item=><div key={item.reminder_type+'-'+item.id} className="flex items-center justify-between gap-4 p-3 rounded-xl bg-slate-50 border border-slate-200"><div><p className="text-sm font-semibold text-slate-800">{item.compliance_type}</p><p className="text-xs text-slate-500">{item.employee_name?item.employee_name+' • ':''}{item.reminder_type}</p></div><div className="flex items-center gap-2"><AlertTriangle className="w-4 h-4 text-amber-500"/><span className="text-xs font-semibold text-slate-600">{item.due_date||'No due date'}</span></div></div>)}</div>}</div></section>
 </div></MainLayout>
}
