import { useEffect, useMemo, useState } from 'react';
import api from '../api/axios';
import { AlertTriangle, CheckCircle2, ChevronRight, FileCheck2, FileUp, Plus, RefreshCw, Save, Send, ShieldCheck, UserPlus, Users, X } from 'lucide-react';

const CATEGORIES=['GUARD','GUNMAN','SUPERVISOR','FIELD_OFFICER','JANITOR','CLEANER','FACILITY_ATTENDANT','GDA','NURSE_ASSISTANT','HOSPITAL_ATTENDANT'];
const REQUIRED_DOCS=['FORM_11','POLICE_VERIFICATION','MEDICAL_FITNESS','BANK_PASSBOOK','AADHAAR','PAN'];
const DOC_LABELS={FORM_11:'Form 11',POLICE_VERIFICATION:'Police Verification',MEDICAL_FITNESS:'Medical / Fitness Certificate',BANK_PASSBOOK:'Bank Passbook',AADHAAR:'Aadhaar Card',PAN:'PAN Card',FORM_11A:'Form 11A',ESIC_FORM:'ESIC Form',BANK_CHEQUE:'Cancelled Cheque',ADDRESS_PROOF:'Address Proof',PSARA_CERTIFICATE:'PSARA Certificate',GUN_LICENSE:'Gun Licence',PHOTO:'Photograph'};

const emptyDraft={name:'',phone:'',dob:'',gender:'',designation:'',client_id:'',site_id:'',joining_date:'',category:'GUARD',aadhaar_no:'',pan_no:'',permanent_address:'',present_address:'',emergency_contact:'',marital_status:'',bank_account_no:'',bank_name:'',bank_branch:'',bank_ifsc:'',nominee_name:'',nominee_relation:'',nominee_dob:'',nominee_aadhaar:'',nominee_percentage:'100'};

export default function EmployeeOnboardingWorkflow(){
 const [tab,setTab]=useState('intimations');
 const [intimations,setIntimations]=useState([]),[joining,setJoining]=useState([]),[approvals,setApprovals]=useState([]);
 const [categories,setCategories]=useState([]),[users,setUsers]=useState([]),[clients,setClients]=useState([]);
 const [loading,setLoading]=useState(false),[error,setError]=useState('');
 const [showIntimation,setShowIntimation]=useState(false),[intimation,setIntimation]=useState({name:'',phone:'',designation:'',category:'GUARD',client_id:'',notes:''});
 const [draft,setDraft]=useState(null),[form,setForm]=useState(emptyDraft),[docs,setDocs]=useState([]),[busy,setBusy]=useState(false),[remarks,setRemarks]=useState('');
 const [approvalRemark,setApprovalRemark]=useState('');

 async function loadAll(){
  setLoading(true);setError('');
  try{
   const [a,b,c,d,e]=await Promise.all([
    api.get('/erp/employees/workflow/intimations'),
    api.get('/erp/employees/workflow/joining'),
    api.get('/erp/employees/workflow/approvals'),
    api.get('/erp/employees/workflow/approval-categories'),
    api.get('/users/')
   ]);
   setIntimations(a.data||[]);setJoining(b.data||[]);setApprovals(c.data||[]);setCategories(d.data||[]);setUsers(e.data||[]);
   try{const cr=await api.get('/clients/');setClients(cr.data||[])}catch{}
  }catch(e){setError(e.response?.data?.detail||'Unable to load employee onboarding workflow.')}
  finally{setLoading(false)}
 }
 useEffect(()=>{loadAll()},[]);

 const setF=(k,v)=>setForm(x=>({...x,[k]:v}));
 async function createIntimation(e){
  e.preventDefault();setBusy(true);setError('');
  try{const r=await api.post('/erp/employees/workflow/intimations',{...intimation,client_id:intimation.client_id?Number(intimation.client_id):undefined});setShowIntimation(false);setIntimation({name:'',phone:'',designation:'',category:'GUARD',client_id:'',notes:''});await loadAll();setTab('intimations')}
  catch(e){setError(e.response?.data?.detail||'Unable to create intimation.')}finally{setBusy(false)}
 }
 async function openJoining(row){
  setBusy(true);setError('');
  try{
   let data;
   if(row.employee_id){data=(await api.get('/erp/employees/workflow/joining/'+row.employee_id)).data}
   else {data=(await api.post('/erp/employees/workflow/intimations/'+row.id+'/create')).data}
   setDraft(data);
   const mapped={...emptyDraft,...data};
   setForm(mapped);
   const dr=await api.get('/erp/employees/'+data.id+'/documents');setDocs(dr.data||[]);
   setTab('joining-edit');
  }catch(e){setError(e.response?.data?.detail||'Unable to open employee joining.')}finally{setBusy(false)}
 }
 async function saveDraft(){
  if(!draft)return;
  setBusy(true);setError('');
  try{
   const payload={...form,client_id:form.client_id?Number(form.client_id):undefined,site_id:form.site_id?Number(form.site_id):undefined};
   await api.patch('/erp/employees/workflow/joining/'+draft.id,payload);
   await loadAll();setTab('joining');alert('Employee joining saved as draft.');
  }catch(e){setError(e.response?.data?.detail||'Unable to save draft.')}finally{setBusy(false)}
 }
 async function upload(file,type){
  if(!draft||!file)return;setBusy(true);setError('');
  try{
   const body=new FormData();body.append('document_type',type);body.append('file',file);
   const r=await api.post('/erp/employees/'+draft.id+'/documents',body,{headers:{'Content-Type':'multipart/form-data'}});
   setDocs(x=>[r.data,...x]);
  }catch(e){setError(e.response?.data?.detail||'Document upload failed.')}finally{setBusy(false)}
 }
 async function submit(){
  if(!draft)return;
  setBusy(true);setError('');
  try{await api.post('/erp/employees/workflow/joining/'+draft.id+'/submit');await loadAll();setTab('approvals');alert('Employee submitted for approval.')}
  catch(e){setError(e.response?.data?.detail||'Submission blocked. Complete the required details and documents.')}finally{setBusy(false)}
 }
 async function decide(id,decision){
  setBusy(true);setError('');
  try{await api.post('/erp/employees/workflow/approvals/'+id+'/decision',{decision,remarks:approvalRemark});setApprovalRemark('');await loadAll()}
  catch(e){setError(e.response?.data?.detail||'Approval action failed.')}finally{setBusy(false)}
 }
 async function assignCategory(id,userId,finalFlag){
  try{await api.put('/erp/employees/workflow/approval-categories/'+id,{approver_user_id:userId?Number(userId):null,is_final_approver:finalFlag});await loadAll()}
  catch(e){setError(e.response?.data?.detail||'Unable to update approver assignment.')}
 }

 const docMap=useMemo(()=>Object.fromEntries(docs.map(d=>[d.document_type,d])),[docs]);
 const missingDocs=REQUIRED_DOCS.filter(x=>!docMap[x]);

 return <div className="space-y-5">
  <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
   <div><div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Employee onboarding control</div><h2 className="mt-1 text-2xl font-semibold text-slate-950">Intimation → Employee Joining → Approval</h2><p className="mt-1 text-sm text-slate-500">Create a general employee intimation first. Detailed joining remains a draft until documents are complete and submitted to the assigned approver.</p></div>
   <button onClick={loadAll} className="inline-flex items-center gap-2 self-start rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-semibold text-slate-700"><RefreshCw className="h-4 w-4"/>Refresh</button>
  </div>
  {error&&<div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}
  <div className="grid gap-3 md:grid-cols-4">
   <Step icon={UserPlus} number="01" title="Intimation" text="General information"/>
   <Step icon={FileCheck2} number="02" title="Employee Joining" text="Detailed profile + documents"/>
   <Step icon={ShieldCheck} number="03" title="Approval" text="Assigned approver reviews"/>
   <Step icon={Users} number="04" title="Approver Setup" text="Set responsible users"/>
  </div>
  <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white p-1.5 shadow-sm"><div className="flex min-w-max gap-1">
   {[
    ['intimations','Intimation Bucket'],['joining','Employee Joining'],['approvals','Approval Queue'],['approvers','Approver Setup']
   ].map(([id,label])=><button key={id} onClick={()=>setTab(id)} className={`rounded-xl px-4 py-2.5 text-sm font-semibold ${tab===id||tab==='joining-edit'&&id==='joining'?'bg-slate-950 text-white':'text-slate-500 hover:bg-slate-50'}`}>{label}</button>)}
  </div></div>

  {tab==='intimations'&&<section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
   <div className="flex items-center justify-between border-b border-slate-200 p-5"><div><h3 className="font-semibold text-slate-900">Employee Intimations</h3><p className="text-xs text-slate-500 mt-1">Only general information is captured here.</p></div><button onClick={()=>setShowIntimation(true)} className="inline-flex items-center gap-2 rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white"><Plus className="h-4 w-4"/>Create Intimation</button></div>
   <Table loading={loading} empty={!intimations.length} headers={['Intimation','Employee','Phone','Designation','Category','Status','Action']}>
    {intimations.map(x=><tr key={x.id} className="border-b border-slate-100 last:border-0"><Cell><b>{x.intimation_id}</b></Cell><Cell>{x.name}</Cell><Cell>{x.phone||'—'}</Cell><Cell>{x.designation||'—'}</Cell><Cell>{x.category||'—'}</Cell><Cell><Badge value={x.joining_status||x.status}/></Cell><Cell><button onClick={()=>openJoining(x)} disabled={!!x.employee_id&&x.joining_status==='APPROVED'} className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 disabled:opacity-40">{x.employee_id?'Open Joining':'Create Employee'}<ChevronRight className="h-3.5 w-3.5"/></button></Cell></tr>)}
   </Table>
  </section>}

  {tab==='joining'&&<section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
   <div className="border-b border-slate-200 p-5"><h3 className="font-semibold text-slate-900">Employee Joining Bucket</h3><p className="text-xs text-slate-500 mt-1">Every intimation becomes a joining record here. Use the action tab to complete the detailed employee file.</p></div>
   <Table loading={loading} empty={!joining.length} headers={['Employee ID','Employee','Designation','Category','Documents','Status','Action']}>
    {joining.map(x=><tr key={x.id} className="border-b border-slate-100 last:border-0"><Cell><b className="font-mono text-xs">{x.employee_code}</b></Cell><Cell>{x.name}</Cell><Cell>{x.designation||'—'}</Cell><Cell>{x.category||'—'}</Cell><Cell>{x.document_count}</Cell><Cell><Badge value={x.joining_status||x.employee_status}/></Cell><Cell><button onClick={()=>openJoining(x)} className="rounded-lg bg-slate-950 px-3 py-2 text-xs font-semibold text-white">Open / Continue</button></Cell></tr>)}
   </Table>
  </section>}

  {tab==='joining-edit'&&draft&&<JoiningEditor draft={draft} form={form} setF={setF} docs={docs} missingDocs={missingDocs} upload={upload} saveDraft={saveDraft} submit={submit} busy={busy} onBack={()=>setTab('joining')} clients={clients}/>}
  
  {tab==='approvals'&&<section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
   <div className="border-b border-slate-200 p-5"><h3 className="font-semibold text-slate-900">Employee Approval Queue</h3><p className="text-xs text-slate-500 mt-1">Only the assigned approver, or an administrator, can decide a request.</p></div>
   <Table loading={loading} empty={!approvals.length} headers={['Employee','ID','Category','Assigned To','Submitted','Decision']}>
    {approvals.map(x=><tr key={x.id} className="border-b border-slate-100 last:border-0"><Cell><b>{x.name}</b><div className="text-xs text-slate-400">{x.phone}</div></Cell><Cell>{x.employee_code}</Cell><Cell>{x.category_name}</Cell><Cell>{x.assigned_to_name||'Unassigned'}</Cell><Cell>{x.submitted_at?new Date(x.submitted_at).toLocaleString('en-IN'):'—'}</Cell><Cell><div className="flex flex-wrap gap-2"><input value={approvalRemark} onChange={e=>setApprovalRemark(e.target.value)} placeholder="Remark (optional)" className="w-44 rounded-lg border border-slate-200 px-2.5 py-2 text-xs"/><button disabled={busy} onClick={()=>decide(x.id,'APPROVE')} className="rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold text-white">Approve</button><button disabled={busy} onClick={()=>decide(x.id,'REJECT')} className="rounded-lg bg-rose-600 px-3 py-2 text-xs font-semibold text-white">Reject</button></div></Cell></tr>)}
   </Table>
  </section>}

  {tab==='approvers'&&<section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
   <div className="border-b border-slate-200 p-5"><h3 className="font-semibold text-slate-900">Approver Setup</h3><p className="text-xs text-slate-500 mt-1">Assign the person responsible for each approval category. Mark the final approver explicitly.</p></div>
   <div className="p-5 space-y-3">{categories.map(c=><div key={c.id} className="grid gap-3 rounded-xl border border-slate-200 p-4 md:grid-cols-[1.2fr_1fr_auto] md:items-center"><div><div className="font-semibold text-slate-800">{c.category_name}</div><div className="text-xs text-slate-400">{c.task_type}</div></div><select value={c.approver_user_id||''} onChange={e=>assignCategory(c.id,e.target.value,c.is_final_approver)} className="rounded-lg border border-slate-200 px-3 py-2.5 text-sm"><option value="">Select approver</option>{users.filter(u=>u.is_active).map(u=><option key={u.id} value={u.id}>{u.full_name} — {u.role}</option>)}</select><label className="flex items-center gap-2 text-xs font-semibold text-slate-700"><input type="checkbox" checked={!!c.is_final_approver} onChange={e=>assignCategory(c.id,c.approver_user_id,e.target.checked)}/> Final approver</label></div>)}</div>
  </section>}

  {showIntimation&&<div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4"><form onSubmit={createIntimation} className="w-full max-w-2xl rounded-3xl bg-white p-6 shadow-2xl"><div className="flex items-center justify-between"><div><h3 className="text-xl font-semibold">New Employee Intimation</h3><p className="text-xs text-slate-500 mt-1">This is only the general information stage.</p></div><button type="button" onClick={()=>setShowIntimation(false)}><X/></button></div><div className="mt-5 grid gap-4 md:grid-cols-2">
   <Field label="Employee Name" required value={intimation.name} onChange={v=>setIntimation({...intimation,name:v})}/><Field label="Mobile Number" value={intimation.phone} onChange={v=>setIntimation({...intimation,phone:v})}/><Field label="Designation" value={intimation.designation} onChange={v=>setIntimation({...intimation,designation:v})}/><Select label="Category" value={intimation.category} onChange={v=>setIntimation({...intimation,category:v})} options={CATEGORIES}/><Select label="Client" value={intimation.client_id} onChange={v=>setIntimation({...intimation,client_id:v})} options={['',...clients.map(c=>String(c.id))]} labels={['Select client',...clients.map(c=>c.company_name)]}/><Field label="General Notes" value={intimation.notes} onChange={v=>setIntimation({...intimation,notes:v})}/>
  </div><div className="mt-6 flex justify-end gap-2"><button type="button" onClick={()=>setShowIntimation(false)} className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-semibold">Cancel</button><button disabled={busy} className="rounded-xl bg-slate-950 px-5 py-2.5 text-sm font-semibold text-white">Create Intimation</button></div></form></div>}
 </div>
}

function JoiningEditor({draft,form,setF,docs,missingDocs,upload,saveDraft,submit,busy,onBack,clients}){
 const sections=[['general','General'],['personal','Personal & KYC'],['bank','Bank'],['nominee','Nominee'],['documents','Documents']];
 const [section,setSection]=useState('general');
 const [docType,setDocType]=useState('FORM_11');
 return <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
  <div className="flex flex-col gap-3 border-b border-slate-200 p-5 md:flex-row md:items-center md:justify-between"><div><div className="text-xs font-semibold uppercase tracking-wider text-slate-400">Employee Joining File</div><h3 className="mt-1 text-xl font-semibold">{form.name||draft.name} <span className="font-mono text-sm text-slate-500">{draft.employee_code}</span></h3><p className="text-xs text-slate-500">Intimation: {draft.source_intimation_id}</p></div><button onClick={onBack} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold">Back to bucket</button></div>
  <div className="border-b border-slate-200 px-4"><div className="flex gap-1 overflow-x-auto py-2">{sections.map(([id,label])=><button key={id} onClick={()=>setSection(id)} className={`whitespace-nowrap rounded-lg px-3 py-2 text-xs font-semibold ${section===id?'bg-slate-950 text-white':'text-slate-500 hover:bg-slate-50'}`}>{label}</button>)}</div></div>
  <div className="p-5 md:p-7">
   {section==='general'&&<div className="grid gap-4 md:grid-cols-3"><Field label="Full Name" required value={form.name} onChange={v=>setF('name',v)}/><Field label="Mobile" required value={form.phone} onChange={v=>setF('phone',v)}/><Field label="Date of Birth" required type="date" value={form.dob} onChange={v=>setF('dob',v)}/><Select label="Gender" required value={form.gender} onChange={v=>setF('gender',v)} options={['','Male','Female','Other']} labels={['Select gender','Male','Female','Other']}/><Field label="Designation" required value={form.designation} onChange={v=>setF('designation',v)}/><Select label="Client" required value={form.client_id} onChange={v=>setF('client_id',v)} options={['',...clients.map(c=>String(c.id))]} labels={['Select client',...clients.map(c=>c.company_name)]}/><Field label="Joining Date" required type="date" value={form.joining_date} onChange={v=>setF('joining_date',v)}/><Select label="Category" required value={form.category} onChange={v=>setF('category',v)} options={CATEGORIES}/><Field label="Site ID" value={form.site_id||''} onChange={v=>setF('site_id',v)}/></div>}
   {section==='personal'&&<div className="grid gap-4 md:grid-cols-2"><Field label="Aadhaar Number" required value={form.aadhaar_no} onChange={v=>setF('aadhaar_no',v)}/><Field label="PAN" required value={form.pan_no} onChange={v=>setF('pan_no',v)}/><Field label="Permanent Address" required value={form.permanent_address} onChange={v=>setF('permanent_address',v)} textarea/><Field label="Present Address" required value={form.present_address} onChange={v=>setF('present_address',v)} textarea/><Field label="Emergency Contact" required value={form.emergency_contact} onChange={v=>setF('emergency_contact',v)}/><Select label="Marital Status" value={form.marital_status} onChange={v=>setF('marital_status',v)} options={['','Single','Married','Other']}/></div>}
   {section==='bank'&&<div className="grid gap-4 md:grid-cols-2"><Field label="Account Number" required value={form.bank_account_no} onChange={v=>setF('bank_account_no',v)}/><Field label="Bank Name" required value={form.bank_name} onChange={v=>setF('bank_name',v)}/><Field label="Branch" required value={form.bank_branch} onChange={v=>setF('bank_branch',v)}/><Field label="IFSC" required value={form.bank_ifsc} onChange={v=>setF('bank_ifsc',v)}/></div>}
   {section==='nominee'&&<div className="grid gap-4 md:grid-cols-2"><Field label="Nominee Name" value={form.nominee_name} onChange={v=>setF('nominee_name',v)}/><Field label="Relation" value={form.nominee_relation} onChange={v=>setF('nominee_relation',v)}/><Field label="Nominee DOB" type="date" value={form.nominee_dob} onChange={v=>setF('nominee_dob',v)}/><Field label="Nominee Aadhaar" value={form.nominee_aadhaar} onChange={v=>setF('nominee_aadhaar',v)}/><Field label="Allocation %" type="number" value={form.nominee_percentage} onChange={v=>setF('nominee_percentage',v)}/></div>}
   {section==='documents'&&<div className="space-y-5"><div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"><b>{missingDocs.length} required documents missing.</b> Upload all required documents before submitting for approval.</div><div className="flex flex-wrap gap-2"><select value={docType} onChange={e=>setDocType(e.target.value)} className="rounded-lg border border-slate-200 px-3 py-2.5 text-sm">{Object.entries(DOC_LABELS).map(([k,v])=><option key={k}>{k}</option>)}</select><label className="inline-flex cursor-pointer items-center gap-2 rounded-lg bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white"><FileUp className="h-4 w-4"/> Upload<input type="file" accept=".pdf,image/jpeg,image/png,image/webp" className="hidden" disabled={busy} onChange={e=>{const f=e.target.files?.[0];if(f)upload(f,docType)}}/></label></div><div className="grid gap-3 md:grid-cols-2">{Object.entries(DOC_LABELS).map(([k,label])=><div key={k} className="flex items-center justify-between rounded-xl border border-slate-200 p-3"><div><div className="text-sm font-semibold">{label}</div><div className="text-[11px] text-slate-400">{REQUIRED_DOCS.includes(k)?'Required':'Optional'}</div></div>{docs.some(d=>d.document_type===k)?<span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600"><CheckCircle2 className="h-4 w-4"/>Uploaded</span>:<span className="text-xs font-semibold text-rose-500">Missing</span>}</div>)}</div></div>}
  </div>
  <div className="flex flex-col gap-3 border-t border-slate-200 p-5 md:flex-row md:items-center md:justify-between"><div className="text-xs text-slate-500">Employee code is generated automatically: <b>{draft.employee_code}</b>. Save Draft never sends the file for approval.</div><div className="flex flex-wrap gap-2"><button disabled={busy} onClick={saveDraft} className="inline-flex items-center gap-2 rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold"><Save className="h-4 w-4"/>Save Draft</button><button disabled={busy||missingDocs.length>0} onClick={submit} className="inline-flex items-center gap-2 rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-40"><Send className="h-4 w-4"/>Submit for Approval</button></div></div>
 </section>
}

function Step({icon:Icon,number,title,text}){return <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"><div className="flex items-center gap-3"><div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-950 text-white"><Icon className="h-4 w-4"/></div><div><div className="text-[10px] font-bold tracking-widest text-slate-400">{number}</div><div className="font-semibold text-slate-900">{title}</div></div></div><div className="mt-2 text-xs text-slate-500">{text}</div></div>}
function Field({label,value,onChange,required,type='text',textarea=false}){return <label className="block"><span className="mb-1.5 block text-xs font-semibold text-slate-600">{label}{required&&<span className="text-rose-500"> *</span>}</span>{textarea?<textarea value={value??''} onChange={e=>onChange(e.target.value)} rows={3} className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-slate-400"/>:<input required={required} type={type} value={value??''} onChange={e=>onChange(e.target.value)} className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-slate-400"/>}</label>}
function Select({label,value,onChange,options,labels,required}){return <label className="block"><span className="mb-1.5 block text-xs font-semibold text-slate-600">{label}{required&&<span className="text-rose-500"> *</span>}</span><select required={required} value={value??''} onChange={e=>onChange(e.target.value)} className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm">{options.map((o,i)=><option key={o} value={o}>{labels?.[i]??o||'Select'}</option>)}</select></label>}
function Table({children,headers,loading,empty}){return <div className="overflow-x-auto"><table className="min-w-[950px] w-full text-left text-sm"><thead><tr className="border-b border-slate-200 bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500">{headers.map(h=><th key={h} className="px-4 py-3.5">{h}</th>)}</tr></thead><tbody>{loading?<tr><td colSpan={headers.length} className="px-4 py-12 text-center text-slate-400">Loading…</td>:empty?<tr><td colSpan={headers.length} className="px-4 py-12 text-center text-slate-400">No records found.</td></tr>:children}</tbody></table></div>}
function Cell({children}){return <td className="px-4 py-4 align-top text-slate-700">{children}</td>}
function Badge({value}){return <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-slate-600">{String(value||'').replaceAll('_',' ')}</span>}
