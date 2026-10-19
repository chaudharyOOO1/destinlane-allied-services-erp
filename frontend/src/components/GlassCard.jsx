// Historical name retained so existing modules can use the shared business panel.
export default function GlassCard({ className = '', children, glow: _glow = false }) {
  return <div className={`erp-panel rounded-xl p-5 sm:p-6 ${className}`}>{children}</div>;
}

GlassCard.Header = function GlassCardHeader({ title, subtitle, badge = null, action = null, className = '' }) {
  return <div className={`mb-5 flex flex-col justify-between gap-3 border-b border-slate-200 pb-4 sm:flex-row sm:items-center ${className}`}>
    <div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><h3 className="text-base font-semibold tracking-tight text-slate-900">{title}</h3>{typeof badge === 'string' && <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">{badge}</span>}</div>{subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}</div>
    {action && <div className="flex shrink-0 items-center gap-2">{action}</div>}
  </div>;
};
