// A stat presents an observed value. Decorative trends and sample sparklines
// from the original prototype are intentionally not rendered.
export default function StatCard({ label, value, icon: Icon, description = null }) {
  return <div className="erp-panel rounded-xl p-5">
    <div className="flex items-center justify-between gap-3"><p className="text-sm font-medium text-slate-600">{label}</p>{Icon && <Icon size={18} className="shrink-0 text-slate-400" aria-hidden="true" />}</div>
    <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-950 tabular-nums">{value ?? '—'}</p>
    {description && <p className="mt-1.5 text-xs leading-relaxed text-slate-500">{description}</p>}
  </div>;
}
