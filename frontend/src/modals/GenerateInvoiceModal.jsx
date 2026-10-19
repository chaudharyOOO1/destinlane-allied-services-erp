import { useRef, useState } from 'react';
import Modal from '../components/Modal';
import api from '../api/axios';
import { formatCurrency } from '../utils/helpers';

const currentMonth = () => new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Asia/Kolkata', year: 'numeric', month: '2-digit',
}).format(new Date()).slice(0, 7);
const input = 'mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900';

export default function GenerateInvoiceModal({ isOpen, onClose, onSave, clients = [] }) {
  const [clientId, setClientId] = useState('');
  const [month, setMonth] = useState(currentMonth);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const active = useRef(false);

  async function generate(event) {
    event.preventDefault();
    if (active.current || result) return;
    active.current = true;
    setBusy(true);
    setError('');
    try {
      const { data } = await api.post('/erp/billing/generate', { month, client_id: Number(clientId) });
      // Acknowledge committed invoices before any directory read or navigation.
      setResult(data);
      onSave(data.invoices || []);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : err.response
        ? 'Invoice generation failed. Check the selected client, rates and attendance.'
        : 'The response was lost. Close and refresh the invoice list before trying again; the server may have saved invoices.');
    } finally {
      active.current = false;
      setBusy(false);
    }
  }
  function close() {
    if (active.current) return;
    setError('');
    setResult(null);
    onClose();
  }
  return <Modal isOpen={isOpen} onClose={close} title="Generate invoice drafts"
    subtitle="Use verified attendance and the effective site rate cards.">
    {result ? <div className="space-y-4 text-sm text-slate-700">
      <p role="status" className="rounded-lg bg-emerald-50 p-3 text-emerald-800">
        {result.invoices_created > 0 ? `${result.invoices_created} invoice draft(s) saved for ${result.month}.` : 'No new invoice drafts were created.'}
      </p>
      {(result.invoices || []).map(invoice => <div key={invoice.id} className="flex flex-wrap justify-between gap-2 rounded-lg border border-slate-200 p-3">
        <span>{invoice.invoice_number}</span><strong>{formatCurrency(invoice.total_amount)}</strong>
      </div>)}
      {!result.invoices_created && <p>Invoices may already exist, or completed verified attendance may have no billable effective rate. Review attendance, contracts and rates before generating again.</p>}
      <p className="text-xs text-slate-500">Saved drafts are not payment receipts or posted bookkeeping entries. Review the invoice and tax treatment before issuing it.</p>
      <button onClick={close} className="rounded-lg bg-slate-900 px-4 py-2 text-white">Done</button>
    </div> : <form onSubmit={generate} className="space-y-5 text-sm text-slate-700">
      <fieldset disabled={busy} className="grid gap-4 sm:grid-cols-2">
        <label>Client<select required aria-label="Invoice client" value={clientId} onChange={event => setClientId(event.target.value)} className={input}>
          <option value="">Select client</option>
          {clients.map(client => <option key={client.id} value={client.id}>{client.company_name}</option>)}
        </select></label>
        <label>Billing month<input required aria-label="Invoice billing month" type="month" value={month} onChange={event => setMonth(event.target.value)} className={input}/></label>
      </fieldset>
      <div className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-4 text-xs leading-5">
        <p>Amounts are calculated on the server from completed, verified attendance and the matching site rates. Existing month/site invoices are skipped.</p>
        <p>The current billing policy applies 18% GST and a regional tax split. Review these draft taxes with Accounts before issuing an invoice.</p>
      </div>
      {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-rose-700">{error}</p>}
      <div className="flex justify-end gap-3">
        <button type="button" onClick={close} disabled={busy} className="rounded-lg border border-slate-200 px-4 py-2">Cancel</button>
        <button disabled={busy || !clientId || !clients.length} className="rounded-lg bg-slate-900 px-4 py-2 font-semibold text-white disabled:opacity-50">{busy ? 'Generating…' : 'Generate drafts'}</button>
      </div>
    </form>}
  </Modal>;
}
