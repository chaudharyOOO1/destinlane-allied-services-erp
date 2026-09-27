import { useEffect, useState } from 'react';
import MainLayout from '../layouts/MainLayout';
import api from '../api/axios';
import { Upload, RefreshCw, Search, Database, Building2, CheckCircle2, AlertTriangle } from 'lucide-react';

export default function IfscMaster() {
  const [stats,setStats]=useState({total:0,approved:0,banks:0});
  const [rows,setRows]=useState([]);
  const [search,setSearch]=useState('');
  const [file,setFile]=useState(null);
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState('');
  const [error,setError]=useState('');

  async function load() {
    setError('');
    try {
      const [s,r]=await Promise.all([
        api.get('/erp/ifsc/stats'),
        api.get('/erp/ifsc',{params:{search:search||undefined,limit:100}})
      ]);
      setStats(s.data||{});
      setRows(r.data||[]);
    } catch(e) { setError(e.response?.data?.detail||'Unable to load IFSC master.'); }
  }
  useEffect(()=>{load();},[]);

  async function importFile(e) {
    e.preventDefault();
    if(!file) return;
    setBusy(true); setMessage(''); setError('');
    try {
      const fd=new FormData();
      fd.append('file',file);
      const r=await api.post('/erp/ifsc/import-csv',fd,{headers:{'Content-Type':'multipart/form-data'}});
      setMessage(`Imported ${r.data.imported.toLocaleString('en-IN')} IFSC records. ${r.data.invalid_rows_skipped||0} invalid rows skipped.`);
      setFile(null);
      e.target.reset();
      await load();
    } catch(err) { setError(err.response?.data?.detail||'IFSC import failed.'); }
    finally { setBusy(false); }
  }

  return <MainLayout>
    <div className="space-y-6">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Administrator / Master Data</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">IFSC Master</h1>
        <p className="mt-1 text-sm text-slate-500">Approved bank and branch database used to validate employee bank details.</p>
      </header>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Metric icon={Database} label="IFSC Records" value={stats.total||0}/>
        <Metric icon={CheckCircle2} label="Approved" value={stats.approved||0}/>
        <Metric icon={Building2} label="Banks" value={stats.banks||0}/>
      </div>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-start gap-3">
          <div className="rounded-xl bg-slate-100 p-2.5"><Upload className="h-5 w-5 text-slate-700"/></div>
          <div className="flex-1">
            <h2 className="font-semibold text-slate-950">Import approved IFSC database</h2>
            <p className="mt-1 text-xs leading-5 text-slate-500">Upload a UTF-8 CSV. Required columns: <b>IFSC</b> and <b>Bank</b>. Optional: Branch, Address, City, District, State. Existing IFSC codes are updated.</p>
            <form onSubmit={importFile} className="mt-4 flex flex-col gap-3 md:flex-row md:items-center">
              <input type="file" accept=".csv,text/csv" onChange={e=>setFile(e.target.files?.[0]||null)} className="block w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"/>
              <button disabled={!file||busy} className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40">
                <Upload className="h-4 w-4"/> {busy?'Importing…':'Import CSV'}
              </button>
            </form>
            <div className="mt-3 rounded-xl border border-amber-100 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              <AlertTriangle className="mr-1 inline h-3.5 w-3.5"/> Only an Administrator can import or replace IFSC records.
            </div>
          </div>
        </div>
      </section>

      {message&&<div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{message}</div>}
      {error&&<div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}

      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-3 border-b border-slate-200 p-4 md:flex-row md:items-center">
          <div className="relative flex-1"><Search className="absolute left-3 top-3 h-4 w-4 text-slate-400"/><input value={search} onChange={e=>setSearch(e.target.value)} onKeyDown={e=>e.key==='Enter'&&load()} placeholder="Search IFSC, bank or branch…" className="w-full rounded-xl border border-slate-200 py-2.5 pl-9 pr-3 text-sm outline-none focus:border-slate-400"/></div>
          <button onClick={load} className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-700"><RefreshCw className="h-4 w-4"/> Refresh</button>
        </div>
        <div className="overflow-auto">
          <table className="min-w-[900px] w-full text-left text-sm">
            <thead><tr className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              {['IFSC','Bank','Branch','City','District','State','Status'].map(h=><th key={h} className="px-4 py-3">{h}</th>)}
            </tr></thead>
            <tbody>{rows.map(r=><tr key={r.ifsc_code} className="border-b border-slate-100 last:border-0 hover:bg-slate-50/70">
              <td className="px-4 py-3 font-mono text-xs font-semibold text-slate-900">{r.ifsc_code}</td><td className="px-4 py-3 font-medium">{r.bank_name}</td><td className="px-4 py-3 text-slate-600">{r.branch_name||'—'}</td><td className="px-4 py-3 text-slate-600">{r.city||'—'}</td><td className="px-4 py-3 text-slate-600">{r.district||'—'}</td><td className="px-4 py-3 text-slate-600">{r.state||'—'}</td><td className="px-4 py-3"><span className="rounded-full bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700">Approved</span></td>
            </tr>)}{!rows.length&&<tr><td colSpan="7" className="px-4 py-12 text-center text-slate-400">No approved IFSC records found. Import your approved CSV above.</td></tr>}</tbody>
          </table>
        </div>
      </section>
    </div>
  </MainLayout>;
}
function Metric({icon:Icon,label,value}){return <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs font-semibold text-slate-500"><Icon className="h-4 w-4"/>{label}</div><div className="mt-2 text-2xl font-semibold text-slate-950">{Number(value||0).toLocaleString('en-IN')}</div></div>}
