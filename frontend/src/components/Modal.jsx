import { useEffect, useId, useRef } from 'react';
import { X } from 'lucide-react';

export default function Modal({ isOpen, onClose, title, subtitle, children, maxWidth = 'max-w-2xl' }) {
  const dialogRef = useRef(null);
  const closeRef = useRef(onClose);
  const titleId = useId();
  const subtitleId = useId();
  // Keep the current close guard without restarting focus/scroll management
  // whenever a parent rerenders during form editing.
  useEffect(() => { closeRef.current = onClose; }, [onClose]);
  useEffect(() => {
    if (!isOpen) return;
    const previous = document.activeElement;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const firstControl = dialogRef.current?.querySelector('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href]');
    firstControl?.focus();
    function keyboard(event) {
      if (event.key === 'Escape') { event.preventDefault(); closeRef.current?.(); }
      if (event.key === 'Tab') {
        const controls = [...dialogRef.current.querySelectorAll('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href]')].filter(node => node.getClientRects().length);
        const first = controls[0]; const last = controls.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    }
    document.addEventListener('keydown', keyboard);
    return () => { document.removeEventListener('keydown', keyboard); document.body.style.overflow = overflow; previous?.focus?.(); };
  }, [isOpen]);

  if (!isOpen) return null;
  return <div className="fixed inset-0 z-[80] flex items-start justify-center overflow-y-auto p-3 sm:p-6">
    <div className="fixed inset-0 bg-slate-950/45" onClick={onClose} aria-hidden="true" />
    <section ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={subtitle ? subtitleId : undefined} className={`modal-enter relative my-auto w-full ${maxWidth} rounded-xl border border-slate-200 bg-white p-5 shadow-xl sm:my-6 sm:p-6`}>
      <header className="mb-5 flex items-start justify-between gap-4 border-b border-slate-200 pb-4"><div><h2 id={titleId} className="text-xl font-semibold tracking-tight text-slate-900">{title}</h2>{subtitle && <p id={subtitleId} className="mt-1 text-sm leading-relaxed text-slate-500">{subtitle}</p>}</div><button type="button" aria-label="Close dialog" onClick={onClose} className="shrink-0 rounded-lg p-2 text-slate-500 hover:bg-slate-100"><X size={20} /></button></header>
      <div className="max-h-[calc(100dvh-13rem)] overflow-y-auto px-0.5 py-0.5">{children}</div>
    </section>
  </div>;
}
