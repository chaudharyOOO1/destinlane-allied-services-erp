import { useEffect, useId, useRef } from 'react';
import { X } from 'lucide-react';

const hiddenFields = /password|token|secret|credential/i;
const label = value => value.replaceAll('_', ' ').replace(/^./, char => char.toUpperCase());

export default function DetailDrawer({ isOpen, onClose, title, subtitle, data, type = 'generic', actions = null }) {
  const drawerRef = useRef(null);
  const closeRef = useRef(onClose);
  const headingId = useId();
  const hasData = Boolean(data);
  useEffect(() => { closeRef.current = onClose; }, [onClose]);
  useEffect(() => {
    if (!isOpen || !hasData) return;
    const previous = document.activeElement;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    drawerRef.current?.querySelector('button')?.focus();
    function keyboard(event) {
      if (event.key === 'Escape') { event.preventDefault(); closeRef.current?.(); }
      if (event.key === 'Tab') {
        const controls = [...drawerRef.current.querySelectorAll('button:not(:disabled), a, input:not(:disabled), select:not(:disabled), textarea:not(:disabled)')];
        const first = controls[0]; const last = controls.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    }
    document.addEventListener('keydown', keyboard);
    return () => { document.removeEventListener('keydown', keyboard); document.body.style.overflow = overflow; previous?.focus?.(); };
  }, [isOpen, hasData]);

  if (!isOpen || !data) return null;
  const fields = Object.entries(data).filter(([key, value]) => !hiddenFields.test(key) && key !== 'id' && (typeof value !== 'object' || value === null));
  return <div className="fixed inset-0 z-[80] flex justify-end">
    <div className="absolute inset-0 bg-slate-950/40" onClick={onClose} aria-hidden="true" />
    <section ref={drawerRef} role="dialog" aria-modal="true" aria-labelledby={headingId} className="drawer-enter relative flex h-full w-full max-w-lg flex-col border-l border-slate-200 bg-white shadow-xl">
      <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-5 sm:px-6"><div>{type !== 'generic' && <p className="mb-1 text-xs font-medium text-slate-500">{label(type)} details</p>}<h2 id={headingId} className="text-xl font-semibold text-slate-900">{title}</h2>{subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}</div><button type="button" onClick={onClose} aria-label="Close record details" className="shrink-0 rounded-lg p-2 text-slate-500 hover:bg-slate-100"><X size={20} /></button></div>
      <dl className="flex-1 divide-y divide-slate-100 overflow-y-auto px-5 sm:px-6">{fields.map(([key, value]) => <div key={key} className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)] gap-5 py-4"><dt className="text-sm text-slate-500">{label(key)}</dt><dd className="break-words text-sm font-medium text-slate-800">{value === null || value === '' ? 'Not provided' : typeof value === 'boolean' ? (value ? 'Yes' : 'No') : String(value)}</dd></div>)}</dl>
      {actions && <div className="flex flex-wrap items-center justify-end gap-3 border-t border-slate-200 px-5 py-4 sm:px-6">{actions}</div>}
    </section>
  </div>;
}
