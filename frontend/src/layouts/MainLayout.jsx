import { useState, useEffect } from 'react';
import { useAuth } from '../context/useAuth';
import { useNavigate, useLocation } from 'react-router-dom';
import CommandPalette from '../components/CommandPalette';
import {
  LayoutDashboard,
  Users,
  MapPin,
  ClipboardList,
  ReceiptText,
  Shield,
  Calendar,
  Search,
  LogOut,
  Zap,
  ChevronDown,
  Menu,
  X,
  Radio,
  WalletCards,
  Landmark,
  FileCheck2,
  AlertTriangle,
  Bell,
  ChevronRight
} from 'lucide-react';

export default function MainLayout({ children, onQuickAction = null }) {
  const { user, logout, apiConnected, can } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [paletteOpen, setPaletteOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [personaMenuOpen, setPersonaMenuOpen] = useState(false);
  const [currentTime, setCurrentTime] = useState('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setCurrentTime(
        now.toLocaleTimeString('en-US', {
          hour12: false,
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        })
      );
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  const role = user?.role || 'STAFF';

  const fullNavItems = [
    { icon: LayoutDashboard, label: 'Command Center', path: '/erp', permission: 'dashboard.view' },
    { icon: Landmark, label: 'Owner Executive', path: '/owner-executive', permission: 'owner.view' },
    { icon: Shield, label: 'Employees & HR', path: '/employees', permission: 'employees.view' },
    { icon: Users, label: 'Clients', path: '/clients', permission: 'clients.view' },
    { icon: MapPin, label: 'Sites & Deployment', path: '/sites', permission: 'sites.view' },
    { icon: Calendar, label: 'Rosters', path: '/rosters', permission: 'rosters.view' },
    { icon: ClipboardList, label: 'Attendance & OT', path: '/attendance', permission: 'attendance.view' },
    { icon: ReceiptText, label: 'Invoices & Billing', path: '/billing', permission: 'billing.view' },
    { icon: WalletCards, label: 'Payroll', path: '/payroll', permission: 'payroll.view' },
    { icon: Landmark, label: 'Accounts & GST', path: '/accounts', permission: 'finance.view' },
    { icon: FileCheck2, label: 'Compliance', path: '/compliance', permission: 'compliance.view' },
    { icon: AlertTriangle, label: 'Risk Controls', path: '/risks', permission: 'risks.view' },
    { icon: Users, label: 'User Management', path: '/users', permission: 'user_management.view' },
    { icon: Shield, label: 'My Account', path: '/account', permission: null },
  ];

  const navItems = fullNavItems.filter((item) => !item.permission || can(item.permission));

  return (
    <div className="min-h-screen bg-[#f5f7fb] text-slate-700 flex flex-col">
      <CommandPalette
        isOpen={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onAction={(action) => {
          if (action === 'toggle_palette') setPaletteOpen((prev) => !prev);
          else if (onQuickAction) onQuickAction(action);
        }}
      />

      <header className="h-16 shrink-0 bg-white border-b border-slate-200 flex items-center sticky top-0 z-30 shadow-sm">
        <div className="w-full px-4 lg:px-6 flex items-center gap-4">
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="md:hidden p-2 rounded-lg text-slate-500 hover:bg-slate-100"
            aria-label="Open menu"
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>

          <button
            onClick={() => navigate('/erp')}
            className="flex items-center gap-3 shrink-0 text-left"
          >
            <div className="w-9 h-9 rounded-lg bg-teal-50 border border-teal-100 flex items-center justify-center text-teal-700">
              <Shield className="w-5 h-5" />
            </div>
            <div className="hidden sm:block leading-tight">
              <div className="flex items-baseline gap-2">
                <span className="text-[15px] font-extrabold tracking-tight text-slate-900">FORTELLUS</span>
                <span className="text-[15px] font-extrabold tracking-tight text-teal-700">ENTERPRISE ERP</span>
              </div>
              <p className="text-[9px] font-semibold tracking-[0.16em] text-slate-400 uppercase mt-0.5">Security & Facility Management ERP</p>
            </div>
          </button>

          <div className="flex-1 max-w-xl mx-auto hidden md:block">
            <button
              onClick={() => setPaletteOpen(true)}
              className="w-full h-10 flex items-center justify-between px-3.5 rounded-lg bg-slate-50 border border-slate-200 hover:border-teal-300 hover:bg-white text-slate-500 text-sm transition-colors"
            >
              <span className="flex items-center gap-2">
                <Search className="w-4 h-4 text-slate-400" />
                Search employees, clients, sites, invoices...
              </span>
              <span className="text-[11px] font-medium px-2 py-1 rounded-md bg-white border border-slate-200 text-slate-400">Ctrl K</span>
            </button>
          </div>

          <div className="flex items-center gap-2 lg:gap-3 ml-auto">
            <div className="hidden xl:flex items-center gap-2 text-xs text-slate-500 px-2">
              <Radio className={`w-3.5 h-3.5 ${apiConnected ? 'text-emerald-500' : 'text-slate-400'}`} />
              <span>{currentTime || '00:00:00'} IST</span>
            </div>

            <div
              className={`hidden sm:flex items-center gap-1.5 px-2.5 py-1.5 rounded-full text-[11px] font-semibold border ${apiConnected
                ? 'bg-emerald-50 text-emerald-700 border-emerald-100'
                : 'bg-amber-50 text-amber-700 border-amber-100'}`}
              title={apiConnected ? 'Connected to live FastAPI backend' : 'Running in offline demo mode'}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${apiConnected ? 'bg-emerald-500' : 'bg-amber-500'}`} />
              {apiConnected ? 'LIVE' : 'OFFLINE'}
            </div>

            <button className="hidden sm:flex w-9 h-9 items-center justify-center rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-50">
              <Bell className="w-4 h-4" />
            </button>

            <div className="relative">
              <button
                onClick={() => setPersonaMenuOpen(!personaMenuOpen)}
                className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-slate-50 transition-colors"
              >
                <div className="w-8 h-8 rounded-lg bg-teal-50 border border-teal-100 flex items-center justify-center text-teal-700 font-bold text-xs">
                  {user?.full_name?.charAt(0) || 'A'}
                </div>
                <div className="hidden lg:block text-left">
                  <p className="text-xs font-semibold text-slate-800 leading-tight">{user?.full_name?.split(' ')[0] || 'Admin'}</p>
                  <p className="text-[10px] text-slate-400 uppercase tracking-wider">{role}</p>
                </div>
                <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
              </button>

              {personaMenuOpen && (
                <div className="absolute right-0 top-full mt-2 w-64 bg-white rounded-xl border border-slate-200 p-2 shadow-xl z-40">
                  <div className="px-3 py-2.5 rounded-lg bg-slate-50 border border-slate-100 mb-1">
                    <p className="text-xs font-semibold text-slate-800">{user?.full_name || 'Account'}</p>
                    <p className="text-[10px] text-slate-400 uppercase tracking-wider mt-0.5">{role}</p>
                  </div>
                  <div className="h-px bg-slate-100 my-2" />
                  <button
                    onClick={() => { logout(); navigate('/login'); }}
                    className="w-full text-left px-3 py-2 text-xs text-rose-600 hover:bg-rose-50 rounded-lg flex items-center gap-2"
                  >
                    <LogOut className="w-3.5 h-3.5" />
                    Sign Out
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      <div className="flex flex-1 min-h-0">
        <aside className="hidden md:flex w-64 shrink-0 bg-white border-r border-slate-200 flex-col">
          <div className="px-4 pt-5 pb-3">
            <p className="text-[10px] text-slate-400 uppercase tracking-[0.16em] font-bold px-2">Workspace</p>
          </div>

          <nav className="flex-1 px-3 space-y-1 overflow-y-auto">
            {navItems.filter((item) => !item.ownerOnly || role === 'OWNER').map((item) => {
              const isActive = location.pathname === item.path;
              const Icon = item.icon;
              return (
                <button
                  key={item.path}
                  onClick={() => navigate(item.path)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${isActive
                    ? 'bg-teal-50 text-teal-700 border border-teal-100'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'}`}
                >
                  <Icon className={`w-[18px] h-[18px] shrink-0 ${isActive ? 'text-teal-700' : 'text-slate-400'}`} />
                  <span className="truncate">{item.label}</span>
                  {isActive && <ChevronRight className="w-3.5 h-3.5 ml-auto shrink-0" />}
                </button>
              );
            })}
          </nav>

          <div className="p-3 border-t border-slate-200">
            <div className="rounded-xl bg-slate-50 border border-slate-200 p-3">
              <div className="flex items-center justify-between text-xs font-semibold text-slate-700">
                <span className="flex items-center gap-2"><Zap className="w-3.5 h-3.5 text-teal-600" />System Health</span>
                <span className="text-emerald-600">99.9%</span>
              </div>
              <div className="w-full h-1.5 bg-slate-200 rounded-full mt-2 overflow-hidden">
                <div className="w-[99.9%] h-full bg-teal-600 rounded-full" />
              </div>
            </div>
            <p className="text-[10px] text-slate-400 px-1 mt-2">Fortellus Security & Facility Management ERP</p>
          </div>
        </aside>

        {mobileMenuOpen && (
          <div className="md:hidden fixed inset-x-0 top-16 bottom-0 bg-white z-40 p-4 overflow-y-auto">
            <nav className="space-y-1">
              {navItems.map((item) => (
                <button
                  key={item.path}
                  onClick={() => { navigate(item.path); setMobileMenuOpen(false); }}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium ${location.pathname === item.path ? 'bg-teal-50 text-teal-700' : 'text-slate-600 hover:bg-slate-50'}`}
                >
                  <item.icon className="w-5 h-5" />
                  <span>{item.label}</span>
                </button>
              ))}
            </nav>
          </div>
        )}

        <main className="flex-1 min-w-0 overflow-y-auto bg-[#f5f7fb]">
          <div className="max-w-[1440px] mx-auto p-4 sm:p-6 lg:p-8">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
