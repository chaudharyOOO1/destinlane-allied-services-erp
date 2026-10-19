import { useEffect, useId, useRef, useState } from 'react';
import { useAccess } from '../context/AccessContext';
import { useNavigate } from 'react-router-dom';
import { Search, UserRound, ArrowUpRight, X } from 'lucide-react';
import { NAV_GROUPS } from '../config/navigation';

export default function CommandPalette({ isOpen, onClose, onToggle = null, onAction = null }) {
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(0);
  const navigate = useNavigate();
  const { canPage } = useAccess();
  const dialogRef = useRef(null);
  const inputRef = useRef(null);
  const titleId = useId();
  const items = [...NAV_GROUPS.flatMap(group => group.items.map(item => ({ ...item, group: group.label }))),
    { label: 'My Account', path: '/account', icon: UserRound, group: 'Account' }]
    .filter(item => canPage(item.path))
    .filter(item => `${item.label} ${item.group}`.toLowerCase().includes(query.toLowerCase().trim()));
  const selectedIndex = Math.min(selected, Math.max(0, items.length - 1));

  useEffect(() => {
    function handleShortcut(event) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        if (isOpen) { setQuery(''); setSelected(0); onClose(); }
        else if (onToggle) onToggle();
        else onAction?.('toggle_palette');
      }
    }
    window.addEventListener('keydown', handleShortcut);
    return () => window.removeEventListener('keydown', handleShortcut);
  }, [isOpen, onClose, onToggle, onAction]);

  useEffect(() => {
    if (!isOpen) return;
    const previous = document.activeElement;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const frame = requestAnimationFrame(() => inputRef.current?.focus());
    return () => { cancelAnimationFrame(frame); document.body.style.overflow = overflow; previous?.focus?.(); };
  }, [isOpen]);

  if (!isOpen) return null;

  function close() { setQuery(''); setSelected(0); onClose(); }
  function choose(item) { if (item) { navigate(item.path); close(); } }
  function handleKeyDown(event) {
    if (event.key === 'Escape') { event.preventDefault(); close(); }
    if ((event.key === 'ArrowDown' || event.key === 'ArrowUp') && event.target === inputRef.current) {
      event.preventDefault();
      const next = items.length ? (selectedIndex + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length : 0;
      setSelected(next);
      dialogRef.current?.querySelector(`[data-command-index="${next}"]`)?.scrollIntoView({ block: 'nearest' });
    }
    if (event.key === 'Enter' && event.target === inputRef.current) { event.preventDefault(); choose(items[selectedIndex]); }
    if (event.key === 'Tab') {
      const focusable = [...dialogRef.current.querySelectorAll('button, input')];
      const first = focusable[0]; const last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }
  }

  return <div className="fixed inset-0 z-[90] flex items-start justify-center p-3 pt-[12vh] sm:p-6 sm:pt-[14vh]">
    <div className="absolute inset-0 bg-slate-950/45" onClick={close} aria-hidden="true" />
    <section ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby={titleId} onKeyDown={handleKeyDown} className="relative w-full max-w-xl overflow-hidden rounded-xl border border-slate-200 bg-white shadow-2xl modal-enter">
      <h2 id={titleId} className="sr-only">Find a page</h2>
      <div className="flex items-center gap-3 border-b border-slate-200 px-4 py-3">
        <Search size={19} className="shrink-0 text-slate-500" />
        <input ref={inputRef} aria-label="Search pages" value={query} onChange={event => { setQuery(event.target.value); setSelected(0); }} placeholder="Search workspace pages…" className="min-w-0 flex-1 bg-transparent py-1 text-sm text-slate-900 outline-none placeholder:text-slate-400" />
        <button type="button" onClick={close} aria-label="Close page search" className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100"><X size={18} /></button>
      </div>
      <div className="max-h-[50vh] overflow-y-auto p-2">
        {items.length === 0 ? <p className="px-4 py-10 text-center text-sm text-slate-500">No accessible pages match your search.</p> : items.map((item, index) => {
          const Icon = item.icon;
          return <button type="button" key={item.path} data-command-index={index} onFocus={() => setSelected(index)} onClick={() => choose(item)} className={`flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left ${index === selectedIndex ? 'bg-[#eef3f7] text-[#0b2f4a]' : 'text-slate-700 hover:bg-slate-50'}`}>
            <Icon size={18} className="shrink-0 text-slate-500" />
            <span className="flex-1 text-sm font-medium">{item.label}</span>
            <span className="hidden text-xs text-slate-500 sm:block">{item.group}</span><ArrowUpRight size={15} className="text-slate-400" />
          </button>;
        })}
      </div>
      <p className="border-t border-slate-100 px-4 py-2.5 text-xs text-slate-500">↑ ↓ to browse · Enter to open · Esc to close</p>
    </section>
  </div>;
}
