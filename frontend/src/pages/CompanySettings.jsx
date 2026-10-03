import { useCallback, useEffect, useState } from 'react';
import { Building2, Save, Plus, RefreshCw, CheckCircle2 } from 'lucide-react';
import MainLayout from '../layouts/MainLayout';
import { useAuth } from '../context/AuthContext';
import { useCompany } from '../context/CompanyContext';
import api from '../api/axios';
import CompanyDocuments from '../components/CompanyDocuments';

const inputClass = 'mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-600/10';
const months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

function Field({ name, label, value, onChange, required = false, type = 'text', maxLength, readOnly = false, ...rest }) {
  return <label className="block text-sm font-medium text-slate-700" htmlFor={name}>
    {label}{required && <span className="ml-1 text-teal-700">*</span>}
    <input id={name} name={name} type={type} value={value ?? ''} onChange={event => onChange(event.target.value)} required={required} maxLength={maxLength} readOnly={readOnly} className={`${inputClass} ${readOnly ? 'bg-slate-50 text-slate-500' : ''}`} {...rest} />
  </label>;
}

function Section({ title, description, children }) {
  return <section className="rounded-xl border border-slate-200 bg-white p-5 sm:p-6">
    <h2 className="font-semibold text-slate-900">{title}</h2>
    <p className="mt-1 text-sm text-slate-500">{description}</p>
    <div className="mt-5">{children}</div>
  </section>;
}

function errorMessage(err) {
  const detail = err?.response?.data?.detail;
  if (Array.isArray(detail)) return detail.map(item => item.msg.replace(/^Value error, /, '')).join(' ');
  return typeof detail === 'string' ? detail : 'Unable to save company settings. Please retry.';
}

export default function CompanySettings() {
  const { user } = useAuth();
  const { updateCompany } = useCompany();
  const canManage = ['OWNER', 'SUPER_ADMIN', 'ADMIN', 'HR', 'OPERATIONS', 'ACCOUNTS'].includes(user?.role);
  const isOwner = user?.role === 'OWNER';
  const [form, setForm] = useState(null);
  const [saved, setSaved] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const canEdit = ['OWNER', 'SUPER_ADMIN', 'ADMIN'].includes(user?.role) && (saved?.status !== 'SUBMITTED' || isOwner);

  const applySaved = useCallback(data => {
    setSaved(data);
    setForm({ ...data.profile, branches: data.profile.branches.map(branch => ({ ...branch, originalCode: branch.code, rowKey: crypto.randomUUID() })) });
    setDirty(false);
  }, []);

  const load = useCallback(async signal => {
    try {
      const { data } = await api.get('/erp/company', { signal });
      applySaved(data);
    } catch (err) {
      if (!signal?.aborted) setError(errorMessage(err));
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [applySaved]);

  useEffect(() => {
    if (!canManage) return;
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [canManage, load]);

  function update(name, value) {
    setForm(previous => ({ ...previous, [name]: value }));
    setDirty(true);
    setMessage('');
  }
  function updateBranch(rowKey, name, value) {
    update('branches', form.branches.map(branch => branch.rowKey === rowKey ? { ...branch, [name]: value } : branch));
  }
  function addBranch() {
    update('branches', [...form.branches, { rowKey: crypto.randomUUID(), code: '', name: '', address: '', city: '', state: '', pincode: '', is_active: true }]);
  }

  async function submit(event, finalize = false) {
    event.preventDefault();
    setError('');
    setMessage('');
    setSaving(true);
    const profile = { ...form, registration_date: form.registration_date || null, gst_registration_date: form.gst_registration_date || null, branches: form.branches.map(({ rowKey: _rowKey, originalCode: _originalCode, ...branch }) => branch) };
    try {
      const { data } = await api.put('/erp/company', { version: saved.version, profile, submit: finalize });
      applySaved(data);
      const publicKeys = ['legal_name','display_name','address','city','state','pincode','contact_email','contact_phone','website','gstin'];
      const displayProfile = Object.fromEntries(publicKeys.map(key => [key, data.profile[key]]));
      displayProfile.address = data.profile.registered_office || data.profile.address;
      updateCompany(displayProfile);
      setMessage(finalize ? 'Company profile submitted. Only the Owner can make further changes.' : 'Company settings saved successfully.');
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  const basicFields = [
    ['legal_name', 'Legal company name', 200, true], ['display_name', 'Display name', 120, true],
    ['company_type', 'Company type', 100], ['registration_authority', 'Registration authority / ROC', 200], ['city', 'City', 100], ['state', 'State', 100], ['pincode', 'PIN code', 6],
    ['contact_email', 'Company contact email', 254, false, 'email'], ['contact_phone', 'Company contact phone', 25, false, 'tel'],
    ['website', 'Website (https://...)', 500, false, 'url'],
  ];

  return <MainLayout><div className="mx-auto max-w-5xl space-y-5">
    <div className="flex items-start gap-3"><Building2 className="mt-1 h-7 w-7 text-teal-700" /><div><h1 className="text-2xl font-bold text-slate-950">Company Setup</h1><p className="mt-1 text-sm text-slate-500">Company profile, registrations, branches and legal records.</p></div></div>
    {!canManage ? <p className="rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-600">Company legal records are available to internal staff only.</p> : <>
      {error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}<button type="button" onClick={() => { setLoading(true); setError(''); load(); }} disabled={saving} className="ml-3 font-semibold underline">Reload saved settings</button></div>}
      {message && <div role="status" className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800"><CheckCircle2 className="h-4 w-4" />{message}</div>}
      {saved && <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600"><span className="font-semibold text-slate-900">{saved.status === 'SUBMITTED' ? 'Submitted profile' : 'Draft profile'}</span> · {saved.status === 'SUBMITTED' ? 'Only the Owner can edit this profile and add legal documents.' : 'Administrators can prepare the draft. Submission locks changes to the Owner.'}{!canEdit && <p className="mt-1">You can view the company profile and legal documents.</p>}</div>}
      {loading ? <p className="p-5 text-sm text-slate-500">Loading company settings…</p> : form && <form onSubmit={event => submit(event)} className="space-y-5">
        <fieldset disabled={saving || !canEdit} className="space-y-5">
          <Section title="Company identity and contact" description="Use the details from your company records. Unknown details can stay blank.">
            <div className="grid gap-5 sm:grid-cols-2">{basicFields.map(([name, label, maxLength, required, type]) => <Field key={name} name={name} label={label} maxLength={maxLength} required={required} type={type} value={form[name]} onChange={value => update(name, value)} />)}</div>
            <label htmlFor="company-address" className="mt-5 block text-sm font-medium text-slate-700">Operating / correspondence address<textarea id="company-address" value={form.address} onChange={event => update('address', event.target.value)} maxLength={1000} rows={3} className={inputClass} /></label>
            <label htmlFor="registered-office" className="mt-5 block text-sm font-medium text-slate-700">Registered office address<textarea id="registered-office" value={form.registered_office} onChange={event => update('registered_office', event.target.value)} maxLength={1000} rows={3} className={inputClass} /></label>
            <label htmlFor="business-description" className="mt-5 block text-sm font-medium text-slate-700">Company profile / business activities<textarea id="business-description" value={form.business_description} onChange={event => update('business_description', event.target.value)} maxLength={3000} rows={4} className={inputClass} /></label>
          </Section>
          <Section title="Registrations" description="These fields check format and consistency. Enter identifiers from your actual registrations.">
            <div className="grid gap-5 sm:grid-cols-2">{[['gstin', 'GSTIN', 15], ['pan', 'PAN', 10], ['cin', 'CIN', 21], ['tan', 'TAN', 10], ['pf_registration_number', 'PF registration number', 100], ['esic_registration_number', 'ESIC registration number', 100], ['udyam_registration_number', 'Udyam registration number', 100], ['labour_registration_number', 'Labour registration number', 100], ['psara_registration_number', 'PSARA licence number', 100]].map(([name, label, maxLength]) => <Field key={name} name={name} label={label} maxLength={maxLength} value={form[name]} onChange={value => update(name, value.toUpperCase())} />)}</div>
            <div className="mt-5 grid gap-5 sm:grid-cols-2"><Field name="registration_date" label="Company registration / incorporation date" type="date" value={form.registration_date} onChange={value => update('registration_date', value)} /><Field name="gst_registration_date" label="GST registration date" type="date" value={form.gst_registration_date} onChange={value => update('gst_registration_date', value)} /></div>
            <p className="mt-4 text-xs text-slate-500">Legal identifiers remain in the internal staff profile. Document headers use the company name, contact details and GSTIN.</p>
          </Section>
          <Section title="Financial year" description="Choose the financial year used for your company records. Payroll and invoice calculations will be checked in their scheduled stages.">
            <div className="grid gap-5 sm:grid-cols-3"><Field name="financial_year_start_year" label="Starting year" type="number" min={2000} max={2100} required value={form.financial_year_start_year} onChange={value => update('financial_year_start_year', value === '' ? '' : Number(value))} /><label htmlFor="financial_year_start_month" className="text-sm font-medium text-slate-700">Starting month<select id="financial_year_start_month" value={form.financial_year_start_month} onChange={event => update('financial_year_start_month', Number(event.target.value))} className={inputClass}>{months.map((month, index) => <option key={month} value={index + 1}>{month}</option>)}</select></label><Field name="currency" label="Currency" value="INR — Indian Rupee" readOnly onChange={() => {}} /></div>
            {saved?.financial_year && <p className="mt-4 text-xs text-slate-500">Saved financial year: {saved.financial_year.start} to {saved.financial_year.end}</p>}
          </Section>
          <Section title="Branches" description="Add your actual branches. Saved branch codes stay fixed; mark a branch inactive when it closes.">
            <div className="space-y-4">{form.branches.length === 0 && <p className="text-sm text-slate-500">No branches added yet.</p>}{form.branches.map(branch => {
              const existing = Boolean(branch.originalCode);
              return <div key={branch.rowKey} className="rounded-lg border border-slate-200 bg-slate-50/50 p-4"><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{[['code', 'Branch code', 20, true], ['name', 'Branch name', 120, true], ['city', 'City', 100], ['state', 'State', 100], ['pincode', 'PIN code', 6], ['address', 'Branch address', 1000]].map(([name, label, maxLength, required]) => <Field key={name} name={`${branch.rowKey}-${name}`} label={label} maxLength={maxLength} required={required} readOnly={name === 'code' && existing} value={branch[name]} onChange={value => updateBranch(branch.rowKey, name, name === 'code' ? value.toUpperCase() : value)} />)}</div><div className="mt-4 flex items-center justify-between"><label className="flex items-center gap-2 text-sm text-slate-700"><input type="checkbox" checked={branch.is_active} onChange={event => updateBranch(branch.rowKey, 'is_active', event.target.checked)} />Active branch</label>{!existing && <button type="button" onClick={() => update('branches', form.branches.filter(item => item.rowKey !== branch.rowKey))} className="text-sm text-rose-700">Remove unsaved branch</button>}</div></div>;
            })}</div>
            <button type="button" onClick={addBranch} disabled={form.branches.length >= 100} className="mt-4 inline-flex items-center gap-2 rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700"><Plus className="h-4 w-4" />Add branch</button>
          </Section>
        </fieldset>
        {canEdit && <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-slate-200 bg-white p-4"><p className="text-xs text-slate-500">{dirty ? 'You have unsaved changes.' : saved.updated_at ? `Last saved: ${new Date(saved.updated_at).toLocaleString('en-IN')}` : 'Company details have not been saved yet.'}</p><button type="submit" disabled={saving || !dirty} className="inline-flex items-center gap-2 rounded-lg bg-teal-700 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50">{saving ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}{saving ? 'Saving…' : 'Save draft / changes'}</button>{saved.status !== 'SUBMITTED' && <button type="button" onClick={event => submit(event, true)} disabled={saving || !form.registration_date} className="rounded-lg border border-teal-700 px-5 py-2.5 text-sm font-semibold text-teal-800 disabled:opacity-50">Submit and lock profile</button>}</div>}
      </form>}
      {!loading && form && <CompanyDocuments canUpload={canEdit} isOwner={isOwner} />}
    </>}
  </div></MainLayout>;
}
