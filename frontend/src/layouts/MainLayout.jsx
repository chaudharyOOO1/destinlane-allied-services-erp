import { useState } from 'react';
import { useAuth } from '../context/useAuth';
import { useNavigate, useLocation } from 'react-router-dom';
import CommandPalette from '../components/CommandPalette';
import {
  LayoutDashboard, Users, MapPin, ClipboardList, ReceiptText, Shield,
  Calendar, Search, LogOut, ChevronDown, Menu, X, Radio, WalletCards,
  Landmark, FileCheck2, AlertTriangle, Bell, ChevronRight, UserRound,
  BriefcaseBusiness, UserCog, Building2, CircleDollarSign, PanelLeft
} from 'lucide-react';

const NAV_GROUPS = [
  { label: 'Overview', items: [
    { icon: LayoutDashboard, label: 'Dashboard', path: '/erp', permission: 'dashboard.view' },
    { icon: Landmark, label: 'Owner Executive', path: '/owner-executive', permission: 'owner.view' },
  ]},
  { label: 'Workforce', items: [
    { icon: Users, label: 'Employees', path: '/employees', permission: 'employees.view' },
    { icon: Calendar, label: 'Rosters', path: '/rosters', permission: 'rosters.view' },
    { icon: ClipboardList, label: 'Attendance', path: '/attendance', permission: 'attendance.view' },
  ]},
  { label: 'Clients & Sites', items: [
    { icon: BriefcaseBusiness, label: 'Clients', path: '/clients', permission: 'clients.view' },
    { icon: MapPin, label: 'Sites & Deployment', path: '/sites', permission: 'sites.view' },
  ]},
  { label: 'Finance', items: [
    { icon: ReceiptText, label: 'Billing & Invoices', path: '/billing', permission: 'billing.view' },
    { icon: WalletCards, label: 'Payroll', path: '/payroll', permission: 'payroll.view' },
    { icon: CircleDollarSign, label: 'Accounts & GST', path: '/accounts', permission: 'finance.view' },
  ]},
  { label: 'Control', items: [
    { icon: FileCheck2, label: 'Compliance', path: '/compliance', permission: 'compliance.view' },
    { icon: AlertTriangle, label: 'Risk Controls', path: '/risks', permission: 'risks.view' },
    { icon: UserCog, label: 'User Management', path: '/users', permission: 'user_management.view' },
  ]},
];

export default function MainLayout({ children, onQuickAction = null }) {
  const { user, logout, apiConnected, can } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [personaMenuOpen, setPersonaMenuOpen] = useState(false);

  const role = user?.role || 'STAFF';
  const visibleGroups = NAV_GROUPS
    .map(group => ({ ...group, items: group.items.filter(item => !item.permission || can(item.permission)) }))
    .filter(group => group.items.length > 0);

  const go = (path) => { navigate(path); setMobileMenuOpen(false); };

  return (
    <div className="min-h-screen bg-[#f8fafc] text-slate-900 flex flex-col">
      <CommandPalette
        isOpen={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onAction={(action) => {
          if (action === 'toggle_palette') setPaletteOpen(v => !v);
          else if (onQuickAction) onQuickAction(action);
        }}
      />

      <header className="h-16 shrink-0 bg-white/95 backdrop-blur border-b border-slate-200 sticky top-0 z-50">
        <div className="h-full px-4 lg:px-6 flex items-center gap-4">
          <button className="md:hidden p-2 rounded-lg hover:bg-slate-100" onClick={() => setMobileMenuOpen(v => !v)} aria-label="Open navigation">
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>

          <button onClick={() => go('/erp')} className="flex items-center gap-3 shrink-0 text-left group">
            <div className="w-9 h-9 rounded-lg bg-slate-950 text-white flex items-center justify-center shadow-sm group-hover:bg-slate-800 transition-colors">
              <Shield className="w-[18px] h-[18px]" />
            </div>
            <div className="hidden sm:block leading-tight">
              <div className="text-[15px] font-semibold tracking-[-0.02em] text-slate-950">NORTHLANE</div>
              <div className="text-[9px] font-medium tracking-[0.16em] text-slate-400 uppercase">Allied Services ERP</div>
            </div>
          </button>

          <div className="hidden md:flex flex-1 max-w-2xl mx-auto">
            <button onClick={() => setPaletteOpen(true)} className="w-full max-w-xl mx-auto h-9 px-3 rounded-lg border border-slate-200 bg-slate-50/80 hover:bg-white hover:border-slate-300 flex items-center gap-2 text-xs text-slate-400 transition-colors">
              <Search className="w-4 h-4" />
              <span className="flex-1 text-left">Search anything...</span>
              <kbd className="hidden lg:inline-flex px-1.5 py-0.5 rounded border border-slate-200 bg-white text-[10px] text-slate-400">Ctrl K</kbd>
            </button>
          </div>

          <div className="ml-auto flex items-center gap-1.5">
            <div className={`hidden lg:flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[10px] font-semibold border ${apiConnected ? 'bg-emerald-50 text-emerald-700 border-emerald-100' : 'bg-amber-50 text-amber-700 border-amber-100'}`}>
              <Radio className="w-3 h-3" />
              {apiConnected ? 'LIVE' : 'OFFLINE'}
            </div>
            <button className="w-9 h-9 rounded-lg hover:bg-slate-100 flex items-center justify-center text-slate-500" aria-label="Notifications">
              <Bell className="w-4 h-4" />
            </button>
            <div className="relative">
              <button onClick={() => setPersonaMenuOpen(v => !v)} className="flex items-center gap-2 px-1.5 py-1 rounded-lg hover:bg-slate-100">
                <div className="w-8 h-8 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-700 text-xs font-semibold">
                  {user?.full_name?.charAt(0) || 'A'}
                </div>
                <div className="hidden sm:block text-left leading-tight">
                  <p className="text-xs font-semibold text-slate-800">{user?.full_name?.split(' ')[0] || 'Admin'}</p>
                  <p className="text-[10px] text-slate-400 uppercase tracking-wider">{role}</p>
                </div>
                <ChevronDown className="hidden sm:block w-3.5 h-3.5 text-slate-400" />
              </button>
              {personaMenuOpen && (
                <div className="absolute right-0 top-full mt-2 w-60 bg-white border border-slate-200 rounded-xl shadow-xl p-2">
                  <div className="px-3 py-2.5 rounded-lg bg-slate-50 border border-slate-100">
                    <p className="text-xs font-semibold text-slate-800">{user?.full_name || 'Account'}</p>
                    <p className="text-[10px] text-slate-400 uppercase tracking-wider mt-0.5">{role}</p>
                  </div>
                  <button onClick={() => { logout(); navigate('/login'); }} className="mt-2 w-full px-3 py-2 rounded-lg text-left text-xs font-medium text-rose-600 hover:bg-rose-50 flex items-center gap-2">
                    <LogOut className="w-3.5 h-3.5" /> Sign out
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      <div className="flex flex-1 min-h-0">
        <aside className="hidden md:flex w-[232px] shrink-0 bg-white border-r border-slate-200 flex-col">
          <div className="px-4 py-5 border-b border-slate-100">
            <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.16em] font-semibold text-slate-400">
              <PanelLeft className="w-3.5 h-3.5" /> Workspace
            </div>
          </div>
          <nav className="flex-1 px-3 py-3 overflow-y-auto">
            {visibleGroups.map(group => (
              <div key={group.label} className="mb-5">
                <p className="px-2 mb-1.5 text-[10px] uppercase tracking-[0.14em] font-semibold text-slate-400">{group.label}</p>
                <div className="space-y-0.5">
                  {group.items.map(item => {
                    const Icon = item.icon;
                    const active = location.pathname === item.path || (item.path === '/erp' && location.pathname === '/dashboard');
                    return (
                      <button key={item.path} onClick={() => go(item.path)} className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded-md text-[13px] font-medium transition-colors ${active ? 'bg-slate-100 text-slate-950' : 'text-slate-600 hover:bg-slate-50 hover:text-slate-950'}`}>
                        <Icon className={`w-4 h-4 shrink-0 ${active ? 'text-slate-950' : 'text-slate-400'}`} />
                        <span className="truncate">{item.label}</span>
                        {active && <ChevronRight className="w-3 h-3 ml-auto text-slate-400" />}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </nav>
          <div className="p-3 border-t border-slate-200">
            <button onClick={() => go('/account')} className="w-full p-2.5 rounded-lg border border-slate-200 bg-slate-50 hover:bg-white text-left">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-full bg-white border border-slate-200 flex items-center justify-center"><UserRound className="w-3.5 h-3.5 text-slate-500" /></div>
                <div className="min-w-0">
                  <p className="text-[11px] font-semibold text-slate-800 truncate">{user?.full_name || 'Account'}</p>
                  <p className="text-[10px] text-slate-400 truncate">Manage your account</p>
                </div>
              </div>
            </button>
            <p className="text-[9px] text-slate-400 px-1 mt-2">Northlane Allied Services · ERP</p>
          </div>
        </aside>

        {mobileMenuOpen && (
          <div className="md:hidden fixed inset-x-0 top-16 bottom-0 bg-white z-40 overflow-y-auto p-4">
            <div className="pb-3 mb-3 border-b border-slate-200">
              <p className="text-xs font-semibold text-slate-900">Northlane Allied Services</p>
              <p className="text-[10px] text-slate-400 mt-0.5 uppercase tracking-wider">{role} workspace</p>
            </div>
            {visibleGroups.map(group => (
              <div key={group.label} className="mb-5">
                <p className="px-2 mb-1.5 text-[10px] uppercase tracking-[0.14em] font-semibold text-slate-400">{group.label}</p>
                {group.items.map(item => {
                  const Icon = item.icon;
                  return <button key={item.path} onClick={() => go(item.path)} className="w-full flex items-center gap-3 px-3 py-3 rounded-lg text-sm text-slate-700 hover:bg-slate-50"><Icon className="w-5 h-5 text-slate-400" /><span>{item.label}</span></button>;
                })}
              </div>
            ))}
            <button onClick={() => go('/account')} className="w-full flex items-center gap-3 px-3 py-3 rounded-lg text-sm text-slate-700 hover:bg-slate-50"><UserRound className="w-5 h-5 text-slate-400" />My Account</button>
          </div>
        )}

        <main className="flex-1 min-w-0 overflow-y-auto bg-[#f8fafc]">
          <div className="max-w-[1440px] mx-auto p-4 sm:p-6 lg:p-8">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
