import { useEffect, useMemo, useState } from 'react';
import MainLayout from '../layouts/MainLayout';
import api from '../api/axios';
import {
  AlertTriangle, Banknote, BadgeCheck, CalendarDays, Camera, CheckCircle2,
  ChevronRight, ClipboardCheck, Download, FileCheck2, FileText, HeartPulse,
  Landmark, LockKeyhole, Plus, RefreshCw, Search, ShieldCheck, UserRound,
  UsersRound, X, Upload, WalletCards
} from 'lucide-react';

const EMPTY_MASTER = {
  employee_code: '', name: '', phone: '', dob: '', gender: '', designation: '',
  branch: '', site_id: '', joining_date: '', category: 'GUARD', status: 'active',
  intimation_id: '', emergency_contact: '', marital_status: '',
  aadhaar_no: '', pan_no: '', permanent_address: '', present_address: '',
};

const EMPTY_ADVANCED = {
  nominee_name: '', nominee_relation: '', nominee_dob: '', nominee_aadhaar: '', nominee_percentage: '100',
  bank_account_no: '', bank_name: '', bank_branch: '', bank_ifsc: '',
  gun_license_no: '', arms_issuing_authority: '', gun_license_expiry: '', arms_caliber: '',
  weapon_serial_no: '', ammunition_count: '',
  uniform_shirt: false, uniform_trousers: false, uniform_shoes: false, uniform_belt: false, uniform_cap: false,
  uniform_total_cost: '', uniform_monthly_emi: '',
  police_station: '', police_verification_expiry: '', medical_exam_date: '', medical_fitness_expiry: '',
  psara_batch_no: '', psara_skill_level: '', psara_training_expiry: '',
  form11_uploaded: false, passbook_uploaded: false, gun_license_uploaded: false,
};

const SUBTABS = [
  ['master', 'Create Master', UserRound],
  ['compliance', 'Compliance & Documents', ShieldCheck],
  ['attendance', 'Reports & Attendance', ClipboardCheck],
  ['payroll', 'Payroll & Salary', WalletCards],
];

const CATEGORY_OPTIONS = ['GUARD', 'GUNMAN', 'SUPERVISOR', 'FIELD_OFFICER', 'JANITOR', 'CLEANER', 'FACILITY_ATTENDANT', 'GDA', 'NURSE_ASSISTANT', 'HOSPITAL_ATTENDANT'];

function verhoeff(number) {
  if (!/^\d{12}$/.test(number)) return false;
  const d=[[0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,1,6,4,2],[8,7,9,0,6,4,3,5,2,1],[6,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,1,6,4,2],[8,7,9,0,6,4,3,5,2,1],[6,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4]];
  const p=[[0,1,2,3,4,5,6,7,8,9],[0,5,7,8,9,4,2,1,3,6],[0,8,1,4,6,3,5,9,7,2],[0,9,4,7,2,6,3,8,5,1],[0,4,8,1,6,2,9,5,7,3],[0,2,9,5,1,7,4,8,6,3],[0,7,3,6,4,5,2,9,8,1],[0,3,5,2,7,9,8,6,1,4]];
  let c=0;
  [...number].reverse().forEach((n,i)=>{ c=d[c][p[i%8][Number(n)]]; });
  return c===0;
}

export default function Employees() {
  const [rows, setRows] = useState([]);
  const [staff, setStaff] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('ALL');
  const [subtab, setSubtab] = useState('master');
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_MASTER);
  const [advanced, setAdvanced] = useState(EMPTY_ADVANCED);
  const [saving, setSaving] = useState(false);
  const [photo, setPhoto] = useState('');
  const [ifscState, setIfscState] = useState({ state: 'idle', message: '' });

  async function load() {
    setLoading(true);
    setError('');
    try {
      const [employees, staffRows] = await Promise.all([
        api.get('/erp/employees'),
        api.get('/staff').catch(() => ({ data: [] })),
      ]);
      setRows(employees.data || []);
      setStaff(staffRows.data || []);
    } catch (e) {
      setError(e.response?.data?.detail || 'Unable to load employee master.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  const staffByEmployee = useMemo(() => {
    const map = {};
    staff.forEach((s) => { map[String(s.employee_id)] = s; });
    return map;
  }, [staff]);

  const filtered = rows.filter((x) => {
    const q = search.toLowerCase();
    const matchesSearch = [x.employee_code, x.name, x.phone, x.designation, x.branch, x.category]
      .some((v) => String(v || '').toLowerCase().includes(q));
    const matchesStatus = status === 'ALL' || String(x.status || '').toUpperCase() === status;
    return matchesSearch && matchesStatus;
  });

  const counts = useMemo(() => ({
    total: rows.length,
    active: rows.filter((x) => String(x.status).toLowerCase() === 'active').length,
    bench: rows.filter((x) => String(x.status).toLowerCase() === 'bench').length,
    inactive: rows.filter((x) => ['inactive', 'terminated'].includes(String(x.status).toLowerCase())).length,
  }), [rows]);

  function updateMaster(key, value) { setForm((f) => ({ ...f, [key]: value })); }
  function updateAdvanced(key, value) { setAdvanced((f) => ({ ...f, [key]: value })); }

  async function validateIfsc() {
    const code = advanced.bank_ifsc.trim().toUpperCase();
    if (!code) {
      setIfscState({ state: 'idle', message: '' });
      return false;
    }
    if (!/^[A-Z]{4}0[A-Z0-9]{6}$/.test(code)) {
      setIfscState({ state: 'error', message: 'Invalid IFSC format. Expected 11 characters, e.g. SBIN0001234.' });
      return false;
    }
    setIfscState({ state: 'checking', message: 'Checking IFSC against the approved bank database…' });
    try {
      const r = await api.get('/erp/ifsc/validate', { params: { ifsc: code } });
      if (r.data?.valid === true) {
        setIfscState({ state: 'valid', message: r.data.bank_name ? `Verified — ${r.data.bank_name}` : 'IFSC verified.' });
        return true;
      }
      setIfscState({ state: 'error', message: 'IFSC was not found in the approved bank database. Submission is blocked.' });
      return false;
    } catch (e) {
      setIfscState({
        state: 'error',
        message: e.response?.data?.detail || 'IFSC database validation is unavailable. Submission is blocked until it can be verified.',
      });
      return false;
    }
  }

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setError('');

    const aadhaar = String(form.aadhaar_no || '').replace(/\s/g, '');
    if (aadhaar && !verhoeff(aadhaar)) {
      setError('Aadhaar number failed the 12-digit Verhoeff checksum validation.');
      setSaving(false);
      setSubtab('master');
      return;
    }

    const ifscOk = await validateIfsc();
    if (!ifscOk) {
      setSaving(false);
      setSubtab('master');
      return;
    }

    try {
      await api.post('/erp/employees', {
        ...form,
        ...advanced,
        intimation_id: form.intimation_id || undefined,
        dob: form.dob || undefined,
        gender: form.gender || undefined,
        designation: form.designation || undefined,
        branch: form.branch || undefined,
        site_id: form.site_id || undefined,
        joining_date: form.joining_date || undefined,
        category: form.category || undefined,
        aadhaar_no: aadhaar || undefined,
        pan_no: form.pan_no || undefined,
        permanent_address: form.permanent_address || undefined,
        present_address: form.present_address || undefined,
        emergency_contact: form.emergency_contact || undefined,
        marital_status: form.marital_status || undefined,
        bank_ifsc: advanced.bank_ifsc?.trim().toUpperCase() || undefined,
      });
      setOpen(false);
      setForm(EMPTY_MASTER);
      setAdvanced(EMPTY_ADVANCED);
      setPhoto('');
      setIfscState({ state: 'idle', message: '' });
      await load();
    } catch (e) {
      setError(e.response?.data?.detail || 'Unable to create employee.');
    } finally {
      setSaving(false);
    }
  }

  function openCreate() {
    setForm({ ...EMPTY_MASTER, employee_code: '', intimation_id: '' });
    setAdvanced(EMPTY_ADVANCED);
    setPhoto('');
    setIfscState({ state: 'idle', message: '' });
    setOpen(true);
  }

  return (
    <MainLayout>
      <div className="space-y-6">
        <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Workforce / Employee Management</div>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">Employee Management</h1>
            <p className="mt-1 text-sm text-slate-500">Complete employee master, compliance, attendance and payroll control centre.</p>
          </div>
          <div className="flex gap-2">
            <button onClick={load} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-semibold text-slate-700 shadow-sm hover:bg-slate-50">
              <RefreshCw className="h-4 w-4" /> Refresh
            </button>
            <button onClick={openCreate} className="inline-flex items-center gap-2 rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-slate-800">
              <Plus className="h-4 w-4" /> Create Employee
            </button>
          </div>
        </header>

        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Metric icon={UsersRound} label="Total Employees" value={counts.total} />
          <Metric icon={CheckCircle2} label="Active" value={counts.active} />
          <Metric icon={AlertTriangle} label="Bench / Restricted" value={counts.bench} />
          <Metric icon={LockKeyhole} label="Inactive / Terminated" value={counts.inactive} />
        </div>

        <nav className="overflow-x-auto rounded-2xl border border-slate-200 bg-white p-1.5 shadow-sm">
          <div className="flex min-w-max gap-1">
            {SUBTABS.map(([id, label, Icon]) => (
              <button key={id} onClick={() => setSubtab(id)}
                className={`inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition ${subtab === id ? 'bg-slate-950 text-white shadow-sm' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'}`}>
                <Icon className="h-4 w-4" /> {label}
              </button>
            ))}
          </div>
        </nav>

        {error && <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}

        {subtab === 'master' && (
          <section className="space-y-4">
            <div className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm lg:flex-row">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-3 h-4 w-4 text-slate-400" />
                <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search name, employee ID, phone, designation, branch…" className="w-full rounded-xl border border-slate-200 py-2.5 pl-9 pr-3 text-sm outline-none focus:border-slate-400" />
              </div>
              <select value={status} onChange={(e) => setStatus(e.target.value)} className="rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-medium text-slate-700">
                <option value="ALL">All statuses</option><option value="ACTIVE">Active</option><option value="BENCH">Bench</option><option value="INACTIVE">Inactive</option><option value="TERMINATED">Terminated</option>
              </select>
              <button className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-700"><Download className="h-4 w-4" /> Export</button>
            </div>

            <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
              <table className="min-w-[1050px] w-full text-left text-sm">
                <thead><tr className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                  {['Employee', 'ID / Intimation', 'Designation', 'Branch / Site', 'Status', 'Compliance', 'Action'].map((h) => <th key={h} className="px-4 py-3.5">{h}</th>)}
                </tr></thead>
                <tbody>
                  {loading ? <tr><td colSpan="7" className="px-4 py-12 text-center text-slate-400">Loading employee master…</td></tr> :
                    filtered.map((x) => {
                      const s = staffByEmployee[String(x.id)];
                      const locked = s?.is_bench_locked || String(x.status).toLowerCase() === 'bench';
                      return <tr key={x.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50/70">
                        <td className="px-4 py-4"><div className="flex items-center gap-3"><div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-600"><UserRound className="h-5 w-5" /></div><div><div className="font-semibold text-slate-900">{x.name}</div><div className="text-xs text-slate-500">{x.phone || 'No phone'}</div></div></div></td>
                        <td className="px-4 py-4"><div className="font-mono text-xs font-semibold text-slate-800">{x.employee_code || '—'}</div><div className="mt-1 text-[11px] text-slate-400">{x.intimation_id || 'Intimation pending'}</div></td>
                        <td className="px-4 py-4"><div className="font-medium text-slate-800">{x.designation || '—'}</div><div className="text-xs text-slate-400">{x.category || '—'}</div></td>
                        <td className="px-4 py-4"><div className="font-medium text-slate-700">{x.branch || '—'}</div><div className="text-xs text-slate-400">{x.site_id || 'Site not allocated'}</div></td>
                        <td className="px-4 py-4"><StatusBadge value={locked ? 'BENCH' : String(x.status || 'UNKNOWN').toUpperCase()} /></td>
                        <td className="px-4 py-4">{locked ? <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-rose-600"><AlertTriangle className="h-3.5 w-3.5" /> Action required</span> : <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-600"><BadgeCheck className="h-3.5 w-3.5" /> Clear</span>}</td>
                        <td className="px-4 py-4"><button className="inline-flex items-center gap-1 text-xs font-semibold text-slate-700 hover:text-slate-950">View <ChevronRight className="h-3.5 w-3.5" /></button></td>
                      </tr>;
                    })}
                  {!loading && !filtered.length && <tr><td colSpan="7" className="px-4 py-12 text-center text-slate-400">No employees match the selected filters.</td></tr>}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {subtab === 'compliance' && <CompliancePanel staff={staff} />}
        {subtab === 'attendance' && <AttendancePanel rows={rows} />}
        {subtab === 'payroll' && <PayrollPanel staff={staff} />}
      </div>

      {open && <EmployeeModal
        form={form} advanced={advanced} photo={photo} setPhoto={setPhoto}
        updateMaster={updateMaster} updateAdvanced={updateAdvanced}
        ifscState={ifscState} validateIfsc={validateIfsc}
        saving={saving} save={save} close={() => setOpen(false)}
      />}
    </MainLayout>
  );
}

function EmployeeModal({ form, advanced, photo, setPhoto, updateMaster, updateAdvanced, ifscState, validateIfsc, saving, save, close }) {
  const [section, setSection] = useState('identity');
  const uniformItems = [['uniform_shirt', 'Shirt', 450], ['uniform_trousers', 'Trousers', 650], ['uniform_shoes', 'Shoes', 900], ['uniform_belt', 'Belt', 150], ['uniform_cap', 'Cap', 120]];
  const uniformCost = uniformItems.reduce((sum, [key, , cost]) => sum + (advanced[key] ? cost : 0), 0);

  const field = (key, label, opts = {}) => (
    <label className="block">
      <span className="mb-1.5 block text-xs font-semibold text-slate-600">{label}{opts.required && <span className="text-rose-500"> *</span>}</span>
      {opts.textarea ? <textarea value={form[key] ?? ''} onChange={(e) => updateMaster(key, e.target.value)} rows={3} className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-slate-400" /> :
        <input type={opts.type || 'text'} value={form[key] ?? ''} required={opts.required} onChange={(e) => updateMaster(key, e.target.value)} className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-slate-400" />}
    </label>
  );
  const advField = (key, label, opts = {}) => (
    <label className="block">
      <span className="mb-1.5 block text-xs font-semibold text-slate-600">{label}{opts.required && <span className="text-rose-500"> *</span>}</span>
      <input type={opts.type || 'text'} value={advanced[key] ?? ''} required={opts.required} onChange={(e) => updateAdvanced(key, e.target.value)} onBlur={opts.onBlur} className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-slate-400" />
    </label>
  );

  return <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/40 p-3 md:p-6">
    <div className="mx-auto max-w-6xl overflow-hidden rounded-3xl bg-white shadow-2xl">
      <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4 md:px-7">
        <div><div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">Employee onboarding</div><h2 className="mt-1 text-xl font-semibold text-slate-950">Create Employee Master</h2><p className="text-xs text-slate-500">Intimation, identity, KYC, bank, uniform and compliance capture.</p></div>
        <button onClick={close} className="rounded-xl p-2 text-slate-400 hover:bg-slate-100"><X className="h-5 w-5" /></button>
      </div>

      <div className="border-b border-slate-200 px-4 md:px-7">
        <div className="flex gap-1 overflow-x-auto py-2">{[['identity','Identity'],['personal','Personal & KYC'],['nominee','Nominee'],['bank','Bank'],['arms','Arms'],['uniform','Uniform EMI']].map(([id,label]) => <button type="button" key={id} onClick={() => setSection(id)} className={`whitespace-nowrap rounded-lg px-3 py-2 text-xs font-semibold ${section === id ? 'bg-slate-950 text-white' : 'text-slate-500 hover:bg-slate-50'}`}>{label}</button>)}</div>
      </div>

      <form onSubmit={save} className="max-h-[72vh] overflow-y-auto p-5 md:p-7">
        {section === 'identity' && <div className="space-y-6">
          <SectionTitle icon={UserRound} title="General Information" subtitle="The Intimation ID is generated automatically by the onboarding workflow." />
          <div className="grid gap-4 md:grid-cols-3">
            {field('name','Full Name',{required:true})}{field('dob','Date of Birth',{type:'date',required:true})}
            <SelectField label="Gender" value={form.gender} onChange={(v)=>updateMaster('gender',v)} options={['','Male','Female','Other']} required />
            {field('designation','Designation',{required:true})}{field('branch','Branch',{required:true})}{field('joining_date','Joining Date',{type:'date',required:true})}
            <SelectField label="Category" value={form.category} onChange={(v)=>updateMaster('category',v)} options={CATEGORY_OPTIONS} required />
            {field('phone','Mobile Number',{required:true})}{field('employee_code','Employee Code / ID',{required:false})}
          </div>
          <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-4">
            <div className="flex items-center gap-4">
              <div className="flex h-20 w-20 overflow-hidden items-center justify-center rounded-2xl bg-white border border-slate-200">{photo ? <img src={photo} className="h-full w-full object-cover" alt="Employee preview" /> : <Camera className="h-7 w-7 text-slate-300" />}</div>
              <div><div className="font-semibold text-slate-800">Employee photograph</div><div className="mt-1 text-xs text-slate-500">Upload or update the profile photograph.</div><label className="mt-2 inline-flex cursor-pointer items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold"><Upload className="h-3.5 w-3.5" /> Choose photo<input type="file" accept="image/*" className="hidden" onChange={(e)=>{const f=e.target.files?.[0]; if(f)setPhoto(URL.createObjectURL(f));}} /></label></div>
            </div>
          </div>
        </div>}

        {section === 'personal' && <div className="space-y-6">
          <SectionTitle icon={FileCheck2} title="Personal & KYC Details" subtitle="Aadhaar must pass the Verhoeff checksum before onboarding." />
          <div className="grid gap-4 md:grid-cols-2">{field('aadhaar_no','Aadhaar Number',{required:true})}{field('pan_no','PAN',{required:true})}{field('permanent_address','Permanent Address',{textarea:true,required:true})}{field('present_address','Present Address',{textarea:true,required:true})}{field('emergency_contact','Emergency Contact',{required:true})}<SelectField label="Marital Status" value={form.marital_status} onChange={(v)=>updateMaster('marital_status',v)} options={['','Single','Married','Other']} /></div>
        </div>}

        {section === 'nominee' && <div className="space-y-6"><SectionTitle icon={UsersRound} title="Nominee Details" subtitle="Nominee allocation must total 100%." /><div className="grid gap-4 md:grid-cols-2">{advField('nominee_name','Nominee Name',{required:true})}{advField('nominee_relation','Relation',{required:true})}{advField('nominee_dob','Nominee DOB',{type:'date',required:true})}{advField('nominee_aadhaar','Nominee Aadhaar',{required:true})}{advField('nominee_percentage','Allocation Percentage',{type:'number',required:true})}</div></div>}

        {section === 'bank' && <div className="space-y-6">
          <SectionTitle icon={Landmark} title="Bank Account Setup" subtitle="Incorrect or unverified IFSC codes cannot be submitted." />
          <div className="grid gap-4 md:grid-cols-2">{advField('bank_account_no','Account Number',{required:true})}{advField('bank_name','Bank Name',{required:true})}{advField('bank_branch','Branch Name',{required:true})}{advField('bank_ifsc','IFSC Code',{required:true,onBlur:validateIfsc})}</div>
          <div className={`rounded-xl border px-4 py-3 text-sm ${ifscState.state === 'valid' ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : ifscState.state === 'error' ? 'border-rose-200 bg-rose-50 text-rose-700' : 'border-slate-200 bg-slate-50 text-slate-500'}`}>
            {ifscState.state === 'valid' ? <CheckCircle2 className="mr-2 inline h-4 w-4" /> : ifscState.state === 'error' ? <AlertTriangle className="mr-2 inline h-4 w-4" /> : <Landmark className="mr-2 inline h-4 w-4" />}
            {ifscState.message || 'Enter an IFSC code and leave the field to run database validation.'}
          </div>
        </div>}

        {section === 'arms' && <div className="space-y-6">
          <SectionTitle icon={ShieldCheck} title="Arms Details" subtitle="Shown and required only where the employee category requires it." />
          {form.category === 'GUNMAN' ? <div className="grid gap-4 md:grid-cols-2">{advField('gun_license_no','Gun License Number',{required:true})}{advField('arms_issuing_authority','Issuing Authority',{required:true})}{advField('gun_license_expiry','Expiry Date',{type:'date',required:true})}{advField('arms_caliber','Caliber',{required:true})}{advField('weapon_serial_no','Weapon Serial Number',{required:true})}{advField('ammunition_count','Ammunition Count',{type:'number',required:true})}</div> : <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5 text-sm text-slate-600">Arms fields are not applicable to the selected category. Select <strong>GUNMAN</strong> if an arms record is required.</div>}
        </div>}

        {section === 'uniform' && <div className="space-y-6">
          <SectionTitle icon={WalletCards} title="Dress / Uniform EMI Calculator" subtitle="Select issued items to calculate the recovery amount." />
          <div className="grid gap-3 md:grid-cols-2">{uniformItems.map(([key,label,cost]) => <label key={key} className="flex items-center justify-between rounded-xl border border-slate-200 p-4"><span className="flex items-center gap-3"><input type="checkbox" checked={advanced[key]} onChange={(e)=>updateAdvanced(key,e.target.checked)} className="h-4 w-4 rounded border-slate-300" /><span className="text-sm font-semibold text-slate-700">{label}</span></span><span className="text-sm text-slate-500">₹{cost.toLocaleString('en-IN')}</span></label>)}</div>
          <div className="grid gap-4 md:grid-cols-2">{advField('uniform_total_cost','Total Uniform Cost',{type:'number',required:true})}{advField('uniform_monthly_emi','Monthly EMI Recovery',{type:'number',required:true})}</div>
          <div className="rounded-2xl bg-slate-950 p-5 text-white"><div className="text-xs text-slate-400">Selected item estimate</div><div className="mt-1 text-2xl font-semibold">₹{uniformCost.toLocaleString('en-IN')}</div><div className="mt-1 text-xs text-slate-400">Final recovery values are saved only through the payroll/uniform backend workflow.</div></div>
        </div>}

        <div className="mt-8 flex items-center justify-between border-t border-slate-200 pt-5">
          <div className="text-xs text-slate-400">Required fields are marked <span className="text-rose-500">*</span>. IFSC verification is mandatory.</div>
          <div className="flex gap-2"><button type="button" onClick={close} className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-600">Cancel</button><button disabled={saving} className="rounded-xl bg-slate-950 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50">{saving ? 'Saving…' : 'Create Employee Master'}</button></div>
        </div>
      </form>
    </div>
  </div>;
}

function CompliancePanel({ staff }) {
  const today = Date.now();
  const expiring = staff.flatMap((s) => [
    ['Police Verification', s.police_verification_expiry, 45],
    ['Medical & Fitness', s.medical_fitness_expiry, 30],
    ['PSARA Training', s.psara_training_expiry, 30],
    ['Gun License', s.gun_license_expiry, 60],
  ].filter(([,d]) => d).map(([type,d,window]) => ({...s,type,date:d,window,days:Math.ceil((new Date(d)-today)/86400000)}))).filter(x => x.days <= x.window).sort((a,b)=>a.days-b.days);
  return <section className="space-y-4"><div className="grid gap-3 md:grid-cols-3"><Metric icon={ShieldCheck} label="Profiles tracked" value={staff.length}/><Metric icon={AlertTriangle} label="Expiring / expired" value={expiring.length}/><Metric icon={LockKeyhole} label="Bench locked" value={staff.filter(s=>s.is_bench_locked).length}/></div><div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm"><div className="flex items-center justify-between border-b border-slate-200 px-5 py-4"><div><h2 className="font-semibold text-slate-900">Compliance Expiry Summary</h2><p className="text-xs text-slate-500">30 / 45 / 60 day warning windows according to document type.</p></div><button className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold"><Download className="h-3.5 w-3.5"/> Export</button></div><table className="min-w-[760px] w-full text-sm"><thead><tr className="border-b border-slate-100 bg-slate-50 text-xs text-slate-500"><th className="px-5 py-3 text-left">Employee</th><th className="px-5 py-3 text-left">Document</th><th className="px-5 py-3 text-left">Expiry</th><th className="px-5 py-3 text-left">Status</th></tr></thead><tbody>{expiring.map((x,i)=><tr key={i} className="border-b border-slate-100"><td className="px-5 py-3 font-semibold">{x.name}<div className="text-xs font-normal text-slate-400">{x.employee_code}</div></td><td className="px-5 py-3">{x.type}</td><td className="px-5 py-3">{x.date}</td><td className="px-5 py-3"><StatusBadge value={x.days < 0 ? 'EXPIRED' : `${x.days} DAYS`} /></td></tr>)}{!expiring.length&&<tr><td colSpan="4" className="p-10 text-center text-sm text-slate-400">No tracked documents are currently inside a warning window.</td></tr>}</tbody></table></div></section>;
}

function AttendancePanel({ rows }) {
  return <section className="space-y-4"><div className="grid gap-3 md:grid-cols-4"><Metric icon={CalendarDays} label="Employee records" value={rows.length}/><Metric icon={ClipboardCheck} label="Present days" value="—"/><Metric icon={CalendarDays} label="Night shifts" value="—"/><Metric icon={AlertTriangle} label="OT / exceptions" value="—"/></div><div className="grid gap-4 lg:grid-cols-2"><InfoCard icon={ClipboardCheck} title="Attendance Tracker" text="Daily and monthly duty logs, present days, night shifts, overtime and absenteeism will appear here once attendance records are linked to employee profiles."/><InfoCard icon={FileText} title="Master Directory Export" text="Export employee directory by branch, site, designation and active/inactive state to Excel or PDF."/><InfoCard icon={AlertTriangle} title="Late Coming & Shift Violations" text="Punch exceptions will be linked to site check-ins and surfaced for operations review."/><InfoCard icon={Download} title="Compliance Expiry Export" text="Generate a filtered 30 / 60 day compliance report for HR follow-up." /></div></section>;
}

function PayrollPanel({ staff }) {
  return <section className="space-y-4"><div className="grid gap-3 md:grid-cols-4"><Metric icon={Banknote} label="Payroll profiles" value={staff.length}/><Metric icon={FileText} label="Draft" value="—"/><Metric icon={CheckCircle2} label="Approved" value="—"/><Metric icon={WalletCards} label="Disbursed" value="—"/></div><div className="rounded-2xl border border-slate-200 bg-white shadow-sm"><div className="border-b border-slate-200 px-5 py-4"><h2 className="font-semibold text-slate-900">Monthly Payroll Lifecycle</h2><p className="text-xs text-slate-500">Draft → Calculated → Approved → Disbursed</p></div><div className="grid gap-4 p-5 md:grid-cols-2"><InfoCard icon={FileText} title="Salary Slip Generator" text="Monthly PDF payslips should itemize Basic, HRA, allowances, gross pay, PF, ESIC, LWF, dress EMI and net pay."/><InfoCard icon={LockKeyhole} title="Salary Hold Engine" text="Hold payouts for missing police verification, absconding/unannounced exit, pending uniform cost or manual flags, with reason and release audit logs."/><InfoCard icon={ShieldCheck} title="Restricted Salary Access" text="Salary amounts remain role-controlled. Employees can receive their salary slip without exposing payroll administration screens."/><InfoCard icon={ClipboardCheck} title="Audit Trail" text="Payroll actions should retain actor, timestamp, approval state and release criteria." /></div></div></section>;
}

function Metric({ icon: Icon, label, value }) { return <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"><Icon className="h-5 w-5 text-slate-500"/><div className="mt-3 text-2xl font-semibold text-slate-950">{value}</div><div className="mt-1 text-xs font-medium text-slate-500">{label}</div></div>; }
function StatusBadge({ value }) { const danger=['BENCH','EXPIRED'].includes(value) || String(value).includes('DAYS') && Number.parseInt(value) <= 30; return <span className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-bold ${danger?'bg-rose-50 text-rose-700':'bg-emerald-50 text-emerald-700'}`}>{value}</span>; }
function SectionTitle({ icon: Icon, title, subtitle }) { return <div className="flex items-start gap-3"><div className="rounded-xl bg-slate-100 p-2.5 text-slate-600"><Icon className="h-5 w-5"/></div><div><h3 className="font-semibold text-slate-900">{title}</h3><p className="mt-1 text-xs text-slate-500">{subtitle}</p></div></div>; }
function InfoCard({ icon: Icon, title, text }) { return <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><Icon className="h-5 w-5 text-slate-500"/><h3 className="mt-4 font-semibold text-slate-900">{title}</h3><p className="mt-1 text-sm leading-6 text-slate-500">{text}</p></div>; }
function SelectField({ label, value, onChange, options, required=false }) { return <label className="block"><span className="mb-1.5 block text-xs font-semibold text-slate-600">{label}{required&&<span className="text-rose-500"> *</span>}</span><select value={value} required={required} onChange={(e)=>onChange(e.target.value)} className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-slate-400">{options.map((x)=><option key={x} value={x}>{x || 'Select'}</option>)}</select></label>; }
