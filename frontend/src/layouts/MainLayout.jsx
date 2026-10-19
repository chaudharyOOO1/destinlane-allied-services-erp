import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { roleLabel } from '../utils/roleLabels';
import { useAuth } from '../context/AuthContext';
import { useCompany } from '../context/CompanyContext';
import { useAccess } from '../context/AccessContext';
import CommandPalette from '../components/CommandPalette';
import { NAV_GROUPS } from '../config/navigation';
import CompanyLogo from '../components/CompanyLogo';
import { Search, LogOut, ChevronDown, Menu, X, ChevronRight, UserRound } from 'lucide-react';

export default function MainLayout({ children, onQuickAction = null }) {
  const { user, logout } = useAuth();
  const { canPage, home } = useAccess();
  const { company } = useCompany();
  const location = useLocation();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const accountRef = useRef(null);
  const mobileRef = useRef(null);
  const menuButtonRef = useRef(null);
  const visibleGroups = NAV_GROUPS.map(group => ({ ...group, items: group.items.filter(item => canPage(item.path)) })).filter(group => group.items.length);
  const activeItem = NAV_GROUPS.flatMap(group => group.items).find(item => item.path === location.pathname || (item.path === '/erp' && location.pathname === '/dashboard'));
  const fullName = user?.full_name || user?.login_id || 'My account';
  const initials = fullName.split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]).join('').toUpperCase();

  useEffect(() => {
    if (!accountMenuOpen) return;
    function dismiss(event) {
      if (event.type === 'keydown' && event.key !== 'Escape') return;
      if (event.type === 'keydown' || !accountRef.current?.contains(event.target)) setAccountMenuOpen(false);
    }
    document.addEventListener('pointerdown', dismiss);
    document.addEventListener('keydown', dismiss);
    return () => { document.removeEventListener('pointerdown', dismiss); document.removeEventListener('keydown', dismiss); };
  }, [accountMenuOpen]);

  useEffect(() => {
    if (!mobileMenuOpen) return;
    const previousOverflow = document.body.style.overflow;
    const trigger = menuButtonRef.current;
    document.body.style.overflow = 'hidden';
    mobileRef.current?.querySelector('button')?.focus();
    function keyboard(event) {
      if (event.key === 'Escape') { event.preventDefault(); setMobileMenuOpen(false); }
      if (event.key === 'Tab') {
        const controls = [...mobileRef.current.querySelectorAll('button, a')];
        const first = controls[0]; const last = controls.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    }
    function desktop() { if (window.matchMedia('(min-width: 768px)').matches) setMobileMenuOpen(false); }
    document.addEventListener('keydown', keyboard);
    window.addEventListener('resize', desktop);
    return () => { document.body.style.overflow = previousOverflow; document.removeEventListener('keydown', keyboard); window.removeEventListener('resize', desktop); trigger?.focus(); };
  }, [mobileMenuOpen]);

  function closeMenus() { setMobileMenuOpen(false); setAccountMenuOpen(false); }
  function navigation(mobile = false) {
    return <nav aria-label={mobile ? 'Mobile workspace navigation' : 'Workspace navigation'} className="space-y-5">
      {visibleGroups.map(group => <section key={group.label}>
        <h2 className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.13em] text-slate-500">{group.label}</h2>
        <div className="space-y-1">{group.items.map(item => {
          const Icon = item.icon;
          const active = activeItem?.path === item.path;
          return <Link key={item.path} to={item.path} onClick={closeMenus} aria-current={active ? 'page' : undefined} className={`flex items-center gap-3 rounded-lg px-3 ${mobile ? 'py-3 text-sm' : 'py-2.5 text-[13px]'} font-medium transition-colors ${active ? 'bg-[#eef3f7] text-[#0b2f4a] shadow-[inset_3px_0_0_#b88935]' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-950'}`}>
            <Icon size={17} className={`shrink-0 ${active ? 'text-[#0b2f4a]' : 'text-slate-500'}`} /><span className="min-w-0 flex-1">{item.label}</span>
            {active && <ChevronRight size={14} className="text-[#0b2f4a]" />}
          </Link>;
        })}</div>
      </section>)}
    </nav>;
  }

  return <div className="erp-shell min-h-screen bg-slate-50 text-slate-900">
    <a href="#workspace-content" className="sr-only fixed left-3 top-3 z-[100] rounded-lg bg-white px-4 py-3 text-sm font-medium shadow-lg focus:not-sr-only">Skip to main content</a>
    <CommandPalette isOpen={paletteOpen} onClose={() => setPaletteOpen(false)} onToggle={() => { closeMenus(); setPaletteOpen(true); }} onAction={onQuickAction} />
    <header className="sticky top-0 z-40 flex h-16 items-center gap-3 border-b border-slate-200 bg-white px-4 lg:px-6">
      <button ref={menuButtonRef} type="button" onClick={() => setMobileMenuOpen(true)} aria-label="Open navigation" aria-expanded={mobileMenuOpen} aria-controls="mobile-workspace-navigation" className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 md:hidden"><Menu size={21} /></button>
      <Link to={home} onClick={closeMenus} aria-label={`${company.display_name} home`} className="flex min-w-0 shrink items-center gap-2.5 md:w-[206px] md:shrink-0">
        <CompanyLogo compact className="h-9 w-auto sm:hidden" />
        <CompanyLogo className="hidden h-9 w-auto max-w-[200px] sm:flex" />
      </Link>
      <span className="hidden h-6 w-px bg-slate-200 lg:block" aria-hidden="true" />
      <p className="hidden text-sm font-medium text-slate-600 lg:block">{activeItem?.label || 'My Account'}</p>
      <div className="ml-auto flex items-center gap-2 sm:gap-4">
        <button type="button" onClick={() => { closeMenus(); setPaletteOpen(true); }} aria-label="Search workspace pages" className="flex items-center gap-2 rounded-lg p-2 text-slate-500 hover:bg-slate-50 sm:border sm:border-slate-200 sm:px-3 sm:py-2">
          <Search size={17} /><span className="hidden text-xs sm:inline">Find a page</span><kbd className="ml-5 hidden rounded border border-slate-200 px-1 py-0.5 text-[10px] text-slate-400 xl:inline">Ctrl K</kbd>
        </button>
        <div ref={accountRef} className="relative">
          <button type="button" onClick={() => setAccountMenuOpen(value => !value)} aria-label={`Account menu for ${fullName}`} aria-expanded={accountMenuOpen} aria-controls="workspace-account-menu" className="flex items-center gap-2 rounded-lg py-1 pl-1 pr-1.5 text-left hover:bg-slate-50">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-slate-200 bg-slate-100 text-xs font-semibold text-slate-700">{initials}</span>
            <span className="hidden max-w-44 sm:block"><span className="block truncate text-xs font-semibold text-slate-800">{fullName}</span><span className="block text-[11px] text-slate-500">{roleLabel(user?.role)}</span></span>
            <ChevronDown size={14} className="text-slate-400" />
          </button>
          {accountMenuOpen && <div id="workspace-account-menu" className="absolute right-0 top-full z-50 mt-2 w-64 rounded-xl border border-slate-200 bg-white p-2 shadow-lg">
            <div className="mb-1 border-b border-slate-100 px-3 py-3"><p className="break-words text-sm font-semibold">{fullName}</p><p className="mt-1 text-xs text-slate-500">{roleLabel(user?.role)}{user?.login_id ? ` · ${user.login_id}` : ''}</p></div>
            <Link to="/account" onClick={closeMenus} className="flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm text-slate-700 hover:bg-slate-50"><UserRound size={16} />My Account</Link>
            <button type="button" onClick={logout} className="flex w-full items-center gap-2 rounded-lg px-3 py-2.5 text-sm text-rose-700 hover:bg-rose-50"><LogOut size={16} />Sign out</button>
          </div>}
        </div>
      </div>
    </header>
    <div className="flex items-start">
      <aside className="sticky top-16 hidden h-[calc(100dvh-4rem)] w-[244px] shrink-0 flex-col border-r border-slate-200 bg-white md:flex">
        <div className="flex-1 overflow-y-auto px-3 py-6">{navigation()}</div>
        <div className="border-t border-slate-100 p-4"><Link to="/account" className="flex items-center gap-2 rounded-lg px-2 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50"><UserRound size={16} />My Account</Link><p className="mt-2 px-2 text-[10px] text-slate-400">DestinLane · Business workspace</p></div>
      </aside>
      <main id="workspace-content" tabIndex={-1} className="min-w-0 flex-1 outline-none">
        <div className={`mx-auto max-w-[1600px] p-4 sm:p-6 xl:p-8 ${location.pathname === '/billing' ? 'space-y-6' : ''}`}>{children}</div>
      </main>
    </div>
    {mobileMenuOpen && <div id="mobile-workspace-navigation" ref={mobileRef} role="dialog" aria-modal="true" aria-label="Workspace navigation" className="fixed inset-0 z-[70] flex flex-col overflow-y-auto bg-white md:hidden">
      <div className="sticky top-0 flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3"><CompanyLogo className="h-9 w-auto max-w-[210px]" /><button type="button" aria-label="Close navigation" onClick={() => setMobileMenuOpen(false)} className="rounded-lg p-2 text-slate-600 hover:bg-slate-100"><X size={21} /></button></div>
      <p className="px-6 pt-5 text-xs text-slate-500">{roleLabel(user?.role)} workspace</p><div className="flex-1 p-3 pt-5">{navigation(true)}</div>
      <Link to="/account" onClick={closeMenus} className="flex items-center gap-3 border-t border-slate-200 px-6 py-4 text-sm font-medium text-slate-700"><UserRound size={18} />My Account</Link>
    </div>}
  </div>;
}
