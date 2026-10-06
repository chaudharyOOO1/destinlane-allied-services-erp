import { useCallback, useEffect, useState } from 'react';
import { Plus, RefreshCw, X } from 'lucide-react';
import MainLayout from '../layouts/MainLayout';
import { useAuth } from '../context/AuthContext';
import api from '../api/axios';

const base = '/erp/internal-staff';
const inputClass = 'mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm';
const initial = { name:'', phone:'', email:'', department:'', designation:'', branch:'', joining_date:'', employment_type:'FULL_TIME', notes:'' };
const fields = [['name','Full name','text',true],['phone','Mobile number','tel',true],['email','Email','email',true],['department','Department','text',true],['designation','Designation','text',true],['joining_date','Joining date','date',false]];
function errorText(err) {
  const detail = err?.response?.data?.detail;
  return Array.isArray(detail) ? detail.map(x => x.msg.replace(/^Value error, /,'')).join(' ') : (typeof detail === 'string' ? detail : 'Unable to complete this action. Please retry.');
}

export default function StaffMaster() {
  const { user } = useAuth();
  const manager = ['OWNER','HR'].includes(user?.role);
  const [access,setAccess] = useState({});
  const [options,setOptions] = useState({branches:[],login_roles:[],permissions:{},supported:{}});
  const [rows,setRows] = useState([]);
  const [loading,setLoading] = useState(true);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  const [message,setMessage] = useState('');
  const [search,setSearch] = useState('');
  const [selected,setSelected] = useState(null);
  const [form,setForm] = useState(null);
  const [dirty,setDirty] = useState(false);
  const [reason,setReason] = useState('');
  const [loginRole,setLoginRole] = useState('OPERATIONS');
  const [password,setPassword] = useState('');
  const [permissions,setPermissions] = useState({});
  const [enabled,setEnabled] = useState(true);
  const can = key => Boolean(access[key]);
  const canManageTarget = manager && (user.role==='OWNER'||!['OWNER','SUPER_ADMIN','ADMIN'].includes(selected?.account?.role));
  const canEdit = canManageTarget && can(selected?.id?'staff.edit':'staff.create');
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [directory,rights,offices] = await Promise.all([api.get(base),api.get(`/users/${user.id}/permissions`),api.get(`${base}/office-options`)]);
      setRows(directory.data);setAccess(rights.data.permissions);setOptions(offices.data);
    } catch(err) { setError(errorText(err)); }
    finally { setLoading(false); }
  },[user.id]);
  useEffect(()=>{load();},[load]);
  function chooseRole(role) {setLoginRole(role);setPermissions({...options.permissions[role]});setDirty(true);}
  function close() {
    if (busy || (dirty && !window.confirm('Discard unsaved staff changes?'))) return;
    setForm(null);setSelected(null);setPassword('');setDirty(false);
  }
  function show(data) {
    setSelected(data);setForm({...initial,...data.profile});setPassword('');setDirty(false);setReason('');
    setLoginRole(data.account?.role||'OPERATIONS');setEnabled(data.account?.is_active??true);
    setPermissions(data.permissions||{...options.permissions[data.account?.role||'OPERATIONS']});
  }
  async function open(row) {
    setBusy(true);setError('');
    try {show((await api.get(`${base}/${row.id}`)).data);} catch(err){setError(errorText(err));} finally{setBusy(false);}
  }
  async function save(event) {
    event.preventDefault();setBusy(true);setError('');
    try {
      const {data}=selected?.id ? await api.put(`${base}/${selected.id}`,{version:selected.version,profile:form}) : await api.post(base,{profile:form,account:{role:loginRole,temporary_password:password,permissions}});
      show((await api.get(`${base}/${data.id}`)).data);setMessage(`Saved ${data.staff_code}${selected?.id?'':'. ERP login created; password change required at first sign-in.'}`);await load();
    } catch(err){setError(errorText(err));} finally{setBusy(false);}
  }
  async function saveAccess(event) {
    event.preventDefault();setBusy(true);setError('');
    try {
      if (selected.account) await api.put(`${base}/${selected.id}/login`,{version:selected.version,role:loginRole,is_active:enabled,permissions});
      else await api.post(`${base}/${selected.id}/login`,{role:loginRole,temporary_password:password,permissions});
      show((await api.get(`${base}/${selected.id}`)).data);setMessage('ERP access saved.');await load();
    } catch(err){setError(errorText(err));} finally{setBusy(false);}
  }
  async function changeStatus(status) {
    setBusy(true);setError('');
    try {await api.post(`${base}/${selected.id}/status`,{version:selected.version,reason,status});show((await api.get(`${base}/${selected.id}`)).data);setMessage(`Staff marked ${status.toLowerCase()}.`);await load();}
    catch(err){setError(errorText(err));} finally{setBusy(false);}
  }
  const permissionFields = <fieldset disabled={busy} className="space-y-3"><label className="block text-sm font-medium">Departmental role<select value={loginRole} onChange={e=>chooseRole(e.target.value)} className={inputClass}>{options.login_roles.map(role=><option key={role} value={role}>{role.replaceAll('_',' ')}</option>)}</select></label>{(!selected?.account) && <label className="block text-sm font-medium">Temporary password *<input type="password" required minLength={12} maxLength={72} autoComplete="new-password" value={password} onChange={e=>{setPassword(e.target.value);setDirty(true);}} className={inputClass}/><span className="text-xs text-slate-500">At least 12 characters. The staff member must change it at first sign-in.</span></label>}<p className="text-sm font-medium">Working permissions</p><p className="text-xs text-slate-500">Select the information and actions this person needs. Employee creation uses Employees · create.</p><div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{Object.entries(options.supported[loginRole]||{}).filter(([,supported])=>supported).map(([key])=><label key={key} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={Boolean(permissions[key])} onChange={e=>{setPermissions(p=>({...p,[key]:e.target.checked}));setDirty(true);}}/>{key.replaceAll('_',' ').replace('.',' · ')}</label>)}</div></fieldset>;
  return <MainLayout><div className="space-y-5">
    <header className="flex flex-wrap items-center justify-between gap-3"><div><h1 className="text-2xl font-semibold">Staff Master</h1><p className="mt-1 text-sm text-slate-500">Company staff and ERP access · IDs starting from DASS0010.</p></div><div className="flex gap-2"><button type="button" disabled={loading||busy} onClick={load} className="rounded-lg border bg-white p-2.5" aria-label="Refresh staff"><RefreshCw size={18}/></button>{manager&&can('staff.create') && <button type="button" onClick={()=>{setSelected(null);setForm({...initial});setPassword('');setLoginRole('OPERATIONS');setPermissions({...options.permissions.OPERATIONS});setEnabled(true);setDirty(false);setError('');setReason('');}} className="flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white"><Plus size={16}/>Add staff</button>}</div></header>
    {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
    {message && <p role="status" className="rounded-lg bg-teal-50 p-3 text-sm text-teal-800">{message}</p>}
    <section className="overflow-hidden rounded-xl border bg-white"><div className="border-b p-4"><input aria-label="Search staff" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search name, ID, mobile or department" className="w-full text-sm outline-none"/></div>{loading?<p className="p-6">Loading staff…</p>:<div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr>{['Staff','Mobile','Department / designation','Branch','Status','Record'].map(x=><th key={x} className="px-4 py-3">{x}</th>)}</tr></thead><tbody>{rows.filter(row=>`${row.name} ${row.staff_code} ${row.phone} ${row.department}`.toLowerCase().includes(search.toLowerCase())).map(row=><tr key={row.id} className="border-t"><td className="px-4 py-4">{row.name}<div className="text-xs text-slate-500">{row.staff_code}</div></td><td className="px-4 py-4">{row.phone}</td><td className="px-4 py-4">{row.department||'—'}<div className="text-xs text-slate-500">{row.designation}</div></td><td className="px-4 py-4">{row.branch||'—'}</td><td className="px-4 py-4">{row.status}</td><td className="px-4 py-4"><button disabled={busy} onClick={()=>open(row)} className="font-medium text-teal-700">Open</button></td></tr>)}</tbody></table>{!rows.length&&<p className="p-6 text-sm text-slate-500">No staff added yet.</p>}</div>}</section>
    {form && <div className="fixed inset-0 z-[60] overflow-y-auto bg-slate-950/40 p-3 sm:p-8" role="dialog" aria-modal="true" aria-labelledby="staff-title"><div className="mx-auto max-w-4xl rounded-2xl bg-white p-5 sm:p-7"><div className="flex justify-between"><div><h2 id="staff-title" className="text-xl font-semibold">{selected?.staff_code||'Create staff and ERP login'}</h2><p className="mt-1 text-sm text-slate-500">{selected?.status||'Staff ID is assigned when saved.'}</p></div><button type="button" disabled={busy} onClick={close} aria-label="Close staff record"><X size={22}/></button></div>{error&&<p role="alert" className="mt-4 bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
    <form onSubmit={save} className="mt-5 space-y-5"><fieldset disabled={busy||!canEdit||selected?.status==='TERMINATED'} className="grid gap-4 sm:grid-cols-2">{fields.map(([key,label,type,required])=><label key={key} className="block text-sm font-medium">{label}{required?' *':''}<input type={type} required={required} value={form[key]||''} readOnly={key==='email'&&Boolean(selected?.account)} onChange={e=>{setForm(p=>({...p,[key]:e.target.value}));setDirty(true);}} maxLength={type==='date'?undefined:150} className={inputClass}/></label>)}<label className="block text-sm font-medium">Branch<select value={form.branch} onChange={e=>{setForm(p=>({...p,branch:e.target.value}));setDirty(true);}} className={inputClass}><option value="">Head office / no branch</option>{options.branches.map(b=><option key={b.code} value={b.code}>{b.name}</option>)}{form.branch&&!options.branches.some(b=>b.code===form.branch)&&<option value={form.branch}>{form.branch}</option>}</select></label><label className="block text-sm font-medium">Employment type<select value={form.employment_type} onChange={e=>{setForm(p=>({...p,employment_type:e.target.value}));setDirty(true);}} className={inputClass}>{['FULL_TIME','PART_TIME','CONTRACT','INTERN'].map(x=><option key={x} value={x}>{x.replaceAll('_',' ')}</option>)}</select></label><label className="block text-sm font-medium sm:col-span-2">Notes<textarea maxLength={2000} value={form.notes} onChange={e=>{setForm(p=>({...p,notes:e.target.value}));setDirty(true);}} className={inputClass}/></label></fieldset>{!selected?.id&&permissionFields}{canEdit&&selected?.status!=='TERMINATED'&&<button disabled={busy} className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white">{busy?'Saving…':selected?.id?'Save staff details':'Create staff and login'}</button>}</form>
    {selected?.id&&<section className="mt-6 space-y-4 border-t pt-4"><h3 className="font-semibold">ERP access</h3>{selected.account&&<p className="text-sm">Login: {selected.account.login_id} · {selected.account.role} · {selected.account.is_active?'Enabled':'Disabled'}{selected.account.must_change_password?' · Password change required':''}</p>}{canManageTarget&&can('staff.edit')&&selected.status!=='TERMINATED'&&<><form onSubmit={saveAccess} className="space-y-4">{permissionFields}{selected.account&&<label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={enabled} onChange={e=>{setEnabled(e.target.checked);setDirty(true);}}/>Enable ERP login</label>}<button disabled={busy||selected.status!=='ACTIVE'} className="rounded-lg border px-4 py-2 text-sm">{selected.account?'Save ERP access':'Create ERP login'}</button></form><label className="block text-sm font-medium">Status change reason<input maxLength={1000} value={reason} onChange={e=>setReason(e.target.value)} className={inputClass}/></label><div className="flex flex-wrap gap-2"><button type="button" disabled={busy||!reason.trim()} onClick={()=>changeStatus(selected.status==='ACTIVE'?'INACTIVE':'ACTIVE')} className="rounded-lg border px-4 py-2 text-sm">{selected.status==='ACTIVE'?'Mark inactive':'Reactivate staff'}</button><button type="button" disabled={busy||!reason.trim()} onClick={()=>{if(window.confirm('Terminate this staff record and disable its login?'))changeStatus('TERMINATED');}} className="rounded-lg border px-4 py-2 text-sm text-rose-700">Terminate staff</button></div><p className="text-xs text-slate-500">Marking inactive or terminated disables ERP access. After reactivating staff, enable ERP login separately.</p></>}</section>}
    </div></div>}
  </div></MainLayout>;
}
