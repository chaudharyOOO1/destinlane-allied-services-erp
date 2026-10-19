import { useState } from 'react';
import { ChevronUp, ChevronDown, ChevronsUpDown, Inbox } from 'lucide-react';

export default function Table({
  columns,
  data = [],
  onRowClick = null,
  emptyMessage = 'Records will appear here when they are added.',
  emptyTitle = 'No records found',
  label = 'Records',
}) {
  const [sortKey, setSortKey] = useState(null);
  const [sortAsc, setSortAsc] = useState(true);
  function handleSort(key) {
    if (sortKey === key) setSortAsc(value => !value);
    else { setSortKey(key); setSortAsc(true); }
  }
  const sortedData = [...data].sort((a, b) => {
    if (!sortKey) return 0;
    const left = a[sortKey]; const right = b[sortKey];
    if (left == null && right == null) return 0;
    if (left == null) return 1;
    if (right == null) return -1;
    const result = typeof left === 'number' && typeof right === 'number' ? left - right : String(left).localeCompare(String(right), undefined, { numeric: true });
    return sortAsc ? result : -result;
  });

  if (!data.length) return <div className="rounded-xl border border-slate-200 bg-white px-5 py-12 text-center">
    <Inbox size={27} className="mx-auto mb-3 text-slate-400" aria-hidden="true" />
    <h3 className="text-sm font-semibold text-slate-800">{emptyTitle}</h3><p className="mx-auto mt-1 max-w-md text-sm text-slate-500">{emptyMessage}</p>
  </div>;

  return <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
    <table className="w-full border-collapse text-left text-sm" aria-label={label}>
      <thead className="bg-slate-50"><tr className="border-b border-slate-200">{columns.map(col => {
        const sorted = sortKey === col.accessorKey;
        return <th key={col.id || col.accessorKey} scope="col" aria-sort={col.accessorKey ? sorted ? sortAsc ? 'ascending' : 'descending' : 'none' : undefined} className={`px-5 py-3 text-xs font-semibold text-slate-600 ${col.className || ''}`}>
          {col.accessorKey ? <button type="button" onClick={() => handleSort(col.accessorKey)} className="flex items-center gap-1.5 rounded text-left hover:text-slate-950" aria-label={`Sort by ${typeof col.header === 'string' ? col.header : col.accessorKey}`}><span>{col.header}</span>{sorted ? sortAsc ? <ChevronUp size={14} /> : <ChevronDown size={14} /> : <ChevronsUpDown size={13} className="text-slate-400" />}</button> : col.header}
        </th>;
      })}</tr></thead>
      <tbody className="divide-y divide-slate-100">{sortedData.map((row, index) => <tr key={row.id ?? index} tabIndex={onRowClick ? 0 : undefined} aria-label={onRowClick ? `Open ${row.invoice_number || row.name || row.company_name || `record ${index + 1}`}` : undefined} onClick={() => onRowClick?.(row)} onKeyDown={event => {
        if (onRowClick && event.target === event.currentTarget && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); onRowClick(row); }
      }} className={`${onRowClick ? 'cursor-pointer' : ''} transition-colors hover:bg-slate-50`}>{columns.map(col => <td key={col.id || col.accessorKey} className={`px-5 py-4 text-sm text-slate-700 ${col.cellClassName || ''}`}>{(col.render ? col.render(row) : row[col.accessorKey]) ?? '—'}</td>)}</tr>)}</tbody>
    </table>
  </div>;
}
