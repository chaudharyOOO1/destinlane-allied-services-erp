# MD bookkeeping and accounting — functional specification

Purpose: an auditable, exact-decimal double-entry book for the company's current-account movements and other financial entries. Indian accrual accounting, INR and an April–March year are the starting configuration. Reports are management books, not a certified statutory financial statement or a tax return.

## Access

Server setting `MD_ACCOUNTING_USER_ID` identifies one active Management/IT account. This deployment binds the confirmed **DestinLane Administrator / ADMIN-001** identity (user ID 1). The backend and effective permission catalog deny the module to every other account, including other Management and IT Super Admin users. A manually granted permission cannot bypass the identity restriction. Unset configuration denies everyone. Ordinary account-permission editing cannot designate a new MD; changing the binding is a reviewed deployment configuration operation.

Module keys `md_accounting.view/create/edit/approve/export` control supported actions within that identity; page visibility uses those effective keys. Base API is `/api/v1/erp/md-accounting`; UI route `/md-accounting`.

## Setup and chart

Books start date, financial year starting month, opening confirmation/reason, version and period lock are persisted. Dates/year policy lock after a posted voucher or statement import. Ordinary posting requires confirmed openings. Opening vouchers use the books start date, balance-sheet accounts and equal debit/credit totals; no capital/equity plug or invented balance is generated. Genuine zero openings require an explicit reason. Existing balances must be obtained from reconciled bank balances and the previous accountant's trial balance.

The initial chart supplies bank/cash, receivables, input-tax controls, fixed assets/accumulated depreciation, payables, output-tax controls, TDS, payroll/statutory dues, advances/borrowings, capital/retained earnings, service revenue and expenses. It seeds no money. MD may create additional accounts and configure real bank details. Account codes/names/classification cannot change after use; bank details and active state remain versioned/audited. Bank ledgers must be current assets. An overdraft or other statutory reclassification needs an accountant's appropriate ledger/adjusting voucher.

## Bookkeeping

Voucher types: Opening, Payment, Receipt, Contra, Journal; Reversal is server-generated. Fields include date, business narration, party/payee, bank/document reference and 2–200 account lines with detail. Each line has one positive debit or credit, to at most two decimal places. All amounts use Decimal/Numeric, never float calculations in the accounting engine. UI totals are guidance only.

Drafts do not affect financial reports. Posting checks current version, date, period lock, active accounts, opening rules and equal nonzero total debits/credits. Payments credit bank/cash; receipts debit bank/cash; Contra uses only bank/cash accounts. Other entries use Journal. Standard cash ledger is 1000. Every current-account spend must ultimately have a posted bank credit and the correct counter-entry; deposits may settle receivables/loans rather than constitute revenue.

Posted vouchers and their lines cannot be edited/deleted. PostgreSQL triggers enforce immutability and a deferred balance check at commit, independently of UI checks. Correction creates a separately posted, linked opposite-side reversal on an open date, with a reason. One reversal per original; original history remains. Period close/reopen changes require a reason and are audited; outstanding drafts block closing through their dates. Period locking does not automatically transfer profit to retained earnings.

## Bank imports and reconciliation

CSV columns: `statement_id,date,reference,description,debit,credit`; ISO dates, no thousands separators, statement debit=withdrawal and credit=deposit. Reference/description are optional columns. Stable statement IDs are unique per bank account. Identical re-imports skip rows; conflicting IDs reject the entire import. Maximum 2 MiB/5000 rows. No bank credentials or automatic bank connection is created. Do not import a brought-forward/opening balance as a transaction.

Imported rows are separate evidence, not journal entries. Prepare a draft from a row, select the correct counter-account/party, save and post, then match to the exact opposite-side bank book line for the same bank and amount. Opening vouchers cannot be matched as transactions. Each statement/book line can match once; unmatching requires a reason and is audited. No automatic transaction classification or two-way bank synchronisation is claimed.

Reconciliation as of a date:

`Expected statement balance = book balance + outstanding payments − deposits in transit + unbooked statement credits − unbooked statement debits`.

A zero unexplained difference, zero unbooked statement rows and confirmed openings produce RECONCILED; otherwise REVIEW_REQUIRED. Completeness of imported statements, actual bank closing balance and correct counter-accounts remain the MD/accountant's responsibility. Zero arithmetic difference alone does not establish completeness. Reconciliation snapshots/references are stored in the audit.

## Reports and formulas

Only POSTED voucher lines through the report date contribute. All ledgers, including inactive ones with history, are included.

- Account net balance = cumulative debit − credit. Trial debit balance=max(net,0), credit=max(−net,0); total closing debits must equal credits.
- Period revenue = revenue-account credits − debits; period expense = expense-account debits − credits; net profit=revenue−expense.
- Balance-sheet assets = asset-account debit−credit; liabilities/equity = relevant account credit−debit. Add unclosed profit/loss to recorded equity, separately displaying current FY earnings and prior unclosed earnings. Assets−liabilities−total equity must equal zero.
- General ledger shows opening/running/closing signed balances, dates, voucher, party, reference and narration. Debit positive/credit negative is explicit.
- CSV exports include trial balance/P&L/balance sheet or detailed ledger. Free-text spreadsheet formulas are escaped.

A user-selected P&L period does not redefine cumulative balance-sheet earnings. Year-end closing/reclassification must be posted by the accountant with appropriate dates; no silent annual reset occurs.

## GST and statutory scope

GST arithmetic accepts a deliberately entered rate and intra/inter-state choice. Intra-state CGST/SGST each = taxable value × rate / 200, rounded HALF_UP to paise; interstate IGST = value × rate / 100. Invoice total sums the rounded components. No rate, place-of-supply, reverse-charge, exemption, TDS rate, ITC eligibility, payroll contribution or depreciation schedule is assumed by this calculator.

Record eligible tax controls separately from revenue/expense, e.g. Dr Receivable 1180 / Cr Service Revenue 1000 / Cr Output GST 180. Collection is Dr Bank / Cr Receivable, not revenue again. Salary accrual, salary payment and remittance of employee/statutory liabilities are separate vouchers; do not expense a liability settlement twice.

The chart provides current/non-current/equity groupings compatible with preparing accountant-reviewed statements. Complete Schedule III presentation, applicable AS/Ind AS division, comparative figures, disclosures/notes, deferred/current tax, valuation, cash-flow statements, filings, statutory audit/signature and legal-policy determination are not automated or certified here. Do not label a balanced management report legally compliant solely because its equation balances.

## Source boundary

These books do not silently reuse the old dashboard's gross invoice/payroll totals. Existing invoices, expenses (including paid Travel claims), payroll, collections and bank movements require deliberate vouchers/reconciliation; no automatic migration/import/classification is performed. Avoid posting an expense a second time when paying an already accrued payable. Operational records and bank feeds are not a replacement for a complete ledger.

## Evidence and source map

Models: `models/md_accounting.py`; input contracts: `schemas/md_accounting.py`; calculations: `services/md_accounting.py`; scoped routes: `api/v1/endpoints/md_accounting.py`; identity/permission gates: config, `api/permissions.py`, `api/deps.py`; UI: `frontend/src/pages/MDAccounting.jsx`.

Tests cover exact known books, GST separation, current/prior earnings, draft exclusion, stale versions, opening/period rules, reversal, CSV re-imports, matching/reconciliation and other-role/other-owner denial. PostgreSQL tests additionally attempt direct modification/unbalanced posting and check browser-role denial. Browser tests use a simulated API to exercise the operator journey/mobile layout; they are not live bank or statutory acceptance.
