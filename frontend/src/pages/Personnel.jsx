import { useEffect, useState } from 'react';
import MainLayout from '../layouts/MainLayout';
import api from '../api/axios';
import { BriefcaseBusiness, UserPlus, ShieldCheck, AlertTriangle, CheckCircle2 } from 'lucide-react';

const verticals=['SECURITY','HOUSEKEEPING','NURSING'];
const categories={
 SECURITY:['GUARD','GUNMAN','SUPERVISOR','FIELD_OFFICER'],
 HOUSEKEEPING:['JANITOR','CLEANER','FACILITY_ATTENDANT'],
 NURSING:['GDA','NURSE_ASSISTANT','HOSPITAL_ATTENDANT']
};

export default function Personnel(){
 const [tab,setTab]=useState('staff'); const [vertical,setVertical]=useState('ALL');
 const [staff,setStaff]=useState([]); const [candidates,setCandidates]=useState([]);
 const [loading,setLoading]=useState(true); const [message,setMessage]=useState('');
 const [form,setForm]=useState({full_name:'',phone:'',vertical:'SECURITY',category:'GUARD'});
 const [onboard,setOnboard]=useState(null); const [createStaff,setCreateStaff]=useState(false);

 async function load(){
   setLoading(true);
   try { const [s,c]=await Promise.all([api.get('/erp/staff'),api.get('/erp/recruitment')]); setStaff(s.data||[]); setCandidates(c.data||[]); }
   catch(e){setMessage(e?.response?.data?.detail||'Unable to load personnel data.');}
   finally{setLoading(false);}
 }
 useEffect(()=>{load()},[]);
 const filtered=vertical==='ALL'?staff:staff.filter(x=>x.vertical===vertical);
 const locked=staff.filter(x=>x.is_bench_locked).length;
 const expiring=staff.filter(x=>[x.police_verification_expiry,x.medical_fitness_expiry,x.psara_training_expiry,x.gun_license_expiry].some(d=>d && new Date(d)<=new Date(Date.now()+60*86400000))).length;

 async function createCandidate(e){
   e.preventDefault(); setMessage('');
   try{await api.post('/erp/recruitment',form);setForm({full_name:'',phone:'',vertical:'SECURITY',category:'GUARD'});setMessage('Candidate added to APPLIED stage.');load();}
   catch(e){setMessage(e?.response?.data?.detail||'Candidate could not be created.');}
 }
 async function verify(id){try{await api.patch('/erp/recruitment/'+id,{status:'VERIFIED'});setMessage('Candidate verified.');load()}catch(e){setMessage(e?.response?.data?.detail||'Verification failed.')}}
 async function openOnboard(c){setOnboard(c)}
 async function submitOnboard(e){
   e.preventDefault(); setMessage('');
   const fd=new FormData(e.currentTarget); const payload=Object.fromEntries(fd.entries());
   try{await api.post('/erp/recruitment/'+onboard.candidate_id+'/onboard',payload);setOnboard(null);setMessage('Candidate onboarded into Deployment Personnel.');load();}
   catch(e){setMessage(e?.response?.data?.detail||'Onboarding failed.')}
 }
 async function runCompliance(){try{const r=await api.post('/erp/staff/compliance/run');setMessage(`Compliance checked: ${r.data.checked}; bench locked: ${r.data.bench_locked}.`);load()}catch(e){setMessage(e?.response?.data?.detail||'Compliance run failed.')}}
 return <MainLayout>
  <div className="space-y-6">
   <header className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
    <div><p className="text-xs font-semibold uppercase tracking-[.18em] text-teal-600">DestinLane Workforce</p><h1 className="mt-2 text-3xl font-semibold text-slate-900">Deployment Personnel</h1><p className="mt-1 text-sm text-slate-500">Security, housekeeping and healthcare personnel with recruitment and compliance controls.</p></div>
    <button onClick={()=>setCreateStaff(true)} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700"><UserPlus className="h-4 w-4"/>Create Employee</button><button onClick={runCompliance} className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white"><ShieldCheck className="h-4 w-4"/>Run compliance check</button>
   </header>
   {message&&<div className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700">{message}</div>}
   <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
    <Metric icon={BriefcaseBusiness} label="Deployment Profiles" value={staff.length}/>
    <Metric icon={AlertTriangle} label="Bench Locked" value={locked}/>
    <Metric icon={ShieldCheck} label="Compliance Due ≤60 Days" value={expiring}/>
   </div>
   <div className="flex flex-wrap gap-2 border-b border-slate-200">
    {[['staff','Deployed Employee Directory'],['recruitment','Recruitment Pipeline'],['compliance','Compliance & Expiries']].map(([id,label])=><button key={id} onClick={()=>setTab(id)} className={`px-4 py-3 text-sm font-semibold border-b-2 ${tab===id?'border-teal-600 text-teal-700':'border-transparent text-slate-500'}`}>{label}</button>)}
   </div>
   {tab==='staff'&&<section className="space-y-4">
    <div className="flex gap-2 flex-wrap">{['ALL',...verticals].map(v=><button key={v} onClick={()=>setVertical(v)} className={`rounded-full px-3 py-1.5 text-xs font-semibold ${vertical===v?'bg-slate-900 text-white':'bg-white border border-slate-200 text-slate-600'}`}>{v==='NURSING'?'HEALTHCARE':v}</button>)}</div>
    <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white"><table className="min-w-full text-sm"><thead><tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-400"><th className="px-4 py-3">Employee</th><th className="px-4 py-3">Vertical</th><th className="px-4 py-3">Category</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Police Verification</th><th className="px-4 py-3">Medical</th></tr></thead><tbody>{filtered.map(s=><tr key={s.id} className="border-b border-slate-100"><td className="px-4 py-4 font-semibold text-slate-800">{s.name}<div className="text-xs text-slate-400">{s.employee_code}</div></td><td className="px-4 py-4">{s.vertical}</td><td className="px-4 py-4">{s.category}</td><td className="px-4 py-4"><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${s.is_bench_locked?'bg-rose-50 text-rose-700':'bg-emerald-50 text-emerald-700'}`}>{s.is_bench_locked?'BENCH LOCKED':'ACTIVE'}</span>{s.bench_lock_reason&&<div className="mt-1 text-[11px] text-rose-500">{s.bench_lock_reason}</div>}</td><td className="px-4 py-4 text-slate-600">{s.police_verification_expiry||'Missing'}</td><td className="px-4 py-4 text-slate-600">{s.medical_fitness_expiry||'Missing'}</td></tr>)}</tbody></table>{!loading&&!filtered.length&&<div className="p-8 text-center text-sm text-slate-400">No staff profiles found.</div>}</div>
   </section>}
   {tab==='recruitment'&&<section className="grid lg:grid-cols-[360px_1fr] gap-5">
    <form onSubmit={createCandidate} className="rounded-2xl border border-slate-200 bg-white p-5 space-y-4"><h2 className="font-semibold text-slate-900 flex items-center gap-2"><UserPlus className="h-4 w-4"/>New candidate</h2><Input label="Full name" value={form.full_name} onChange={v=>setForm({...form,full_name:v})}/><Input label="Phone" value={form.phone} onChange={v=>setForm({...form,phone:v})}/><Select label="Vertical" value={form.vertical} options={verticals} onChange={v=>setForm({...form,vertical:v,category:categories[v][0]})}/><Select label="Category" value={form.category} options={categories[form.vertical]} onChange={v=>setForm({...form,category:v})}/><button className="w-full rounded-lg bg-teal-700 px-4 py-2.5 text-sm font-semibold text-white">Add to Applied</button></form>
    <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden"><div className="px-5 py-4 border-b border-slate-200 font-semibold">Recruitment Pipeline</div>{candidates.map(c=><div key={c.id} className="p-5 border-b border-slate-100 flex flex-col md:flex-row md:items-center justify-between gap-3"><div><div className="font-semibold text-slate-800">{c.full_name}</div><div className="text-xs text-slate-400">{c.candidate_id} · {c.vertical} · {c.category||'Category pending'}</div></div><div className="flex items-center gap-2"><span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold">{c.status}</span>{c.status==='APPLIED'&&<button onClick={()=>verify(c.candidate_id)} className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold">Verify</button>}{c.status==='VERIFIED'&&<button onClick={()=>openOnboard(c)} className="rounded-lg bg-teal-700 text-white px-3 py-1.5 text-xs font-semibold">Onboard</button>}</div></div>)}{!candidates.length&&<div className="p-8 text-center text-sm text-slate-400">No candidates yet.</div>}</div>
   </section>}
   {tab==='compliance'&&<section className="rounded-2xl border border-slate-200 bg-white p-5"><h2 className="font-semibold text-slate-900">Compliance & Expiries</h2><p className="mt-1 text-sm text-slate-500">Police Verification and Medical Fitness are mandatory. Missing or expired documents lock staff to BENCH.</p><div className="mt-5 grid md:grid-cols-2 gap-3">{staff.filter(s=>s.is_bench_locked||[s.police_verification_expiry,s.medical_fitness_expiry,s.psara_training_expiry,s.gun_license_expiry].some(d=>d&&new Date(d)<=new Date(Date.now()+60*86400000))).map(s=><div key={s.id} className="rounded-xl border border-slate-200 p-4"><div className="font-semibold text-slate-800">{s.name}</div><div className="text-xs text-slate-500 mt-1">{s.vertical} · {s.category}</div><div className="mt-3 text-xs text-rose-600">{s.bench_lock_reason||'Document approaching expiry'}</div></div>)}</div></section>}
  </div>
  {createStaff&&<div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4"><form onSubmit={async e=>{e.preventDefault();setMessage('');const p=Object.fromEntries(new FormData(e.currentTarget).entries());try{const r=await api.post('/erp/staff',p);setCreateStaff(false);setMessage(`Staff created: ${r.data.employee.employee_code}`);load()}catch(e){setMessage(e?.response?.data?.detail||'Staff creation failed.')}}} className="w-full max-w-3xl max-h-[90vh] overflow-auto rounded-2xl bg-white p-6 space-y-5"><div><h2 className="text-xl font-semibold text-slate-900">Create Employee</h2><p className="text-sm text-slate-500 mt-1">Employee codes are generated automatically. Company staff are managed separately in Staff Master.</p></div><div className="grid md:grid-cols-2 gap-4"><Input label="Full name" name="name" required/><Input label="Phone" name="phone" required/><label className="block"><span className="block text-xs font-semibold text-slate-600 mb-1.5">Vertical *</span><select name="vertical" required className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm">{verticals.map(v=><option key={v}>{v}</option>)}</select></label><label className="block"><span className="block text-xs font-semibold text-slate-600 mb-1.5">Category *</span><select name="category" required className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm">{Object.values(categories).flat().map(v=><option key={v}>{v}</option>)}</select></label><Input label="Aadhaar (12 digits)" name="aadhaar_number" required/><Input label="PAN" name="pan_number" required/><Input label="Bank Account" name="bank_account_no" required/><Input label="Bank Name" name="bank_name" required/><Input label="IFSC" name="bank_ifsc" required/><Input label="Police Verification Expiry" name="police_verification_expiry" type="date" required/><Input label="Medical Fitness Expiry" name="medical_fitness_expiry" type="date" required/></div><div className="flex justify-end gap-2"><button type="button" onClick={()=>setCreateStaff(false)} className="rounded-lg border px-4 py-2 text-sm">Cancel</button><button className="rounded-lg bg-teal-700 px-4 py-2 text-sm font-semibold text-white">Create Employee</button></div></form></div>}
  {onboard&&<div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4"><form onSubmit={submitOnboard} className="w-full max-w-2xl max-h-[90vh] overflow-auto rounded-2xl bg-white p-6 space-y-4"><div><h2 className="text-xl font-semibold">Onboard {onboard.full_name}</h2><p className="text-sm text-slate-500">{onboard.vertical} · {onboard.category}</p></div><div className="grid md:grid-cols-2 gap-4"><Input label="Aadhaar (12 digits)" name="aadhaar_number" required/><Input label="PAN" name="pan_number" required/><Input label="Bank Account" name="bank_account_no" required/><Input label="IFSC" name="bank_ifsc" required/><Input label="Police Verification Expiry" name="police_verification_expiry" type="date"/><Input label="Medical Fitness Expiry" name="medical_fitness_expiry" type="date"/>{onboard.category==='GUNMAN'&&<><Input label="Arms License No" name="arms_license_no" required/><Input label="Arms Expiry Date" name="arms_expiry_date" type="date" required/><Input label="Arms Caliber" name="arms_caliber" required/><Input label="Ammunition Count" name="ammunition_count" type="number"/></>}<Input label="PSARA Training Expiry" name="psara_training_expiry" type="date"/><Input label="Gun License Expiry" name="gun_license_expiry" type="date"/><Input label="Uniform Total Cost" name="uniform_total_cost" type="number"/><Input label="Monthly Uniform EMI" name="uniform_monthly_emi" type="number"/></div><div className="flex justify-end gap-2"><button type="button" onClick={()=>setOnboard(null)} className="rounded-lg border px-4 py-2 text-sm">Cancel</button><button className="rounded-lg bg-teal-700 text-white px-4 py-2 text-sm font-semibold">Create Employee Profile</button></div></form></div>}
 </MainLayout>
}
function Metric({icon:Icon,label,value}){return <div className="rounded-2xl border border-slate-200 bg-white p-5"><Icon className="h-5 w-5 text-teal-600"/><div className="mt-4 text-2xl font-semibold text-slate-900">{value}</div><div className="text-xs text-slate-500 mt-1">{label}</div></div>}
function Input({label,value,onChange,name,type='text',required=false}){return <label className="block"><span className="block text-xs font-semibold text-slate-600 mb-1.5">{label}{required&&<span className="text-rose-500"> *</span>}</span><input name={name} type={type} value={value??''} required={required} onChange={e=>onChange&&onChange(e.target.value)} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-teal-500" /></label>}
function Select({label,value,options,onChange}){return <label className="block"><span className="block text-xs font-semibold text-slate-600 mb-1.5">{label}</span><select value={value} onChange={e=>onChange(e.target.value)} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm">{options.map(x=><option key={x}>{x}</option>)}</select></label>}
