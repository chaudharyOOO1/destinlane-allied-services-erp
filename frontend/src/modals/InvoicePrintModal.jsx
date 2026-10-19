import Modal from '../components/Modal';
import CompanyLogo from '../components/CompanyLogo';
import { formatCurrency, formatDate } from '../utils/helpers';
import StatusBadge from '../components/StatusBadge';
import { Printer } from 'lucide-react';
import { useCompany } from '../context/CompanyContext';

export default function InvoicePrintModal({ isOpen, onClose, invoice = null }) {
  const { company, loading, error } = useCompany();
  if (!invoice) return null;

  const address = [company.address, company.city, company.state, company.pincode].filter(Boolean).join(', ');
  const contact = [company.contact_email, company.contact_phone].filter(Boolean).join(' · ');

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      maxWidth="max-w-3xl"
      title={`Invoice: ${invoice.invoice_number}`}
      subtitle={`Billing month: ${invoice.billing_month}`}
    >
      <article className="invoice-print-sheet space-y-6 rounded-lg p-2 text-xs sm:p-4" aria-label={`Invoice ${invoice.invoice_number}`}>
        <header className="flex flex-col justify-between gap-6 border-b border-slate-200 pb-6 sm:flex-row">
          <div className="max-w-md space-y-3">
            <CompanyLogo name={company.legal_name} subtitle="" />
            {address && <p className="leading-5 text-slate-600">{address}</p>}
            {company.gstin && <p className="text-slate-600">GSTIN: {company.gstin}</p>}
            {contact && <p className="break-words text-slate-500">{contact}</p>}
            {loading && <p className="text-slate-500" role="status">Loading company details…</p>}
            {error && <p className="text-rose-700" role="alert">{error}</p>}
          </div>
          <div className="shrink-0 space-y-2 text-left sm:text-right">
            <h2 className="text-lg font-semibold uppercase tracking-wide text-slate-900">Invoice</h2>
            <p className="font-semibold text-slate-900">{invoice.invoice_number}</p>
            <StatusBadge status={invoice.status} />
            <dl className="space-y-1 pt-2 text-slate-600">
              <div><dt className="inline">Issued: </dt><dd className="inline">{formatDate(invoice.issue_date)}</dd></div>
              <div><dt className="inline">Due: </dt><dd className="inline">{formatDate(invoice.due_date)}</dd></div>
            </dl>
          </div>
        </header>

        <section className="grid grid-cols-1 gap-5 sm:grid-cols-2" aria-label="Billing details">
          <div>
            <h3 className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Bill to</h3>
            <p className="mt-2 text-sm font-semibold text-slate-900">{invoice.client_name || `Client #${invoice.client_id}`}</p>
            <p className="mt-1 text-slate-500">Client reference: {invoice.client_id}</p>
          </div>
          <div className="sm:text-right">
            <h3 className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Billing period</h3>
            <p className="mt-2 text-sm font-medium text-slate-900">{invoice.billing_month}</p>
            <p className="mt-1 text-slate-500">Payment due on {formatDate(invoice.due_date)}</p>
          </div>
        </section>

        <div className="overflow-x-auto rounded-lg border border-slate-200">
          <table className="w-full border-collapse text-left">
            <caption className="sr-only">Invoice charges</caption>
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-[10px] uppercase tracking-wide text-slate-500">
                <th scope="col" className="p-3 font-semibold">Description</th>
                <th scope="col" className="p-3 text-right font-semibold">Taxable amount</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="p-3 align-top">
                  <p className="font-medium text-slate-900">Services for {invoice.billing_month}</p>
                  {invoice.notes && <p className="mt-1 whitespace-pre-wrap leading-5 text-slate-500">{invoice.notes}</p>}
                </td>
                <td className="p-3 text-right align-top font-medium tabular-nums text-slate-900">{formatCurrency(invoice.subtotal)}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="flex justify-end border-t border-slate-200 pt-4">
          <dl className="w-full space-y-3 sm:w-64">
            <div className="flex justify-between gap-4"><dt>Subtotal</dt><dd className="font-medium tabular-nums">{formatCurrency(invoice.subtotal)}</dd></div>
            <div className="flex justify-between gap-4"><dt>GST{invoice.tax_rate != null ? ` (${invoice.tax_rate}%)` : ''}</dt><dd className="font-medium tabular-nums">{formatCurrency(invoice.tax_amount)}</dd></div>
            <div className="flex justify-between gap-4 border-t border-slate-200 pt-3 text-sm font-semibold text-slate-900"><dt>Invoice total</dt><dd className="tabular-nums">{formatCurrency(invoice.total_amount)}</dd></div>
          </dl>
        </div>

        <p className="border-t border-slate-200 pt-4 text-[10px] text-slate-500">Generated from the company’s recorded billing details.</p>

        <div className="flex justify-end gap-3 border-t border-slate-200 pt-4 print:hidden">
          <button type="button" onClick={onClose} className="rounded-lg border border-slate-300 px-4 py-2 font-medium text-slate-600 hover:bg-slate-50">Close</button>
          <button
            type="button"
            onClick={() => window.print()}
            disabled={loading || Boolean(error)}
            className="flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Printer className="h-4 w-4" /> Print / Save PDF
          </button>
        </div>
      </article>
    </Modal>
  );
}
