import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, RefreshCw, Search, ShieldCheck, X } from 'lucide-react';
import MainLayout from '../layouts/MainLayout';
import { useAuth } from '../context/AuthContext';
import api from '../api/axios';

const base = '/erp/internal-staff';
const inputClass = 'mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-600/10';
const initial = { region:'', management_level:'SUPPORT', portal_role:'STAFF', name:'', phone:'', email:'', department:'', designation:'', branch:'', reporting_to:'', employment_type:'FULL_TIME', joining_date:'', dob:'', gender:'', father_spouse_name:'', address:'', city:'', state:'', pincode:'', emergency_name:'', emergency_phone:'', emergency_relation:'', pan:'', bank_account:'', bank_name:'', bank_ifsc:'', uan:'', esic_number:'', nominee_name:'', nominee_relation:'', notes:'' };
const sections = [
  ['Personal & contact', [['name','Full name',true],['phone','Mobile number',true],['email','Email',false,'email'],['dob','Date of birth',false,'date'],['gender','Gender'],['father_spouse_name','Father / spouse name']]],
  ['Employment', [['department','Department'],['designation','Designation'],['branch','Branch / office'],['reporting_to','Reporting manager'],['management_level','Management level'],['region','Region / responsibility'],['portal_role','Proposed ERP access role'],['employment_type','Employment type'],['joining_date','Joining date',false,'date']]],
  ['Address & emergency contact', [['address','Residential address'],['city','City'],['state','State'],['pincode','PIN code'],['emergency_name','Emergency contact name'],['emergency_phone','Emergency mobile'],['emergency_relation','Emergency relationship']]],
  ['Bank & statutory details', [['pan','PAN'],['bank_account','Bank account number'],['bank_name','Bank name'],['bank_ifsc','IFSC'],['uan','UAN'],['esic_number','ESIC number'],['nominee_name','Nominee name'],['nominee_relation','Nominee relationship'],['notes','Notes']]],
];
function errorText(err) {
  const detail = err?.response?.data?.detail;
  return Array.isArray(detail) ? detail.map(x => x.msg.replace(/^Value error, /,'')).join(' ') : (typeof detail === 'string' ? detail : 'Unable to complete this action. Please retry.');
}
function Field({ field, value, onChange, branches=[] }) {
  const [name,label,required,type='text'] = field;
  const options = name === 'branch' ? ['',...branches.map(x=>x.code), ...(value && !branches.some(x=>x.code===value) ? [value] : [])] : name === 'region' ? ['','ALL_REGIONS','UTTARAKHAND','UTTAR_PRADESH','DELHI_NCR'] : name === 'management_level' ? ['UPPER_MANAGEMENT','MANAGEMENT','BRANCH_HEAD','FIELD_OFFICER','SUPPORT'] : name === 'portal_role' ? ['OWNER','SUPER_ADMIN','ADMIN','HR','OPERATIONS','ACCOUNTS','SUPERVISOR','STAFF'] : name === 'employment_type' ? ['FULL_TIME','PART_TIME','CONTRACT','INTERN'] : name === 'gender' ? ['','MALE','FEMALE','OTHER'] : null;
  return <label className="block text-sm font-medium text-slate-700">{label}{required && ' *'}
    {options ? <select className={inputClass} value={value} onChange={e=>onChange(e.target.value)}>{options.map(x=><option key={x} value={x}>{name==='branch' ? (branches.find(b=>b.code===x)?.name || x || 'Head office / no branch') : x.replaceAll('_',' ') || 'Select'}</option>)}</select> :
    ['address','notes'].includes(name) ? <textarea maxLength={name==='notes'?2000:1000} rows={3} className={inputClass} value={value} onChange={e=>onChange(e.target.value)} /> :
    <input className={inputClass} type={type} required={required} value={value || ''} maxLength={type==='date'?undefined: name==='phone'||name==='emergency_phone'?18:255} onChange={e=>onChange(e.target.value)} />}
  </label>;
}

export default function StaffMaster() {
  const { user } = useAuth();
  const role = user?.role;
  const userId = user?.id;
  const permittedRole = ['OWNER','SUPER_ADMIN','ADMIN','HR','OPERATIONS','ACCOUNTS'].includes(role);
  const [access,setAccess] = useState(null);
  const [branches,setBranches] = useState([]);
  const [approval,setApproval] = useState(null);
  const [accounts,setAccounts] = useState([]);
  const [approverChoice,setApproverChoice] = useState('');
  const [rows,setRows] = useState([]);
  const [loading,setLoading] = useState(true);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  const [message,setMessage] = useState('');
  const [search,setSearch] = useState('');
  const [status,setStatus] = useState('');
  const [selected,setSelected] = useState(null);
  const [form,setForm] = useState(null);
  const [dirty,setDirty] = useState(false);
  const [reason,setReason] = useState('');
  const [code,setCode] = useState('');
  const [check,setCheck] = useState(null);
  const can = key => role === 'OWNER' || Boolean(access?.[key]);
  const canEdit = selected?.id ? can('staff.edit') : can('staff.create');
  const load = useCallback(async () => {
    if (!permittedRole) { setLoading(false); return; }
    setLoading(true);
    try {
      const [directory,permissions,rules,offices] = await Promise.all([api.get(base),api.get(`/users/${userId}/permissions`),api.get(`${base}/approval-settings`),api.get(`${base}/office-options`)]);
      setRows(directory.data); setAccess(permissions.data.permissions);setApproval(rules.data);setBranches(offices.data.branches);setApproverChoice(String(rules.data.approver_id||''));
      if (role === 'OWNER') setAccounts((await api.get('/users/')).data);
    } catch(err) { setError(errorText(err)); }
    finally { setLoading(false); }
  },[permittedRole,userId,role]);
  useEffect(()=>{load();},[load]);
  const filtered = rows.filter(row=>(!status || row.status===status) && `${row.name} ${row.staff_code} ${row.phone} ${row.department} ${row.designation}`.toLowerCase().includes(search.toLowerCase()));
  function close() {
    if (busy || (dirty && !window.confirm('Discard unsaved staff changes?'))) return;
    setForm(null); setSelected(null); setDirty(false); setReason('');
  }
  async function open(row) {
    setBusy(true); setError('');
    try { const {data}=await api.get(`${base}/${row.id}`); setSelected(data);setForm({...initial,...data.profile});setReason('');setDirty(false); }
    catch(err){setError(errorText(err));} finally{setBusy(false);}
  }
  async function save(event) {
    event.preventDefault();setBusy(true);setError('');
    try {
      const {data}=selected?.id ? await api.put(`${base}/${selected.id}`,{version:selected.version,profile:form}) : await api.post(base,{profile:form,submit:false});
      setSelected(data);setForm({...initial,...data.profile});setDirty(false);setMessage(`Saved ${data.staff_code}.`);await load();
    } catch(err){setError(errorText(err));} finally{setBusy(false);}
  }
  async function action(endpoint,extra={}) {
    if (dirty) { setError('Save your changes before submitting or changing status.');return; }
    setBusy(true);setError('');
    try {
      const {data}=await api.post(`${base}/${selected.id}/${endpoint}`,{version:selected.version,reason,...extra});
      setSelected(data);setForm({...initial,...data.profile});setReason('');setMessage(`${data.staff_code}: ${data.status}.`);await load();
    } catch(err){setError(errorText(err));} finally{setBusy(false);}
  }
  if (!permittedRole) return <MainLayout><p className="p-6 text-sm">Staff Master requires authorized internal office access.</p></MainLayout>;
  return <MainLayout><div className="space-y-5">
    <header className="flex flex-wrap items-end justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-widest text-teal-700">Company staff</p><h1 className="mt-1 text-2xl font-semibold">Staff Master</h1><p className="mt-1 text-sm text-slate-500">Internal company staff · permanent codes starting from S-DAS-0010.</p></div><div className="flex gap-2"><button type="button" disabled={loading||busy} onClick={load} className="rounded-lg border bg-white p-2.5" aria-label="Refresh staff"><RefreshCw size={18}/></button>{can('staff.create') && <button type="button" onClick={()=>{setSelected(null);setForm({...initial});setDirty(false);setError('');setReason('');}} className="flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white"><Plus size={16}/>Add staff</button>}</div></header>
    {error && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
    {message && <p role="status" className="rounded-lg bg-teal-50 p-3 text-sm text-teal-800">{message}</p>}
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">{[['Total staff',rows.length],['Active',rows.filter(x=>x.status==='ACTIVE').length],['Awaiting approval',rows.filter(x=>x.status==='PENDING').length],['Drafts',rows.filter(x=>x.status==='DRAFT').length]].map(([label,value])=><div key={label} className="rounded-xl border border-slate-200 bg-white p-4"><p className="text-sm text-slate-500">{label}</p><p className="mt-1 text-2xl font-semibold">{value}</p></div>)}</div>
    <section className="overflow-hidden rounded-xl border border-slate-200 bg-white">
      <div className="flex flex-wrap gap-3 border-b p-4"><label className="flex flex-1 items-center gap-2"><Search size={16}/><input aria-label="Search staff" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search name, staff code, mobile or department" className="w-full min-w-48 text-sm outline-none"/></label><select aria-label="Filter status" value={status} onChange={e=>setStatus(e.target.value)} className="rounded-lg border px-3 py-2 text-sm"><option value="">All statuses</option>{['DRAFT','PENDING','ACTIVE','INACTIVE','TERMINATED'].map(x=><option key={x}>{x}</option>)}</select></div>
      {loading ? <p className="p-8 text-center text-sm text-slate-500">Loading staff…</p> : <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr>{['Staff','Contact','Department / designation','Branch','Status','Record'].map(x=><th key={x} className="px-4 py-3">{x}</th>)}</tr></thead><tbody>{filtered.map(row=><tr key={row.id} className="border-t border-slate-100"><td className="px-4 py-4 font-medium">{row.name}<div className="mt-1 text-xs text-slate-500">{row.staff_code}</div></td><td className="px-4 py-4">{row.phone}</td><td className="px-4 py-4">{row.department||'—'}<div className="text-xs text-slate-500">{row.designation}</div></td><td className="px-4 py-4">{row.branch||'—'}</td><td className="px-4 py-4"><span className={`rounded-full px-2 py-1 text-xs font-semibold ${row.status==='ACTIVE'?'bg-teal-50 text-teal-800':'bg-slate-100 text-slate-600'}`}>{row.status}</span></td><td className="px-4 py-4"><button disabled={busy} type="button" onClick={()=>open(row)} className="font-medium text-teal-700">Open</button></td></tr>)}</tbody></table>{!filtered.length && <p className="p-8 text-center text-sm text-slate-500">{rows.length?'No matching staff.':'No staff added yet. Add your first staff record to begin.'}</p>}</div>}
    </section>
    {role==='OWNER' && approval && <section className="rounded-xl border bg-white p-4"><h2 className="text-sm font-semibold">Staff approval responsibility</h2><p className="mt-1 text-xs text-slate-500">Select who approves new staff. Assign staff view and approval permissions in User Management first. This applies to new submissions; pending records keep their assigned approver. The Owner can always review them.</p><div className="mt-3 flex flex-wrap gap-3"><select aria-label="Staff approver" value={approverChoice} onChange={e=>setApproverChoice(e.target.value)} className="rounded-lg border px-3 py-2 text-sm"><option value="">Owner</option>{accounts.filter(x=>x.is_active&&['OWNER','SUPER_ADMIN','ADMIN','HR','OPERATIONS','ACCOUNTS'].includes(x.role)).map(x=><option key={x.id} value={x.id}>{x.full_name} · {x.role}</option>)}</select><button type="button" disabled={busy} onClick={async()=>{setBusy(true);setError('');try{const {data}=await api.put(`${base}/approval-settings`,{version:approval.version,approver_id:approverChoice?Number(approverChoice):null});setApproval(data);setMessage('Staff approval responsibility saved.');}catch(err){setError(errorText(err));}finally{setBusy(false);}}} className="rounded-lg border px-3 py-2 text-sm">Save approval responsibility</button></div></section>}
    <form onSubmit={async e=>{e.preventDefault();setBusy(true);setError('');try{setCheck((await api.get(`${base}/code-check`,{params:{code}})).data);}catch(err){setError(errorText(err));}finally{setBusy(false);}}} className="flex flex-wrap items-center gap-3 rounded-xl border bg-white p-4"><ShieldCheck size={20} className="text-teal-700"/><label className="text-sm font-medium" htmlFor="code-check">Check staff code</label><input id="code-check" required maxLength={30} value={code} onChange={e=>{setCode(e.target.value);setCheck(null);}} placeholder="S-DAS-0010" className="rounded-lg border px-3 py-2 text-sm"/><button disabled={busy} className="rounded-lg border px-3 py-2 text-sm">Verify</button>{check && <p role="status" className="text-sm">{check.registered?`Registered · ${check.status}`:check.valid_format?'Valid format; no registered record.':'Invalid staff code format.'}</p>}</form>
    {form && <div className="fixed inset-0 z-[60] overflow-y-auto bg-slate-950/40 p-3 sm:p-8" role="dialog" aria-modal="true" aria-labelledby="staff-title"><div className="mx-auto max-w-4xl rounded-2xl bg-white p-5 sm:p-7">
      <div className="flex items-start justify-between"><div><h2 id="staff-title" className="text-xl font-semibold">{selected?.staff_code||'New staff draft'}</h2><p className="mt-1 text-sm text-slate-500">{selected?.status||'Code is allocated when saved.'}</p></div><button type="button" disabled={busy} onClick={close} aria-label="Close staff record"><X size={22}/></button></div>
      {error && <p role="alert" className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
      {selected?.status_reason && <p className="mt-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">{selected.status_reason}</p>}
      <form onSubmit={save} className="mt-5 space-y-6"><fieldset disabled={busy||!canEdit||selected?.status==='TERMINATED'} className="space-y-6 disabled:opacity-75">{sections.map(([title,fields])=><section key={title}><h3 className="border-b pb-2 text-sm font-semibold">{title}</h3><div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{fields.map(field=><Field key={field[0]} field={field} value={form[field[0]]} branches={branches} onChange={value=>{setForm(p=>({...p,[field[0]]:value}));setDirty(true);}}/>)}</div></section>)}</fieldset><div className="flex flex-wrap items-center justify-between gap-3 border-t pt-4"><p className="text-xs text-slate-500">Department, designation and joining date are required to submit. Proposed ERP role grants access only when an administrator creates the account. Branches come from Company Profile & Docs.</p>{canEdit && selected?.status!=='TERMINATED' && <button disabled={busy} className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white">{busy?'Saving…':selected?.id?'Save changes':'Save draft'}</button>}</div></form>
      {selected?.id && <section className="mt-5 space-y-3 border-t pt-4"><div className="flex flex-wrap gap-2">{selected.status==='DRAFT' && can('staff.edit') && <button disabled={busy||dirty} type="button" onClick={()=>action('submit')} className="rounded-lg bg-teal-700 px-4 py-2 text-sm font-medium text-white">{role==='OWNER'?'Submit & activate':'Submit for approval'}</button>}{selected.status==='PENDING' && (role==='OWNER'||selected.approver_id===user.id) && can('staff.approve') && <><button disabled={busy||dirty} type="button" onClick={()=>action('decision',{decision:'APPROVE'})} className="rounded-lg bg-teal-700 px-4 py-2 text-sm font-medium text-white">Approve staff</button><button disabled={busy||dirty||!reason.trim()} type="button" onClick={()=>action('decision',{decision:'RETURN'})} className="rounded-lg border px-4 py-2 text-sm">Return for correction</button></>}{['ACTIVE','INACTIVE'].includes(selected.status) && ['OWNER','SUPER_ADMIN','ADMIN'].includes(role) && can('staff.edit') && <><button disabled={busy||dirty||!reason.trim()} type="button" onClick={()=>action('status',{status:selected.status==='ACTIVE'?'INACTIVE':'ACTIVE'})} className="rounded-lg border px-4 py-2 text-sm">{selected.status==='ACTIVE'?'Mark inactive':'Reactivate'}</button><button disabled={busy||dirty||!reason.trim()} type="button" onClick={()=>{if(window.confirm('Terminate this staff record? It will be retained as read-only.')) action('status',{status:'TERMINATED'});}} className="rounded-lg border border-rose-200 px-4 py-2 text-sm text-rose-700">Terminate</button></>}</div>{((role==='OWNER'||selected.approver_id===user.id)&&selected.status==='PENDING'||['OWNER','SUPER_ADMIN','ADMIN'].includes(role)&&['ACTIVE','INACTIVE'].includes(selected.status)) && <label className="block text-sm">Decision / status reason<input value={reason} maxLength={1000} onChange={e=>setReason(e.target.value)} className={inputClass}/></label>}<p className="text-xs text-slate-500">Staff status does not change account permissions. Manage ERP login access separately.</p>{selected.account && <p className="text-sm text-slate-600">ERP account: {selected.account.login_id} · {selected.account.role} · {selected.account.is_active?'Enabled':'Disabled'}</p>}{['OWNER','SUPER_ADMIN','ADMIN'].includes(role) && ['ACTIVE','INACTIVE','TERMINATED'].includes(selected.status) && <Link to={`/users?staff_code=${encodeURIComponent(selected.staff_code)}`} state={{staff:{staff_code:selected.staff_code,name:form.name,email:form.email,phone:form.phone,portal_role:form.portal_role}}} className="inline-block text-sm font-medium text-teal-700">Manage login for {selected.staff_code} →</Link>}</section>}
    </div></div>}
  </div></MainLayout>;
}
