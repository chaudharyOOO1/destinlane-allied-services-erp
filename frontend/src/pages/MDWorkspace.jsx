import {useCallback, useEffect, useRef, useState} from 'react';
import MainLayout from '../layouts/MainLayout';
import MDAccounting from './MDAccounting';
import BankReview from '../components/accounting/BankReview';
import MoneyReports from '../components/accounting/MoneyReports';
import api from '../api/axios';
import {money,accountingError} from '../components/accounting/format';

const base='/erp/md-accounting';
const today=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Kolkata'}).format(new Date());
const emptyRecord=(type='MONEY_OUT')=>({transaction_type:type,entry_date:today(),bank_account_id:'',counter_account_id:'',category:type==='TRANSFER'?'TRANSFER':'',amount:'',party:'',purpose:'',reference:''});
const field='mt-1 min-w-0 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm';
const button='rounded-xl border px-4 py-2.5 text-sm font-medium disabled:opacity-50';
function Label({label,children}){return <label className="block min-w-0 text-sm font-medium text-slate-700">{label}{children}</label>;}

export default function MDWorkspace(){
 const [view,setView]=useState('RECORD'),[advanced,setAdvanced]=useState({tab:'Setup',voucherId:null});
 const [options,setOptions]=useState(null),[setup,setSetup]=useState(null),[records,setRecords]=useState([]),[dashboard,setDashboard]=useState(null);
 const [form,setForm]=useState(emptyRecord),[preview,setPreview]=useState(null),[saved,setSaved]=useState(null),[dirty,setDirty]=useState(false);
 const [origin,setOrigin]=useState(null),[error,setError]=useState(''),[message,setMessage]=useState(''),[warning,setWarning]=useState('');
 const [busy,setBusy]=useState(false);const guard=useRef(false);
 const refresh=useCallback(async()=>{
  const [o,s,r,d]=await Promise.all([api.get(`${base}/transactions/options`),api.get(`${base}/setup`),api.get(`${base}/journals`),api.get(`${base}/transactions/dashboard`)]);
  setOptions(o.data);setSetup(s.data);setRecords(r.data);setDashboard(d.data);
 },[]);
 useEffect(()=>{refresh().catch(error=>setError(accountingError(error)));},[refresh]);
 function update(key,value){setForm(previous=>({...previous,[key]:value,...(key==='category'?{counter_account_id:''}:{})}));setPreview(null);setDirty(true);}
 function start(type='MONEY_OUT',values={},statement=null){
  if(guard.current||(dirty&&!window.confirm('Discard this unsaved money record?')))return;
  setForm({...emptyRecord(type),...values});setSaved(null);setPreview(null);setOrigin(statement);setDirty(false);setError('');setMessage('');setWarning('');setView('RECORD');
 }
 function openAdvanced(tab='Setup',voucherId=null){if(guard.current)return;setAdvanced({tab,voucherId});setView('ADVANCED');}
 async function withBusy(task){if(guard.current)return;guard.current=true;setBusy(true);setError('');setWarning('');try{await task();}catch(error){setError(accountingError(error));}finally{guard.current=false;setBusy(false);}}
 function values(){return {...form,bank_account_id:Number(form.bank_account_id),counter_account_id:Number(form.counter_account_id)};}
 async function review(event){event.preventDefault();return withBusy(async()=>{const {data}=await api.post(`${base}/transactions/preview`,values());setPreview(data.summary);setMessage('Review the details below. Nothing has been saved yet.');});}
 async function saveDraft(){return withBusy(async()=>{
  const {data}=await api.post(`${base}/transactions`,values());setSaved(data);setDirty(false);setMessage(`Saved ${data.voucher}. Review it, then confirm to update the books.`);
  try{await refresh();}catch{setWarning('Your draft is saved, but the list could not refresh. Keep this reference and reopen it before retrying.');}
 });}
 async function postRecord(){return withBusy(async()=>{
  const {data}=await api.post(`${base}/journals/${saved.id}/post`,{version:saved.version});setSaved(data);setMessage(`${data.voucher} is recorded in the books. Reports now include it.`);
  if(origin){
   const bankLine=data.lines.find(line=>line.account_id===origin.account_id);
   try{if(!bankLine)throw new Error('Bank line missing');await api.post(`${base}/bank/statements/${origin.id}/match`,{journal_line_id:bankLine.id});setOrigin(null);setMessage(`${data.voucher} is recorded and matched to the bank transaction.`);}
   catch{setWarning('The transaction is recorded, but bank matching was not confirmed. Match the existing record in Bank Review; do not record it again.');}
  }
  try{await refresh();}catch{setWarning(previous=>[previous,'Your record is confirmed, but reports could not refresh. Refresh the workspace.'].filter(Boolean).join(' '));}
 });}
 async function openRecord(record){
  if(!['PAYMENT','RECEIPT','CONTRA'].includes(record.kind)){openAdvanced('Books',record.id);return;}
  if(dirty&&!window.confirm('Discard this unsaved money record?'))return;
  await withBusy(async()=>{setSaved((await api.get(`${base}/journals/${record.id}`)).data);setPreview(null);setDirty(false);setOrigin(null);setView('RECORD');setMessage('');});
 }
 async function returnFromAdvanced(){
  setView('RECORD');
  await withBusy(async()=>{
   // Advanced edits/posting may change the acknowledged record and its version.
   if(saved)setSaved((await api.get(`${base}/journals/${saved.id}`)).data);
   await refresh();
  });
 }
 function recordBankRow(row,bankId){
  start(Number(row.debit)>0?'MONEY_OUT':'MONEY_IN',{entry_date:row.entry_date,bank_account_id:String(bankId),amount:String(Number(row.debit)>0?row.debit:row.credit),purpose:row.description||'',reference:row.reference||row.statement_id},{id:row.id,account_id:Number(bankId)});
 }
 const types=[['MONEY_OUT','Money Out','Record a payment'],['MONEY_IN','Money In','Record money received'],['TRANSFER','Transfer','Move money between company accounts']];
 const category=options?.categories[form.transaction_type]?.find(item=>item.id===form.category);
 const kindName=record=>({PAYMENT:'Money out',RECEIPT:'Money in',CONTRA:'Transfer',OPENING:'Opening balance',JOURNAL:'Accountant adjustment',REVERSAL:'Correction'}[record.kind]||record.kind);
 if(view==='ADVANCED')return <MDAccounting initialTab={advanced.tab} initialVoucherId={advanced.voucherId} onBack={returnFromAdvanced}/>;
 return <MainLayout><div className="space-y-5">
  <header className="flex flex-wrap items-center justify-between gap-3"><div><h1 className="text-2xl font-semibold text-slate-900">Company Money</h1><p className="mt-1 text-sm text-slate-500">Record money simply. Review your business in detail.</p></div><button disabled={busy} onClick={()=>refresh().catch(error=>setError(accountingError(error)))} className={button}>Refresh records</button></header>
  <nav className="flex flex-wrap gap-2" aria-label="Company money navigation">{[['RECORD','Record Money'],['BANK','Bank Review'],['REPORTS','Reports']].map(([key,label])=><button key={key} disabled={busy} onClick={()=>setView(key)} className={`${button} ${view===key?'bg-slate-900 text-white':'bg-white'}`}>{label}</button>)}<button disabled={busy} onClick={()=>openAdvanced()} className={`${button} bg-white text-slate-600`}>Advanced Accounting</button></nav>
  {error&&<p role="alert" className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}{message&&<p role="status" className="rounded-xl bg-teal-50 p-3 text-sm text-teal-800">{message}</p>}{warning&&<p role="status" className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">{warning}</p>}
  {!options||!setup?<section className="rounded-xl border bg-white p-5"><p>Loading company accounts…</p><button onClick={()=>refresh().catch(error=>setError(accountingError(error)))} className={`${button} mt-3`}>Retry loading accounts</button></section>:<>
   {!setup.opening_confirmed&&<section className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4"><p className="text-sm text-amber-900">Finish opening balances before confirming records into the books. You can prepare drafts now.</p><button disabled={busy} onClick={()=>openAdvanced('Setup')} className={`${button} bg-white`}>Complete books setup</button></section>}
   {view==='RECORD'&&<>
    <section className="grid gap-3 sm:grid-cols-3">{types.map(([type,title,description])=><button key={type} aria-label={title} disabled={busy} onClick={()=>start(type)} className={`rounded-2xl border p-5 text-left ${!saved&&form.transaction_type===type?'border-teal-600 bg-teal-50':'bg-white'}`}><span className="block text-lg font-semibold">{title}</span><span className="mt-1 block text-sm text-slate-500">{description}</span></button>)}</section>
    <section className="rounded-2xl border bg-white p-5 sm:p-6" aria-label="Everyday money record">
    {saved?<div className="space-y-4"><div className="flex flex-wrap justify-between gap-2"><h2 className="text-xl font-semibold">{kindName(saved)} · {money(saved.debit_total)}</h2><span className="rounded-full bg-slate-100 px-3 py-1 text-sm">{saved.status==='POSTED'?'Recorded':'Draft — not yet in reports'}</span></div><p className="text-sm text-slate-500">{saved.voucher} · {saved.entry_date}</p><dl className="grid gap-4 sm:grid-cols-2">{[['Who',saved.party||'Company account transfer'],['Accounts',saved.lines.map(line=>line.account_name).join(' · ')],['Purpose',saved.narration],['Reference',saved.reference||'Not provided']].map(([label,value])=><div key={label}><dt className="text-sm text-slate-500">{label}</dt><dd className="font-medium">{value}</dd></div>)}</dl>{saved.status==='DRAFT'?<div className="flex flex-wrap gap-3"><button disabled={busy||!setup.opening_confirmed} onClick={postRecord} className={`${button} bg-teal-700 text-white`}>Confirm and record</button><button disabled={busy} onClick={()=>openAdvanced('Books',saved.id)} className={button}>Adjust draft in Advanced</button></div>:<p className="text-sm text-teal-800">Saved in the books. Use Reports or Bank Review to see the result.</p>}<button disabled={busy} onClick={()=>start()} className={button}>Record another transaction</button></div>:
    <><h2 className="mb-4 text-lg font-semibold">{types.find(([type])=>type===form.transaction_type)[1]}</h2><form onSubmit={review} className="space-y-4"><fieldset disabled={busy} className="grid gap-4 sm:grid-cols-2">
     <Label label="Date"><input aria-label="Money date" required type="date" max={today()} value={form.entry_date} onChange={event=>update('entry_date',event.target.value)} className={field}/></Label>
     <Label label={form.transaction_type==='MONEY_IN'?'Received into':'Paid from'}><select aria-label="Money account" required value={form.bank_account_id} onChange={event=>update('bank_account_id',event.target.value)} className={field}><option value="">Choose a company bank or cash account</option>{options.banks.map(account=><option key={account.id} value={account.id}>{account.name}</option>)}</select></Label>
     {form.transaction_type==='TRANSFER'?<Label label="Transfer to"><select aria-label="Transfer destination" required value={form.counter_account_id} onChange={event=>update('counter_account_id',event.target.value)} className={field}><option value="">Choose another company account</option>{options.banks.filter(account=>String(account.id)!==String(form.bank_account_id)).map(account=><option key={account.id} value={account.id}>{account.name}</option>)}</select></Label>:<>
      <Label label={form.transaction_type==='MONEY_OUT'?'What was the payment for?':'Why was money received?'}><select aria-label="Money purpose type" required value={form.category} onChange={event=>update('category',event.target.value)} className={field}><option value="">Choose the business reason</option>{options.categories[form.transaction_type].map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></Label>
      <Label label="Record under"><select aria-label="Money category" required disabled={!category} value={form.counter_account_id} onChange={event=>update('counter_account_id',event.target.value)} className={field}><option value="">Choose a category</option>{category?.accounts.map(account=><option key={account.id} value={account.id}>{account.name}</option>)}</select></Label>
      <Label label={form.transaction_type==='MONEY_OUT'?'Paid to':'Received from'}><input aria-label="Money party" required maxLength={200} value={form.party} onChange={event=>update('party',event.target.value)} className={field}/></Label>
     </>}
     <Label label="Amount (INR)"><input aria-label="Money amount" required type="number" min="0.01" max="999999999999.99" step="0.01" value={form.amount} onChange={event=>update('amount',event.target.value)} className={field}/></Label>
     <Label label="Purpose / details"><input aria-label="Money description" required minLength={3} maxLength={1000} value={form.purpose} onChange={event=>update('purpose',event.target.value)} className={field}/></Label>
     <Label label="Bank reference or bill number"><input aria-label="Money reference" maxLength={150} value={form.reference} onChange={event=>update('reference',event.target.value)} className={field}/></Label>
    </fieldset><button disabled={busy} className={`${button} bg-slate-900 text-white`}>Review record</button></form>
    {preview&&<section className="mt-5 space-y-3 rounded-xl border border-teal-200 bg-teal-50 p-4" aria-label="Money record preview"><h3 className="font-semibold">Check before saving</h3><p className="text-lg font-semibold">{money(preview.amount)} · {preview.category}</p><p className="text-sm">From {preview.from_account} → {preview.to_account}</p><p className="text-sm">Record under: {preview.record_as}</p><p className="text-sm">{preview.purpose}</p><button disabled={busy} onClick={saveDraft} className={`${button} bg-teal-700 text-white`}>Save draft</button><p className="text-xs text-slate-600">You will confirm the saved draft before it enters reports.</p></section>}
    <p className="mt-4 text-xs text-slate-500">Need a tax split, payroll adjustment or another complex entry? Use Advanced Accounting. Recording here does not send a bank payment.</p></>}
    </section>
    <section className="rounded-2xl border bg-white p-5"><h2 className="mb-4 text-lg font-semibold">Recent records</h2><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr>{['Date','Type / who','Purpose / reference','Amount','Status',''].map((label,index)=><th key={index} className="border-b p-2">{label}</th>)}</tr></thead><tbody>{records.map(record=><tr key={record.id} className="border-b"><td className="p-2">{record.entry_date}</td><td className="p-2">{kindName(record)}<p className="text-xs text-slate-500">{record.party}</p></td><td className="p-2">{record.narration}<p className="text-xs text-slate-500">{record.reference}</p></td><td className="p-2">{money(record.debit_total)}</td><td className="p-2">{record.status==='POSTED'?'Recorded':'Draft'}</td><td className="p-2"><button disabled={busy} onClick={()=>openRecord(record)} className="text-teal-700">Review {record.voucher}</button></td></tr>)}</tbody></table></div>{!records.length&&<p className="text-sm text-slate-500">No records yet. Start with Money Out, Money In or Transfer.</p>}<p className="mt-3 text-xs text-slate-500">Latest 200 records. Reports include all posted records within the selected dates.</p></section>
   </>}
   {view==='BANK'&&<BankReview options={options} setup={setup} onRecord={recordBankRow} onBusy={setBusy}/>}
   {view==='REPORTS'&&<MoneyReports initial={dashboard} onAdvanced={()=>openAdvanced('Reports')}/>}
  </>}
 </div></MainLayout>;
}
