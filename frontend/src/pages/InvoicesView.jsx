import { useState, useEffect, useCallback } from 'react';
import MainLayout from '../layouts/MainLayout';
import StatCard from '../components/StatCard';
import FilterBar from '../components/FilterBar';
import Table from '../components/Table';
import StatusBadge from '../components/StatusBadge';
import DetailDrawer from '../components/DetailDrawer';
import GenerateInvoiceModal from '../modals/GenerateInvoiceModal';
import InvoicePrintModal from '../modals/InvoicePrintModal';
import { formatCurrency, formatDate } from '../utils/helpers';
import api from '../api/axios';
import { useAuth } from '../context/AuthContext';
import { useAccess } from '../context/AccessContext';
import { ReceiptText, Plus, DollarSign, CheckCircle2, Clock, Printer, ShieldAlert } from 'lucide-react';

export default function InvoicesView() {
  const {user}=useAuth();
  const {can}=useAccess();
  const role=user.role;
  const canCreate = can('billing.create');
  const canLoadClients = canCreate && can('clients.view');
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [lookupWarning, setLookupWarning] = useState('');

  const [invoices, setInvoices] = useState([]);
  const [clients, setClients] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [monthFilter, setMonthFilter] = useState('ALL');

  const [isGenerateModalOpen, setGenerateModalOpen] = useState(false);
  const [selectedInvoice, setSelectedInvoice] = useState(null);
  const [printingInvoice, setPrintingInvoice] = useState(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setLoadError('');
    setLookupWarning('');
    const results = await Promise.allSettled([
      api.get('/erp/billing/invoices'),
      ...(canLoadClients ? [api.get('/erp/clients')] : []),
    ]);
    if (results[0].status === 'fulfilled') setInvoices(results[0].value.data || []);
    else setLoadError('Invoices could not be loaded. Retry to show the current records.');
    if (results[1]?.status === 'fulfilled') setClients(results[1].value.data || []);
    if (canCreate && !canLoadClients) {
      setLookupWarning('Client viewing permission is required to select a client for invoice generation.');
    } else if (canCreate && results.slice(1).some(result => result.status === 'rejected')) {
      setLookupWarning('Client choices could not load. Refresh before generating an invoice.');
    }
    setLoading(false);
  }, [canCreate, canLoadClients]);
  useEffect(() => { loadData(); }, [loadData]);

  function handleSaveInvoices(saved) {
    setInvoices(current => [...saved, ...current.filter(invoice => !saved.some(row => row.id === invoice.id))]);
  }

  const enrichedInvoices = invoices.map((inv) => {
    const client = clients.find((c) => c.id === inv.client_id);
    return {
      ...inv,
      client_name: inv.client_name || client?.company_name || `Client #${inv.client_id}`,
    };
  });

  if (role === 'STAFF') {
    return (
      <MainLayout>
        <div className="min-h-[60vh] flex flex-col items-center justify-center text-center p-6 space-y-4">
          <div className="w-16 h-16 rounded-2xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-700 shadow-[0_0_20px_rgba(245,158,11,0.2)]">
            <ShieldAlert className="w-8 h-8" />
          </div>
          <h2 className="text-xl font-semibold text-slate-900">Billing Records Restricted</h2>
          <p className="text-xs text-slate-500 max-w-md">
            Corporate invoicing, client billing, and GST statements are restricted to Administrators and Corporate Clients. For wage payment schedules and overtime rates, please refer to your employee dashboard.
          </p>
          <button
            onClick={() => window.location.href = '/dashboard'}
            className="px-4 py-2 bg-white border border-slate-200 hover:border-emerald-500 text-xs font-bold text-slate-700 rounded-xl transition-all"
          >
            Return to dashboard
          </button>
        </div>
      </MainLayout>
    );
  }

  const clientScopedInvoices = enrichedInvoices;

  const filteredInvoices = clientScopedInvoices.filter((inv) => {
    const cName = inv.client_name || '';
    const num = inv.invoice_number || '';
    const notes = inv.notes || '';

    const matchesSearch =
      cName.toLowerCase().includes(searchTerm.toLowerCase()) ||
      num.toLowerCase().includes(searchTerm.toLowerCase()) ||
      notes.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesStatus = statusFilter === 'ALL' || inv.status === statusFilter;
    const matchesMonth = monthFilter === 'ALL' || inv.billing_month === monthFilter;

    return matchesSearch && matchesStatus && matchesMonth;
  });

  const isPaid = invoice => invoice.clearance_status === 'PAID' || invoice.status === 'PAID';
  const totalRevenue = clientScopedInvoices.reduce((sum, inv) => sum + Number(inv.total_amount || 0), 0);
  const paidRevenue = clientScopedInvoices
    .filter(isPaid)
    .reduce((sum, inv) => sum + Number(inv.total_amount || 0), 0);
  const pendingDraftRevenue = clientScopedInvoices
    .filter((inv) => !isPaid(inv) && inv.status !== 'CANCELLED')
    .reduce((sum, inv) => sum + Number(inv.total_amount || 0), 0);
  const totalTaxCollected = clientScopedInvoices.reduce((sum, inv) => sum + Number(inv.tax_amount || 0), 0);

  const columns = [
    {
      id: 'invoice',
      header: 'Invoice Reference',
      accessorKey: 'invoice_number',
      render: (row) => (
        <div>
          <span className="font-mono text-xs font-bold text-teal-700">{row.invoice_number}</span>
          <p className="text-[10px] text-slate-500 font-mono">Issued: {formatDate(row.issue_date)}</p>
        </div>
      ),
    },
    {
      id: 'client',
      header: 'Client Company',
      accessorKey: 'client_name',
      render: (row) => (
        <div>
          <p className="font-bold text-slate-900 text-xs">{row.client_name}</p>
          <span className="text-[10px] text-slate-500 font-mono">Month: {row.billing_month}</span>
        </div>
      ),
    },
    {
      id: 'subtotal',
      header: 'Subtotal',
      accessorKey: 'subtotal',
      render: (row) => <span className="font-mono text-xs text-slate-600">{formatCurrency(row.subtotal)}</span>,
    },
    {
      id: 'tax',
      header: 'GST',
      accessorKey: 'tax_amount',
      render: (row) => <span className="font-mono text-xs text-amber-700">+{formatCurrency(row.tax_amount)}</span>,
    },
    {
      id: 'total',
      header: 'Total Amount',
      accessorKey: 'total_amount',
      render: (row) => (
        <span className="font-mono text-xs font-bold text-emerald-700">{formatCurrency(row.total_amount)}</span>
      ),
    },
    {
      id: 'status',
      header: 'Invoice status',
      accessorKey: 'status',
      render: (row) => <StatusBadge status={row.status} />,
    },
    {
      id: 'clearance',
      header: 'Clearance',
      render: (row) => <StatusBadge status={row.clearance_status || (row.status === 'PAID' ? 'PAID' : 'PENDING')} />,
    },
    {
      id: 'actions',
      header: 'Actions',
      render: (row) => (
        <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={() => setPrintingInvoice(row)}
            className="p-1.5 rounded-lg text-slate-500 hover:text-teal-700 hover:bg-slate-100 transition-colors"
            title="Print / View PDF"
          >
            <Printer className="w-3.5 h-3.5" />
          </button>

        </div>
      ),
    },
  ];

  return (
    <MainLayout>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-semibold text-slate-900 tracking-tight">
            {role === 'CLIENT' ? 'Client Invoices' : 'Billing & Invoices'}
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            {role === 'CLIENT'
              ? 'Review recorded invoices and download printable copies.'
              : 'Generate invoices from attendance and contract rates, then review their recorded status.'}
          </p>
        </div>
        {canCreate && (
          <button
            disabled={loading || Boolean(loadError) || Boolean(lookupWarning)}
            onClick={() => setGenerateModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold text-white bg-teal-700 hover:bg-teal-800 transition-all disabled:opacity-50 self-start sm:self-auto"
          >
            <Plus className="w-4 h-4" />
            <span>Generate Client Invoice</span>
          </button>
        )}
      </div>

      {loadError && <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{loadError} <button onClick={loadData} className="ml-2 underline" disabled={loading}>Retry</button></div>}
      {lookupWarning && <p role="status" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800">{lookupWarning} <button onClick={loadData} className="underline" disabled={loading}>Refresh</button></p>}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <StatCard
          label="Total invoices"
          value={loading || loadError ? '—' : formatCurrency(totalRevenue)}
          icon={DollarSign}

          glow={role === 'CLIENT' ? 'border-purple-500/30' : 'border-cyan-500/30'}

        />
        <StatCard
          label="Invoices marked paid"
          value={loading || loadError ? '—' : formatCurrency(paidRevenue)}
          icon={CheckCircle2}

          glow="border-emerald-500/30"

        />
        <StatCard
          label="Unpaid invoices"
          value={loading || loadError ? '—' : formatCurrency(pendingDraftRevenue)}
          icon={Clock}

          glow="border-amber-500/30"

        />
        <StatCard
          label="GST on invoices"
          value={loading || loadError ? '—' : formatCurrency(totalTaxCollected)}
          icon={ReceiptText}

          glow="border-purple-500/30"

        />
      </div>

      <p className="text-xs text-slate-500">Invoice totals reflect saved invoice statuses. Bank receipts and the general ledger are reviewed separately in Company Money.</p>
      <FilterBar
        searchTerm={searchTerm}
        setSearchTerm={setSearchTerm}
        placeholder="Search invoices by reference #, client company, memo..."
        filters={[
          {
            name: 'status',
            value: statusFilter,
            options: [
              { value: 'ALL', label: 'All Invoice Statuses' },
              { value: 'DRAFT', label: 'Draft' },
              { value: 'SENT', label: 'Sent / Issued' },
              { value: 'PAID', label: 'Paid & Settled' },
              { value: 'OVERDUE', label: 'Overdue' },
              { value: 'CANCELLED', label: 'Cancelled' },
            ],
          },
          {
            name: 'month',
            value: monthFilter,
            options: [
              { value: 'ALL', label: 'All Billing Months' },
              ...[...new Set(invoices.map(invoice => invoice.billing_month).filter(Boolean))].sort().reverse().map(month => ({ value: month, label: month })),
            ],
          },
        ]}
        onFilterChange={(name, val) => {
          if (name === 'status') setStatusFilter(val);
          if (name === 'month') setMonthFilter(val);
        }}
      />

      <Table
        columns={columns}
        data={filteredInvoices}
        onRowClick={(row) => setSelectedInvoice(row)}
        emptyTitle={loading ? "Loading invoices…" : loadError ? "Invoices unavailable" : "No invoices found"}
        emptyMessage={loading ? "Reading saved invoice records." : loadError ? "Retry loading the records above." : "No invoices match the selected filters."}
      />

      <DetailDrawer
        isOpen={!!selectedInvoice}
        onClose={() => setSelectedInvoice(null)}
        title={selectedInvoice?.client_name || 'Invoice details'}
        subtitle={`Invoice #: ${selectedInvoice?.invoice_number} | Month: ${selectedInvoice?.billing_month}`}
        data={selectedInvoice}
        type="TAX INVOICE"
        actions={
          <button
            onClick={() => {
              setPrintingInvoice(selectedInvoice);
              setSelectedInvoice(null);
            }}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold text-white bg-teal-700 hover:bg-teal-800 transition-all"
          >
            <Printer className="w-3.5 h-3.5" />
            <span>Printable PDF</span>
          </button>
        }
      />

      <GenerateInvoiceModal
        isOpen={isGenerateModalOpen}
        onClose={() => setGenerateModalOpen(false)}
        onSave={handleSaveInvoices}
        clients={clients}
      />

      <InvoicePrintModal
        isOpen={!!printingInvoice}
        onClose={() => setPrintingInvoice(null)}
        invoice={printingInvoice}
      />
    </MainLayout>
  );
}