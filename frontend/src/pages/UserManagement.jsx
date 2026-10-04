import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import MainLayout from '../layouts/MainLayout';
import api from '../api/axios';
import { useAuth } from '../context/AuthContext';
import { useAccess } from '../context/AccessContext';

const modules=['dashboard','employees','recruitment','clients','contracts','sites','rosters','attendance','billing','payroll','finance','compliance','risks','owner','user_management','company','staff'];
const actions=['view','create','edit','delete','approve','export'];
const roles=['OWNER','SUPER_ADMIN','ADMIN','HR','OPERATIONS','ACCOUNTS','SUPERVISOR','CLIENT','STAFF'];

export default function UserManagement(){
 const {user}=useAuth();
 const {can,refresh}=useAccess();
 const [supported,setSupported]=useState({});
 const [roleChoice,setRoleChoice]=useState('STAFF');
 const [users,setUsers]=useState([]),[selected,setSelected]=useState(null),[permissions,setPermissions]=useState({}),[saving,setSaving]=useState(''),[error,setError]=useState('');
 const location = useLocation();
 const staff = location.state?.staff;
 const query = new URLSearchParams(window.location.search);
 const [form,setForm]=useState({login_id:query.get('staff_code')||'',email:staff?.email||'',full_name:staff?.name||'',phone_number:staff?.phone||'',role:roles.includes(staff?.portal_role)?staff.portal_role:'STAFF',password:''});
 async function load(){try{const r=await api.get('/users/');setUsers(r.data||[]);const linked=(r.data||[]).find(x=>x.login_id===query.get('staff_code'));if(linked) selectUser(linked)}catch(e){setError(e.response?.data?.detail||'Unable to load users.')}}
 useEffect(()=>{load()},[]);
 async function selectUser(u){setSelected(u);setRoleChoice(u.role);setError('');try{const r=await api.get('/users/'+u.id+'/permissions');setPermissions(r.data.permissions||{});setSupported(r.data.supported||{})}catch(e){setError(e.response?.data?.detail||'Unable to load permissions.')}}
 async function toggle(key){const next=!permissions[key];setPermissions(p=>({...p,[key]:next}));setSaving(key);try{await api.put('/users/'+selected.id+'/permissions',{permission_key:key,allowed:next});if(selected.id===user.id)await refresh()}catch(e){setPermissions(p=>({...p,[key]:!next}));setError(e.response?.data?.detail||'Permission update failed.')}finally{setSaving('')}}
 async function createUser(e){e.preventDefault();setError('');try{await api.post('/users/',{...form,login_id:form.login_id.trim()||null});setForm({login_id:'',email:'',full_name:'',phone_number:'',role:'STAFF',password:''});load()}catch(e){const detail=e.response?.data?.detail;setError(Array.isArray(detail)?detail.map(x=>x.msg).join(' '):detail||'Unable to create account.')}}
 async function resetPassword(u){const p=window.prompt('Set a temporary password (minimum 12 characters):');if(!p)return;if(p.length<12)return setError('Temporary password must be at least 12 characters.');try{await api.post('/users/'+u.id+'/reset-password',{new_password:p});setError('');alert('Password reset. Ask the user to sign in and change it from My Account.')}catch(e){setError(e.response?.data?.detail||'Unable to reset password.')}}
 async function setActive(u){try{await api.put('/users/'+u.id,{is_active:!u.is_active});load();if(selected?.id===u.id)setSelected({...u,is_active:!u.is_active})}catch(e){setError(e.response?.data?.detail||'Unable to update account status.')}}
 return <MainLayout><div className="space-y-6">
  <div><p className="text-xs font-semibold uppercase tracking-[0.18em] text-teal-700">Administration</p><h1 className="text-2xl font-bold text-slate-900 mt-1">User Management</h1><p className="text-sm text-slate-500 mt-1">Create accounts, activate or disable them, and allow or deny individual module actions.</p></div>
  {error&&<div className="rounded-lg bg-rose-50 border border-rose-200 px-3 py-2 text-sm text-rose-700">{error}</div>}
  <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
   <div className="xl:col-span-1 space-y-5">
    {can('user_management.create')&&<form onSubmit={createUser} className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm space-y-3">
      <h2 className="font-bold text-slate-900">Create Account</h2>
      {['login_id','full_name','email','phone_number','password'].map(k=><input key={k} aria-label={k.replaceAll('_',' ')} required={!['login_id','phone_number'].includes(k)} type={k==='password'?'password':'text'} placeholder={k.replace('_',' ')} value={form[k]} onChange={e=>setForm({...form,[k]:e.target.value})} className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm" />)}
      <select value={form.role} onChange={e=>setForm({...form,role:e.target.value})} className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm">{roles.filter(r=>user.role==='OWNER'||!['OWNER','SUPER_ADMIN','ADMIN'].includes(r)).map(r=><option key={r}>{r}</option>)}</select>
      <button className="w-full rounded-lg bg-slate-900 text-white py-2.5 text-sm font-semibold">Create Account</button>
    </form>}
    <div className="bg-white border border-slate-200 rounded-2xl p-3 shadow-sm">
      <h2 className="px-2 py-2 font-bold text-slate-900">Accounts</h2>
      <div className="space-y-1">{users.map(u=><button key={u.id} onClick={()=>selectUser(u)} className={'w-full text-left p-3 rounded-xl border '+(selected?.id===u.id?'border-teal-300 bg-teal-50':'border-transparent hover:bg-slate-50')}><div className="flex items-center justify-between"><span className="text-sm font-semibold text-slate-800">{u.full_name}</span><span className={'text-[10px] font-bold '+(u.is_active?'text-emerald-600':'text-rose-600')}>{u.is_active?'ACTIVE':'DISABLED'}</span></div><p className="text-xs text-slate-500 mt-1">{u.login_id || u.email} • {u.role}</p></button>)}</div>
    </div>
   </div>
   <div className="xl:col-span-2 bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
    {!selected?<div className="h-full min-h-80 flex items-center justify-center text-sm text-slate-400">Select an account to manage its access.</div>:
    <><div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-4"><div><h2 className="font-bold text-slate-900">{selected.full_name}</h2><p className="text-xs text-slate-500">{selected.email} • {selected.role}</p></div>{can('user_management.edit')&&selected.id!==user.id&&<button onClick={()=>setActive(selected)} className={'px-3 py-2 rounded-lg text-xs font-semibold '+(selected.is_active?'bg-rose-50 text-rose-700':'bg-emerald-50 text-emerald-700')}>{selected.is_active?'Disable Account':'Enable Account'}</button>}{can('user_management.edit')&&<button onClick={()=>resetPassword(selected)} className="px-3 py-2 rounded-lg text-xs font-semibold bg-slate-100 text-slate-700 hover:bg-slate-200">Reset Password</button>}</div><div className="mt-4 flex flex-wrap items-center gap-3"><label className="text-sm font-medium">ERP role<select disabled={selected.id===user.id||!can('user_management.edit')} value={roleChoice} onChange={e=>setRoleChoice(e.target.value)} className="ml-3 rounded-lg border px-3 py-2">{roles.filter(r=>user.role==='OWNER'||!['OWNER','SUPER_ADMIN','ADMIN'].includes(r)||r===selected.role).map(r=><option key={r}>{r}</option>)}</select></label><button disabled={selected.id===user.id||!can('user_management.edit')||roleChoice===selected.role} onClick={async()=>{setError('');try{const {data}=await api.put('/users/'+selected.id,{role:roleChoice});await selectUser(data);await load();}catch(err){setError(err.response?.data?.detail||'Unable to update role.');}}} className="rounded-lg border px-3 py-2 text-sm">Save role</button><span className="text-xs text-slate-500">New and reset accounts must change their temporary password before using ERP.</span></div>
    <div className="mt-5 overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b border-slate-200"><th className="text-left py-2">Module</th>{actions.map(a=><th key={a} className="text-center text-[10px] uppercase text-slate-400">{a}</th>)}</tr></thead><tbody>{modules.map(m=><tr key={m} className="border-b border-slate-100"><td className="py-3 font-semibold text-slate-700">{m.replace('_',' ')}</td>{actions.map(a=>{const k=m+'.'+a;return <td key={k} className="text-center"><button aria-label={`${m} ${a}`} title={supported[k]===false?'Unavailable for this role':''} disabled={Boolean(saving)||supported[k]===false||!can('user_management.edit')||(selected.role==='OWNER'&&selected.is_superuser)} onClick={()=>toggle(k)} className={'w-7 h-7 rounded-md border text-xs font-bold '+(permissions[k]?'bg-teal-600 text-white border-teal-600':'bg-white text-slate-300 border-slate-200')}>{permissions[k]?'✓':'—'}</button></td>})}</tr>)}</tbody></table></div>
    <p className="text-[11px] text-slate-400 mt-4">Permissions override role defaults immediately. The Owner retains full access; staff approvals follow the Owner’s assigned approval responsibility.</p></>}
   </div>
  </div>
 </div></MainLayout>
}