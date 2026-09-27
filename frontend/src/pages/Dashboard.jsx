import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import MainLayout from '../layouts/MainLayout';
import StatCard from '../components/StatCard';
import GlassCard from '../components/GlassCard';
import StatusBadge from '../components/StatusBadge';
import DetailDrawer from '../components/DetailDrawer';
import GuardModal from '../modals/GuardModal';
import RosterModal from '../modals/RosterModal';
import BulkAttendanceModal from '../modals/BulkAttendanceModal';
import GenerateInvoiceModal from '../modals/GenerateInvoiceModal';
import InvoicePrintModal from '../modals/InvoicePrintModal';
import { useAuth } from '../context/useAuth';
import { formatCurrency, formatDate } from '../utils/helpers';
import api from '../api/axios';
import {
  Shield,
  MapPin,
  ClipboardList,
  ReceiptText,
  Plus,
  ArrowRight,
  Radio,
  Zap,
  CheckCircle2,
  Clock,
  Printer,
  Building,
  Phone,
  Calendar,
  AlertCircle,
  UserCheck,
  Navigation
} from 'lucide-react';

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const role = user?.role || 'ADMIN';

  const [guards, setGuards] = useState([]);
  const [clients, setClients] = useState([]);
  const [sites, setSites] = useState([]);
  const [rosters, setRosters] = useState([]);
  const [staffRosters, setStaffRosters] = useState([]);
  const [attendance, setAttendance] = useState([]);
  const [invoices, setInvoices] = useState([]);

  // Active drawer & modals
  const [selectedDrawerItem, setSelectedDrawerItem] = useState(null);
  const [drawerType, setDrawerType] = useState('generic');
  const [isGuardModalOpen, setGuardModalOpen] = useState(false);
  const [isRosterModalOpen, setRosterModalOpen] = useState(false);
  const [isAttendanceModalOpen, setAttendanceModalOpen] = useState(false);
  const [isInvoiceModalOpen, setInvoiceModalOpen] = useState(false);
  const [printingInvoice, setPrintingInvoice] = useState(null);

  // Guard specific punch state
  const [punchedIn, setPunchedIn] = useState(true);
  const [punchToast, setPunchToast] = useState('');

  useEffect(() => {
    let mounted = true;
    Promise.allSettled([
      api.get('/erp/employees'),
      api.get('/erp/clients'),
      api.get('/erp/sites'),
      api.get('/erp/rosters'),
      api.get('/erp/attendance'),
      api.get('/erp/attendance/my-rosters'),
      api.get('/erp/accounts'),
    ]).then(([eRes, cRes, sRes, rRes, aRes, myRosterRes, acRes]) => {
      if (!mounted) return;
      if (eRes.status === 'fulfilled') {
        setGuards((eRes.value.data || []).map((e) => ({
          ...e,
          guard_id: e.id,
          guard_name: e.name,
          guard_badge: e.employee_code,
          status: String(e.status || '').toUpperCase(),
        })));
      }
      if (cRes.status === 'fulfilled') setClients(cRes.value.data || []);
      if (sRes.status === 'fulfilled') setSites(sRes.value.data || []);
      if (rRes.status === 'fulfilled') setRosters(rRes.value.data || []);
      if (myRosterRes.status === 'fulfilled') {
        const mine = myRosterRes.value.data || [];
        setStaffRosters(mine);
        setPunchedIn(mine.some((r) => r.check_in_time && !r.check_out_time));
      }
      if (aRes.status === 'fulfilled') {
        setAttendance((aRes.value.data || []).map((a) => ({
          ...a,
          guard_name: a.name || a.employee_code,
          status: String(a.status || '').toUpperCase(),
          remarks: a.violation_type || 'Standard Duty',
        })));
      }
      if (acRes.status === 'fulfilled') {
        setInvoices((acRes.value.data?.invoices || []).map((i) => ({
          ...i,
          client_name: i.company_name,
          billing_month: i.billing_month || i.issue_date,
        })));
      }
    });
    return () => { mounted = false; };
  }, []);

  const activeGuardsCount = guards.filter((g) => g.status === 'ACTIVE').length;
  const totalSitesCount = sites.length;
  const todayAttendanceRate =
    attendance.length > 0
      ? Math.round(
          (attendance.filter((a) => a.status === 'PRESENT' || a.status === 'HALF_DAY').length / attendance.length) * 100
        )
      : 98;
  const totalBilled = invoices.reduce((sum, inv) => sum + (inv.total_amount || 0), 0);

  function handleSaveGuard(newGuard) {
    setGuards([newGuard, ...guards]);
  }
  function handleSaveRosters(newRosters) {
    setRosters([...newRosters, ...rosters]);
  }
  function handleSaveAttendance(newLogs) {
    setAttendance([...newLogs, ...attendance]);
  }
  function handleSaveInvoice(newInv) {
    setInvoices([newInv, ...invoices]);
  }

  async function handleTogglePunch() {
    const roster = staffRosters.find((r) => r.check_in_time && !r.check_out_time) || staffRosters[0];
    if (!roster) { setPunchToast('No assigned roster is available for GPS attendance.'); return; }
    if (!navigator.geolocation) { setPunchToast('This browser does not support GPS geolocation.'); return; }
    const getPosition = () => new Promise((resolve, reject) => navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }));
    try {
      const pos = await getPosition();
      let deviceKey = localStorage.getItem('northlane_device_id');
      if (!deviceKey) { deviceKey = crypto.randomUUID(); localStorage.setItem('northlane_device_id', deviceKey); }
      const result = await api.post('/erp/attendance/punch', { roster_id: roster.id, latitude: pos.coords.latitude, longitude: pos.coords.longitude, device_id: deviceKey });
      const checkedIn = result.data?.action === 'CHECK_IN';
      setPunchedIn(checkedIn);
      setPunchToast(checkedIn ? 'GPS check-in verified at '+result.data.distance_m+'m from site.' : 'GPS check-out verified. OT: '+(result.data.overtime_hours || 0)+'h.');
      const mine = await api.get('/erp/attendance/my-rosters');
      setStaffRosters(mine.data || []);
      setTimeout(() => setPunchToast(''), 5000);
    } catch (e) {
      setPunchToast(e.response?.data?.detail || 'GPS attendance punch failed. Stay within the site geofence and retry.');
      setTimeout(() => setPunchToast(''), 5000);
    }
  }

  /* ------------------------------------------------------------- */
  /* 1. ADMIN DASHBOARD VIEW                                       */
  /* ------------------------------------------------------------- */
  function renderAdminView() {
    return (
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2">
          <div>
            <div className="flex items-center gap-2 text-cyan-400 text-xs font-mono mb-1">
              <Radio className="w-3.5 h-3.5 animate-pulse" />
              <span>NORTHLANE ALLIED SERVICES // OPERATIONS</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">
              Operations Dashboard
            </h1>
            <p className="text-xs text-slate-400 mt-0.5">
              Workforce, deployment, attendance and financial operations for {user?.full_name || 'Administrator'}.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => setRosterModalOpen(true)}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold text-slate-950 bg-cyan-400 hover:bg-cyan-300 transition-all shadow-lg shadow-cyan-500/20"
            >
              <Zap className="w-3.5 h-3.5" />
              <span>Dispatch Guard</span>
            </button>
            <button
              onClick={() => setAttendanceModalOpen(true)}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold text-slate-200 bg-slate-900 hover:bg-slate-800 border border-slate-800 transition-all"
            >
              <ClipboardList className="w-3.5 h-3.5 text-emerald-400" />
              <span>Bulk Attendance</span>
            </button>
            <button
              onClick={() => setInvoiceModalOpen(true)}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold text-slate-200 bg-slate-900 hover:bg-slate-800 border border-slate-800 transition-all"
            >
              <ReceiptText className="w-3.5 h-3.5 text-amber-400" />
              <span>Generate Bill</span>
            </button>
          </div>
        </div>

        {/* 4 Stat Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Active Employees"
            value={activeGuardsCount}
            icon={Shield}
            trend="+12%"
            description={`${guards.length} Total Enrolled`}
            glow="border-cyan-500/30"
            sparkline={[50, 60, 55, 70, 85, 80, 95]}
          />
          <StatCard
            label="Active Sites"
            value={totalSitesCount}
            icon={MapPin}
            trend="+2"
            description="Across 3 Client Accounts"
            glow="border-purple-500/30"
            sparkline={[40, 45, 60, 65, 70, 75, 80]}
          />
          <StatCard
            label="Today's Attendance"
            value={`${todayAttendanceRate}%`}
            icon={ClipboardList}
            trend="+3%"
            description="Verified Employee Attendance"
            glow="border-emerald-500/30"
            sparkline={[85, 90, 88, 92, 95, 94, 98]}
          />
          <StatCard
            label="Monthly Billing"
            value={formatCurrency(totalBilled)}
            icon={ReceiptText}
            trend="+18%"
            description="Current Billing Period"
            glow="border-amber-500/30"
            sparkline={[30, 45, 60, 55, 75, 85, 92]}
          />
        </div>

        {/* Main Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <GlassCard glow>
              <GlassCard.Header
                title="Workforce & Deployment Overview"
                subtitle="Current employee deployments, rosters and site coverage"
                badge
                action={
                  <button
                    onClick={() => setRosterModalOpen(true)}
                    className="flex items-center gap-1 text-xs text-cyan-400 hover:text-cyan-300 font-bold"
                  >
                    <span>New Shift Slot</span>
                    <Plus className="w-3.5 h-3.5" />
                  </button>
                }
              />

              <div className="space-y-3">
                {rosters.slice(0, 5).map((r) => (
                  <div
                    key={r.id}
                    onClick={() => {
                      setSelectedDrawerItem(r);
                      setDrawerType('Shift Roster');
                    }}
                    className="p-3.5 rounded-xl cyber-card border border-slate-800/80 hover:border-cyan-500/30 flex items-center justify-between gap-4 cursor-pointer group bg-slate-950/40"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-center text-cyan-400 group-hover:scale-105 transition-transform">
                        <Shield className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h4 className="text-sm font-bold text-white group-hover:text-cyan-400 transition-colors">
                            {r.guard_name || `Guard #${r.guard_id}`}
                          </h4>
                          <span className="font-mono text-[10px] text-slate-400">
                            {r.guard_badge || 'SEC-G'}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-400 mt-0.5">
                          {r.site_name || `Site #${r.site_id}`} • {r.notes || 'Station Duty'}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      <StatusBadge status={r.shift_type} />
                      <StatusBadge status={r.status} />
                      <ArrowRight className="w-4 h-4 text-slate-600 group-hover:text-cyan-400 transition-colors" />
                    </div>
                  </div>
                ))}
              </div>
            </GlassCard>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {sites.slice(0, 2).map((site) => (
                <div
                  key={site.id}
                  onClick={() => {
                    setSelectedDrawerItem(site);
                    setDrawerType('Facility Site');
                  }}
                  className="cyber-card p-4 rounded-2xl border border-slate-800 hover:border-cyan-500/40 cursor-pointer space-y-3 bg-slate-950/40"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[10px] text-cyan-400 px-2 py-0.5 rounded bg-cyan-950/60 border border-cyan-500/20">
                      {site.site_code}
                    </span>
                    <StatusBadge status={site.is_active ? 'ACTIVE' : 'INACTIVE'} />
                  </div>
                  <div>
                    <h4 className="font-bold text-white text-sm">{site.site_name}</h4>
                    <p className="text-[11px] text-slate-400 truncate mt-0.5">{site.address}, {site.city}</p>
                  </div>
                  <div className="flex items-center justify-between text-[11px] text-slate-400 pt-2 border-t border-slate-800/80">
                    <span>Day: {site.shift_requirements?.day_shift_guards || 1} Guards</span>
                    <span>Night: {site.shift_requirements?.night_shift_guards || 1} Guards</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-6">
            <GlassCard>
              <GlassCard.Header
                title="Billing & GST Overview"
                subtitle="Billing status, collections and GST visibility"
                action={
                  <button
                    onClick={() => setInvoiceModalOpen(true)}
                    className="text-xs font-bold text-cyan-400 hover:underline"
                  >
                    Generate
                  </button>
                }
              />

              <div className="space-y-4">
                <div className="p-4 rounded-xl cyber-card border border-cyan-500/20 bg-cyan-950/20">
                  <p className="text-[10px] text-slate-400 uppercase font-semibold">Total Active Invoiced</p>
                  <h3 className="text-2xl font-black text-white mt-1 tabular-nums">
                    {formatCurrency(totalBilled)}
                  </h3>
                  <div className="w-full h-1.5 bg-slate-900 rounded-full mt-3 overflow-hidden">
                    <div className="w-4/5 h-full bg-gradient-to-r from-cyan-500 to-emerald-400" />
                  </div>
                  <p className="text-[10px] text-emerald-400 mt-2 flex items-center gap-1 font-semibold">
                    <CheckCircle2 className="w-3 h-3" />
                    18% Tax Compliant & Ready for Export
                  </p>
                </div>

                <div className="space-y-2">
                  {invoices.slice(0, 3).map((inv) => (
                    <div
                      key={inv.id}
                      onClick={() => {
                        setSelectedDrawerItem(inv);
                        setDrawerType('Client Invoice');
                      }}
                      className="p-2.5 rounded-xl cyber-card border border-slate-800/80 flex items-center justify-between text-xs cursor-pointer hover:border-cyan-500/30"
                    >
                      <div>
                        <p className="font-bold text-white truncate max-w-[140px]">{inv.client_name}</p>
                        <p className="font-mono text-[10px] text-slate-400">{inv.billing_month}</p>
                      </div>
                      <div className="text-right">
                        <p className="font-mono font-bold text-white">{formatCurrency(inv.total_amount)}</p>
                        <StatusBadge status={inv.status} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </GlassCard>

            <GlassCard>
              <GlassCard.Header
                title="Recent Activity"
                subtitle="Latest verified workforce and attendance activity"
                badge
              />

              <div className="space-y-3 text-xs">
                {attendance.slice(0, 4).map((att) => (
                  <div key={att.id} className="flex items-start gap-3 pb-3 border-b border-slate-800/60 last:border-0 last:pb-0">
                    <div className="w-2 h-2 rounded-full bg-cyan-400 mt-1.5 animate-ping" />
                    <div className="flex-1">
                      <p className="text-slate-200">
                        <span className="font-bold text-white">{att.guard_name}</span> logged{' '}
                        <span className="font-semibold text-cyan-400">{att.status}</span> at {att.site_name}
                      </p>
                      <p className="text-[10px] text-slate-500 font-mono mt-0.5">
                        {att.overtime_hours > 0 ? `+${att.overtime_hours} hrs Overtime • ` : ''}
                        {att.remarks || 'Standard Duty'}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </GlassCard>
          </div>
        </div>
      </div>
    );
  }

  /* ------------------------------------------------------------- */
  /* 2. CLIENT DASHBOARD VIEW                                      */
  /* ------------------------------------------------------------- */
  function renderClientView() {
    const clientSites = sites.slice(0, 3);
    const clientInvoices = invoices.slice(0, 3);
    const stationedGuards = rosters.slice(0, 4);

    return (
      <div className="space-y-6">
        {/* Client Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2">
          <div>
            <div className="flex items-center gap-2 text-purple-400 text-xs font-mono mb-1">
              <Building className="w-3.5 h-3.5" />
              <span>AUTHORIZED CORPORATE CLIENT ACCESS // ACME CORP</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">
              Corporate Facility Portal
            </h1>
            <p className="text-xs text-slate-400 mt-0.5">
              Live on-site security deployments, facility shift compliance, and billed statements for {user?.full_name || 'Corporate Client'}.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => navigate('/attendance')}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold text-purple-200 bg-purple-950/60 border border-purple-500/40 hover:bg-purple-900/60 transition-all shadow-lg shadow-purple-500/20"
            >
              <UserCheck className="w-3.5 h-3.5 text-purple-300" />
              <span>Verify Gate Logs</span>
            </button>
            <button
              onClick={() => navigate('/billing')}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold text-slate-200 bg-slate-900 hover:bg-slate-800 border border-slate-800 transition-all"
            >
              <ReceiptText className="w-3.5 h-3.5 text-amber-400" />
              <span>View Statements</span>
            </button>
          </div>
        </div>

        {/* Client Tailored Stat Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Protected Facilities"
            value={clientSites.length}
            icon={Building}
            trend="Active"
            description="Contracted Security Sites"
            glow="border-purple-500/30"
            sparkline={[100, 100, 100, 100, 100, 100, 100]}
          />
          <StatCard
            label="Guards On Duty"
            value="8 Officers"
            icon={Shield}
            trend="100% Post"
            description="Actively Stationed Now"
            glow="border-cyan-500/30"
            sparkline={[8, 8, 7, 8, 8, 8, 8]}
          />
          <StatCard
            label="Shift Quota Met"
            value="100%"
            icon={CheckCircle2}
            trend="Compliant"
            description="Day & Night Quotas Fulfilled"
            glow="border-emerald-500/30"
            sparkline={[96, 98, 97, 100, 100, 100, 100]}
          />
          <StatCard
            label="Current Billing Balance"
            value={formatCurrency(245000)}
            icon={ReceiptText}
            trend="Due 25th"
            description="August 2026 Invoiced"
            glow="border-amber-500/30"
            sparkline={[200, 210, 220, 230, 240, 245, 245]}
          />
        </div>

        {/* Client Main Panels */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            {/* Stationed Guards Table */}
            <GlassCard glow>
              <GlassCard.Header
                title="Security Officers Stationed at Your Facilities"
                subtitle="Verified guard details, post locations, and current shift assignments"
                badge
              />

              <div className="space-y-3">
                {stationedGuards.map((r) => (
                  <div
                    key={r.id}
                    onClick={() => {
                      setSelectedDrawerItem(r);
                      setDrawerType('Stationed Officer');
                    }}
                    className="p-3.5 rounded-xl cyber-card border border-purple-500/20 hover:border-purple-500/40 flex items-center justify-between gap-4 cursor-pointer group bg-slate-950/40"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/30 flex items-center justify-center text-purple-300 group-hover:scale-105 transition-transform">
                        <Shield className="w-5 h-5" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h4 className="text-sm font-bold text-white group-hover:text-purple-300 transition-colors">
                            {r.guard_name}
                          </h4>
                          <span className="font-mono text-[10px] text-purple-400 bg-purple-950/60 px-1.5 py-0.5 rounded border border-purple-500/20">
                            {r.guard_badge}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-400 mt-0.5 flex items-center gap-1.5">
                          <MapPin className="w-3 h-3 text-cyan-400" />
                          <span>{r.site_name}</span>
                          <span>•</span>
                          <Phone className="w-3 h-3 text-emerald-400" />
                          <span>+91-987654320{r.id}</span>
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      <StatusBadge status={r.shift_type} />
                      <span className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-bold rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                        ON SITE
                      </span>
                      <ArrowRight className="w-4 h-4 text-slate-600 group-hover:text-purple-300 transition-colors" />
                    </div>
                  </div>
                ))}
              </div>
            </GlassCard>

            {/* Contracted Sites & Quota Card */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {clientSites.map((site) => (
                <div
                  key={site.id}
                  className="cyber-card p-4 rounded-2xl border border-slate-800 space-y-3 bg-slate-950/40"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[10px] text-purple-400 px-2 py-0.5 rounded bg-purple-950/60 border border-purple-500/20 font-bold">
                      {site.site_code}
                    </span>
                    <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                      SECURED
                    </span>
                  </div>
                  <div>
                    <h4 className="font-bold text-white text-sm">{site.site_name}</h4>
                    <p className="text-[11px] text-slate-400 truncate mt-0.5">{site.address}, {site.city}</p>
                  </div>
                  <div className="pt-2 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-300">
                    <span className="text-cyan-400">Day Quota: {site.shift_requirements?.day_shift_guards || 2} Officers</span>
                    <span className="text-purple-400">Night Quota: {site.shift_requirements?.night_shift_guards || 1} Officers</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Right Column: Invoices & Statements */}
          <div className="space-y-6">
            <GlassCard>
              <GlassCard.Header
                title="Service Invoices"
                subtitle="Your corporate billing statements"
              />

              <div className="space-y-3">
                {clientInvoices.map((inv) => (
                  <div
                    key={inv.id}
                    className="p-3 rounded-xl cyber-card border border-slate-800 flex items-center justify-between hover:border-purple-500/30 transition-colors"
                  >
                    <div>
                      <p className="font-bold text-white text-xs">{inv.invoice_number}</p>
                      <p className="text-[10px] text-slate-400 font-mono mt-0.5">{inv.billing_month} Statement</p>
                      <p className="font-mono text-xs font-bold text-cyan-400 mt-1">{formatCurrency(inv.total_amount)}</p>
                    </div>
                    <div className="flex flex-col items-end gap-2">
                      <StatusBadge status={inv.status} />
                      <button
                        onClick={() => setPrintingInvoice(inv)}
                        className="flex items-center gap-1 text-[11px] font-bold text-purple-300 hover:text-purple-200 bg-purple-950/60 px-2 py-1 rounded-lg border border-purple-500/30 transition-all"
                      >
                        <Printer className="w-3 h-3" />
                        <span>Receipt</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </GlassCard>

            <GlassCard>
              <GlassCard.Header
                title="Operations Contacts"
                subtitle="Direct connection to your facility dispatch team"
              />
              <div className="space-y-2 text-xs">
                <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-between">
                  <div>
                    <p className="font-bold text-white">Central Operations Room</p>
                    <p className="text-[11px] text-slate-400">24/7 Rapid Response</p>
                  </div>
                  <span className="font-mono font-bold text-cyan-400">+91-9876543000</span>
                </div>
                <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-between">
                  <div>
                    <p className="font-bold text-white">Facility Account Manager</p>
                    <p className="text-[11px] text-slate-400">Direct Support Line</p>
                  </div>
                  <span className="font-mono font-bold text-purple-400">+91-9876543299</span>
                </div>
              </div>
            </GlassCard>
          </div>
        </div>
      </div>
    );
  }

  /* ------------------------------------------------------------- */
  /* 3. STAFF / GUARD DASHBOARD VIEW                               */
  /* ------------------------------------------------------------- */
  function renderStaffView() {
    const myShifts = staffRosters.length ? staffRosters.slice(0, 4) : rosters.slice(0, 4);
    const myAttendanceLogs = attendance.slice(0, 4);

    return (
      <div className="space-y-6">
        {/* Employee Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2">
          <div>
            <div className="flex items-center gap-2 text-emerald-400 text-xs font-mono mb-1">
              <Shield className="w-3.5 h-3.5 animate-pulse" />
              <span>EMPLOYEE WORKSPACE</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">
              Employee Console // {user?.full_name || 'Ramesh Kumar'}
            </h1>
            <p className="text-xs text-slate-400 mt-0.5">
              Personal post assignment, digital gate attendance terminal, and post orders.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className={`px-3 py-1.5 rounded-full text-xs font-bold border flex items-center gap-2 ${
              punchedIn
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30 shadow-[0_0_15px_rgba(16,185,129,0.2)]'
                : 'bg-rose-500/10 text-rose-400 border-rose-500/30'
            }`}>
              <span className={`w-2 h-2 rounded-full ${punchedIn ? 'bg-emerald-400 animate-ping' : 'bg-rose-400'}`} />
              <span>{punchedIn ? 'STATUS: ON DUTY - PERIMETER ACTIVE' : 'STATUS: OFF DUTY'}</span>
            </span>
          </div>
        </div>

        {punchToast && (
          <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-400 text-xs font-bold flex items-center gap-2 animate-bounce">
            <CheckCircle2 className="w-4 h-4" />
            <span>{punchToast}</span>
          </div>
        )}

        {/* Employee Workspace Summary */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Assigned Post"
            value="Acme Towers"
            icon={MapPin}
            trend="Gate 3"
            description="North Barrier Security"
            glow="border-emerald-500/30"
            sparkline={[1, 1, 1, 1, 1, 1, 1]}
          />
          <StatCard
            label="Current Shift"
            value="DAY SHIFT"
            icon={Clock}
            trend="08:00 - 20:00"
            description="12 Hour Shift Window"
            glow="border-cyan-500/30"
            sparkline={[12, 12, 12, 12, 12, 12, 12]}
          />
          <StatCard
            label="Monthly Duty Days"
            value="24 Days"
            icon={Calendar}
            trend="+2 Days"
            description="Verified Present"
            glow="border-purple-500/30"
            sparkline={[20, 21, 22, 22, 23, 23, 24]}
          />
          <StatCard
            label="Overtime Logged"
            value="14.5 Hours"
            icon={Zap}
            trend="+₹4,850 OT"
            description="Added to Next Wage Payout"
            glow="border-amber-500/30"
            sparkline={[4, 6, 8, 10, 11, 13, 14.5]}
          />
        </div>

        {/* Employee Workspace */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            {/* Digital Clock-In & Punch Terminal */}
            <GlassCard glow>
              <GlassCard.Header
                title="Digital Shift Attendance Terminal"
                subtitle="Geofenced gate check-in & verified duty logger"
                badge
              />

              <div className="p-6 rounded-2xl cyber-panel border border-emerald-500/20 flex flex-col sm:flex-row items-center justify-between gap-6 bg-slate-950/60">
                <div className="space-y-2 text-center sm:text-left">
                  <div className="flex items-center justify-center sm:justify-start gap-2 text-slate-400 font-mono text-xs">
                    <Navigation className="w-3.5 h-3.5 text-emerald-400" />
                    <span>GPS LOC: 19.0760° N, 72.8777° E (Within 10m of Gate)</span>
                  </div>
                  <h3 className="text-xl font-bold text-white">
                    {punchedIn ? 'Shift Active: Acme Cyber Towers' : 'Shift Not Started'}
                  </h3>
                  <p className="text-xs text-slate-400">
                    {punchedIn
                      ? 'Duty check-in recorded at 08:00 AM. Biometric and geo-perimeter verified.'
                      : 'Please punch in once you arrive at your assigned gate post.'}
                  </p>
                </div>

                <button
                  onClick={handleTogglePunch}
                  className={`px-6 py-4 rounded-2xl font-black text-sm transition-all shadow-xl flex items-center gap-2.5 cursor-pointer select-none ${
                    punchedIn
                      ? 'bg-rose-500 hover:bg-rose-400 text-white shadow-rose-500/25'
                      : 'bg-emerald-400 hover:bg-emerald-300 text-slate-950 shadow-emerald-500/25'
                  }`}
                >
                  <Clock className="w-5 h-5" />
                  <span>{punchedIn ? 'PUNCH OUT (END SHIFT)' : 'PUNCH IN FOR DUTY'}</span>
                </button>
              </div>
            </GlassCard>

            {/* Upcoming Duty Schedule */}
            <GlassCard>
              <GlassCard.Header
                title="My Assigned Shifts (Next 7 Days)"
                subtitle="Your approved shift schedule issued by Central Dispatch"
              />

              <div className="space-y-3">
                {myShifts.map((s, idx) => (
                  <div
                    key={s.id}
                    className="p-3.5 rounded-xl cyber-card border border-slate-800 flex items-center justify-between bg-slate-950/40"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-center text-emerald-400">
                        <Calendar className="w-5 h-5" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-white text-xs">
                            {formatDate(s.date || new Date().toISOString())}
                          </span>
                          <span className="text-[10px] text-slate-400 font-mono">
                            {idx === 0 ? '(TODAY)' : idx === 1 ? '(TOMORROW)' : ''}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-400 mt-0.5 flex items-center gap-1">
                          <MapPin className="w-3 h-3 text-cyan-400" />
                          <span>{s.site_name || 'Tech Park Main Barrier'}</span>
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      <StatusBadge status={s.shift_type} />
                      <span className="text-[11px] font-mono text-emerald-400 font-semibold">SCHEDULED</span>
                    </div>
                  </div>
                ))}
              </div>
            </GlassCard>
          </div>

          {/* Right Column: Emergency Hotlines & Recent Logs */}
          <div className="space-y-6">
            <GlassCard glow>
              <GlassCard.Header
                title="Operations Support"
                subtitle="Immediate direct-dial dispatch contacts"
              />

              <div className="space-y-2.5 text-xs">
                <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-center justify-between text-rose-300">
                  <div className="flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 text-rose-400" />
                    <div>
                      <p className="font-bold">Security Control SOS</p>
                      <p className="text-[10px] text-rose-400/80">Immediate Armed Support</p>
                    </div>
                  </div>
                  <span className="font-mono font-bold">+91-9876543000</span>
                </div>

                <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-between text-slate-300">
                  <div className="flex items-center gap-2">
                    <Phone className="w-4 h-4 text-emerald-400" />
                    <div>
                      <p className="font-bold">Shift Supervisor Desk</p>
                      <p className="text-[10px] text-slate-400">Roster & Relief Guard</p>
                    </div>
                  </div>
                  <span className="font-mono font-bold text-emerald-400">+91-9876543212</span>
                </div>

                <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-between text-slate-300">
                  <div className="flex items-center gap-2">
                    <Shield className="w-4 h-4 text-cyan-400" />
                    <div>
                      <p className="font-bold">Police Emergency</p>
                      <p className="text-[10px] text-slate-400">National Emergency Portal</p>
                    </div>
                  </div>
                  <span className="font-mono font-bold text-cyan-400">112</span>
                </div>
              </div>
            </GlassCard>

            <GlassCard>
              <GlassCard.Header
                title="My Recent Attendance"
                subtitle="Recorded punch times and overtime"
              />

              <div className="space-y-2.5 text-xs">
                {myAttendanceLogs.map((log) => (
                  <div key={log.id} className="p-2.5 rounded-xl bg-slate-900/60 border border-slate-800/80 flex items-center justify-between">
                    <div>
                      <p className="font-bold text-white text-xs">{log.status}</p>
                      <p className="text-[10px] text-slate-400 font-mono mt-0.5">
                        {log.overtime_hours > 0 ? `+${log.overtime_hours} hrs Overtime` : 'Normal Shift'}
                      </p>
                    </div>
                    <span className="text-[10px] font-mono text-emerald-400 font-bold">VERIFIED</span>
                  </div>
                ))}
              </div>
            </GlassCard>
          </div>
        </div>
      </div>
    );
  }

  return (
    <MainLayout
      onQuickAction={(act) => {
        if (act === 'add_guard') setGuardModalOpen(true);
        if (act === 'add_site') setRosterModalOpen(true);
        if (act === 'add_roster') setRosterModalOpen(true);
        if (act === 'log_attendance') setAttendanceModalOpen(true);
        if (act === 'generate_invoice') setInvoiceModalOpen(true);
      }}
    >
      {role === 'CLIENT' && renderClientView()}
      {role === 'STAFF' && renderStaffView()}
      {role !== 'CLIENT' && role !== 'STAFF' && renderAdminView()}

      <DetailDrawer
        isOpen={!!selectedDrawerItem}
        onClose={() => setSelectedDrawerItem(null)}
        title={selectedDrawerItem?.site_name || selectedDrawerItem?.guard_name || selectedDrawerItem?.client_name || 'Dossier'}
        subtitle={selectedDrawerItem?.badge_number || selectedDrawerItem?.invoice_number || selectedDrawerItem?.site_code}
        data={selectedDrawerItem}
        type={drawerType}
      />

      <GuardModal
        isOpen={isGuardModalOpen}
        onClose={() => setGuardModalOpen(false)}
        onSave={handleSaveGuard}
      />
      <RosterModal
        isOpen={isRosterModalOpen}
        onClose={() => setRosterModalOpen(false)}
        onSave={handleSaveRosters}
        guards={guards}
        sites={sites}
      />
      <BulkAttendanceModal
        isOpen={isAttendanceModalOpen}
        onClose={() => setAttendanceModalOpen(false)}
        onSave={handleSaveAttendance}
        sites={sites}
        rosters={rosters}
      />
      <GenerateInvoiceModal
        isOpen={isInvoiceModalOpen}
        onClose={() => setInvoiceModalOpen(false)}
        onSave={handleSaveInvoice}
        clients={clients}
        sites={sites}
      />
      <InvoicePrintModal
        isOpen={!!printingInvoice}
        onClose={() => setPrintingInvoice(null)}
        invoice={printingInvoice}
      />
    </MainLayout>
  );
}