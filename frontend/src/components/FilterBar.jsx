import { Search, LayoutGrid, List, Download, X } from 'lucide-react';

export default function FilterBar({
  searchTerm,
  setSearchTerm,
  filters = [],
  onFilterChange,
  placeholder = 'Search records…',
  searchLabel = 'Search records',
  viewMode = null,
  setViewMode = null,
  onExport = null,
}) {
  return <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
    <div className="relative min-w-0 flex-1"><Search size={17} aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
      <input type="search" aria-label={searchLabel} value={searchTerm} onChange={event => setSearchTerm(event.target.value)} placeholder={placeholder} className="h-10 w-full rounded-lg border border-slate-300 bg-white pl-10 pr-10 text-sm text-slate-900 placeholder:text-slate-400" />
      {searchTerm && <button type="button" onClick={() => setSearchTerm('')} aria-label="Clear search" className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-slate-500 hover:bg-slate-100"><X size={16} /></button>}
    </div>
    <div className="flex flex-wrap items-center gap-2">{filters.map(filter => <label key={filter.name} className="min-w-0"><span className="sr-only">{filter.label || `${filter.name.replaceAll('_', ' ')} filter`}</span><select value={filter.value} onChange={event => onFilterChange?.(filter.name, event.target.value)} className="h-10 max-w-full rounded-lg border border-slate-300 bg-white pl-3 pr-8 text-sm text-slate-700">{filter.options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>)}
      {viewMode && setViewMode && <div className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white p-1" role="group" aria-label="Record display">
        <button type="button" onClick={() => setViewMode('table')} aria-label="Table view" aria-pressed={viewMode === 'table'} className={`rounded-md p-1.5 ${viewMode === 'table' ? 'bg-slate-100 text-slate-900' : 'text-slate-500 hover:bg-slate-50'}`}><List size={17} /></button>
        <button type="button" onClick={() => setViewMode('grid')} aria-label="Card view" aria-pressed={viewMode === 'grid'} className={`rounded-md p-1.5 ${viewMode === 'grid' ? 'bg-slate-100 text-slate-900' : 'text-slate-500 hover:bg-slate-50'}`}><LayoutGrid size={17} /></button>
      </div>}
      {onExport && <button type="button" onClick={onExport} className="inline-flex h-10 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-slate-700 hover:bg-slate-50"><Download size={16} />Export CSV</button>}
    </div>
  </div>;
}
