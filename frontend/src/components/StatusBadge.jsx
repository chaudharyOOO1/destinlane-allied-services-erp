const tones = {
  positive: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  warning: 'border-amber-200 bg-amber-50 text-amber-800',
  negative: 'border-rose-200 bg-rose-50 text-rose-800',
  info: 'border-sky-200 bg-sky-50 text-sky-800',
  neutral: 'border-slate-200 bg-slate-50 text-slate-600',
};
const statusTones = {
  ACTIVE: 'positive', APPROVED: 'positive', COMPLETED: 'positive', PRESENT: 'positive', PAID: 'positive', POSTED: 'positive', TRUE: 'positive',
  ON_LEAVE: 'warning', DAY: 'warning', HALF_DAY: 'warning', LATE: 'warning', PENDING: 'warning', SUBMITTED: 'warning',
  TERMINATED: 'negative', ABSENT: 'negative', OVERDUE: 'negative', REJECTED: 'negative', HELD: 'negative',
  SCHEDULED: 'info', NIGHT: 'info', SENT: 'info',
};

export default function StatusBadge({ status }) {
  if (status === null || status === undefined || status === '') return null;
  const normalized = String(status).toUpperCase();
  const label = normalized === 'TRUE' ? 'Yes' : normalized === 'FALSE' ? 'No' : normalized.toLowerCase().replaceAll('_', ' ').replace(/^./, char => char.toUpperCase());
  return <span className={`inline-flex items-center whitespace-nowrap rounded-md border px-2 py-0.5 text-xs font-medium ${tones[statusTones[normalized] || 'neutral']}`}>{label}</span>;
}
