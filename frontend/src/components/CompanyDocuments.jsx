import { useCallback, useEffect, useState } from 'react';
import { Upload, FileText, Download, Archive } from 'lucide-react';
import api from '../api/axios';

const initialForm = { document_type: 'COI', title: '', document_number: '', issue_date: '', expiry_date: '' };
const inputClass = 'mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm';

function detail(err) {
  const value = err?.response?.data?.detail;
  return typeof value === 'string' ? value : 'Unable to complete this document action. Please retry.';
}

export default function CompanyDocuments({ canUpload, isOwner }) {
  const [data, setData] = useState({ documents: [], document_types: {} });
  const [form, setForm] = useState(initialForm);
  const [file, setFile] = useState(null);
  const [inputVersion, setInputVersion] = useState(0);
  const [loading, setLoading] = useState(true);
  const [storageReady, setStorageReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const load = useCallback(async signal => {
    try {
      const results = await Promise.allSettled([api.get('/erp/company/documents', { signal }), api.get('/erp/company/documents/storage-status', { signal })]);
      if (results[0].status === 'rejected') throw results[0].reason;
      setData(results[0].value.data);
      setStorageReady(results[1].status === 'fulfilled' && results[1].value.data.ready);
      if (results[1].status === 'rejected' && !signal?.aborted) setError(detail(results[1].reason));
    } catch (err) {
      if (!signal?.aborted) setError(detail(err));
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  async function upload(event) {
    event.preventDefault();
    setError(''); setMessage('');
    if (!file) return setError('Choose a document to upload.');
    if (file.size > 3 * 1024 * 1024) return setError('Maximum document size is 3 MB.');
    setBusy(true);
    const body = new FormData();
    Object.entries(form).forEach(([key, value]) => body.append(key, value));
    body.append('file', file);
    try {
      await api.post('/erp/company/documents', body, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 60000 });
      setForm(initialForm); setFile(null); setInputVersion(version => version + 1);
      setMessage('Legal document uploaded successfully.');
      await load();
    } catch (err) { setError(detail(err)); }
    finally { setBusy(false); }
  }
  async function download(document) {
    setError(''); setBusy(true);
    const opened = window.open('about:blank', '_blank');
    if (opened) opened.opener = null;
    try {
      const { data: result } = await api.get(`/erp/company/documents/${document.id}/download`, { timeout: 30000 });
      if (opened) opened.location.href = result.url;
      else setError('Allow pop-ups for this ERP to open the document, then try again.');
    } catch (err) { if (opened) opened.close(); setError(detail(err)); }
    finally { setBusy(false); }
  }
  async function archive(document) {
    setError(''); setMessage(''); setBusy(true);
    try {
      await api.post(`/erp/company/documents/${document.id}/archive`);
      setMessage('Document archived. The original remains in the company records.');
      await load();
    } catch (err) { setError(detail(err)); }
    finally { setBusy(false); }
  }

  return <section className="rounded-xl border border-slate-200 bg-white p-5 sm:p-6">
    <h2 className="flex items-center gap-2 font-semibold text-slate-900"><FileText className="h-5 w-5 text-teal-700" />Company legal documents</h2>
    <p className="mt-1 text-sm text-slate-500">Private records for internal staff. Employee and client accounts cannot access these files.</p>
    <p className="mt-2 text-xs text-slate-500">PDF, JPG or PNG · Up to 3 MB per file · After profile submission, only the Owner can upload additional documents. Only the Owner can archive records.</p>
    {error && <div role="alert" className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>}
    {message && <div role="status" className="mt-4 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">{message}</div>}
    {canUpload && <form onSubmit={upload} className="mt-5 space-y-4 rounded-lg border border-slate-200 bg-slate-50/50 p-4"><fieldset disabled={busy} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"><label className="text-sm font-medium text-slate-700" htmlFor="company-document-type">Category<select id="company-document-type" value={form.document_type} onChange={event => setForm(previous => ({ ...previous, document_type: event.target.value }))} className={inputClass}>{Object.entries(data.document_types).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>{[['title', 'Document title', 'text', 200], ['document_number', 'Document number', 'text', 100], ['issue_date', 'Issue date', 'date'], ['expiry_date', 'Expiry date', 'date']].map(([name, label, type, maxLength]) => <label key={name} htmlFor={`document-${name}`} className="text-sm font-medium text-slate-700">{label}<input id={`document-${name}`} type={type} maxLength={maxLength} value={form[name]} onChange={event => setForm(previous => ({ ...previous, [name]: event.target.value }))} className={inputClass} /></label>)}</div>
      <label htmlFor="company-document-file" className="block text-sm font-medium text-slate-700">Choose file<input key={inputVersion} id="company-document-file" type="file" accept="application/pdf,image/jpeg,image/png" required onChange={event => setFile(event.target.files?.[0] || null)} className="mt-2 block w-full text-sm text-slate-600" /></label>
      <button type="submit" disabled={busy || loading || !storageReady} className="inline-flex items-center gap-2 rounded-lg bg-teal-700 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"><Upload className="h-4 w-4" />{busy ? 'Uploading…' : 'Upload legal document'}</button>
    </fieldset></form>}
    <div className="mt-5 space-y-3">{loading ? <p className="text-sm text-slate-500">Loading documents…</p> : data.documents.length === 0 ? <p className="text-sm text-slate-500">No company legal documents uploaded yet.</p> : data.documents.map(document => <div key={document.id} className={`flex flex-wrap items-center justify-between gap-3 rounded-lg border p-4 ${document.is_archived ? 'border-slate-200 bg-slate-50' : 'border-slate-200'}`}><div><p className="text-sm font-semibold text-slate-900">{document.title}{document.is_archived && <span className="ml-2 text-xs text-slate-500">Archived</span>}</p><p className="mt-1 break-all text-xs text-slate-500">{document.original_filename} · {(document.size_bytes / 1024).toFixed(0)} KB · {data.document_types[document.document_type]}</p>{document.document_number && <p className="mt-1 text-xs text-slate-500">Number: {document.document_number}</p>}{(document.issue_date || document.expiry_date) && <p className="mt-1 text-xs text-slate-500">{document.issue_date && `Issued: ${document.issue_date}`} {document.expiry_date && `Expires: ${document.expiry_date}`}</p>}</div><div className="flex gap-3"><button type="button" onClick={() => download(document)} disabled={busy} className="inline-flex items-center gap-1.5 text-sm font-medium text-teal-700"><Download className="h-4 w-4" />Open</button>{isOwner && !document.is_archived && <button type="button" onClick={() => archive(document)} disabled={busy} className="inline-flex items-center gap-1.5 text-sm text-slate-500"><Archive className="h-4 w-4" />Archive</button>}</div></div>)}</div>
  </section>;
}
