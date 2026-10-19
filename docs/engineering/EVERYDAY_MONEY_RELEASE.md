# Company Money — everyday recording handover

19 October 2026. Scope: simplify the designated MD's existing bookkeeping workspace. No migration, new dependency, financial data import or role expansion is required.

## Read the code in this order

1. `frontend/src/pages/MDWorkspace.jsx`: business form → server preview → save draft → versioned confirmation. The acknowledged response is retained before refreshing lists/reports. Record-bank-row origin is carried only until posting/matching.
2. `backend/app/schemas/md_transactions.py`: closed business-input contract; caller cannot set lines/status/totals.
3. `backend/app/services/md_transactions.py`: account eligibility and business-action-to-journal mapping. Money is Decimal; exactly two balanced lines are generated. Revalidate at save, not only preview.
4. `backend/app/api/v1/endpoints/md_transactions.py`: exact existing MD guard on every route, setup lock at creation, reuse existing journal creation. No new posting implementation.
5. Existing `md_accounting.py` service/endpoints and SQL triggers remain authoritative for posting, stale versions, opening confirmation, periods, immutability, audits, reconciliation and reports.
6. `frontend/src/components/accounting/BankReview.jsx`: statement evidence, exact candidate matches, deliberate record action and reconciliation. Cash excluded. `MoneyReports.jsx`: displays backend totals and authenticated exports. `format.js`: display only.
7. `frontend/src/pages/MDAccounting.jsx`: existing tools, entered through Advanced Accounting. Supports direct draft opening and warns before abandoning unsaved advanced edits on return.

Navigation remains `/md-accounting`; no old bookmark breaks. Only the label changes to Company Money. Existing ledger responses gain the voucher `kind` so Bank Review can exclude opening lines from candidate matches.

## Review invariants

- A collection credits an existing receivable/control; borrowing/capital credits liability/equity; liability payment debits liability; transfer moves only bank/cash. None becomes new revenue/expense automatically.
- Party is required except own-account transfers. Active, different accounts and category sections are validated server-side. A preview writes nothing; creation saves only DRAFT. Posting is a separate existing versioned command.
- Reports include all posted history for cumulative balances, including inactive accounts; selected P&L range affects only period income/expense.
- Posting and bank matching are separate transactions. Failed matching after successful posting warns explicitly and retains the posted record. Never retry creation as match recovery.
- Categories do not establish tax eligibility or source recognition. Multi-line/tax/accrual adjustments remain Advanced Accounting. No automatic bank feed or operational-to-ledger sync.
- MD identity configuration and all existing access/database controls remain in force. No new public table access.

## Verification

Local backend: `TEST_POSTGRES_ADMIN_URL` pointed only to the loopback development PostgreSQL administrator; `python -m pytest tests -q`: **255 passed**, none skipped. Includes 14 new business-action checks, existing real PostgreSQL migration/workflow/immutability/access checks. One existing Starlette/AnyIO deprecation warning.

Browser checks use Chromium and simulated APIs, never production credentials. `npm run test:md-everyday` covers payment, collection, transfer, preview no write, failed-refresh retention, posted-record controls, CSV import, matching, reconciliation, failed automatic match recovery and mobile width. Existing Advanced Accounting, Staff and Travel workflows remain required. Lint/build results and deployment evidence are recorded below after execution.

## Deployment and recovery

Application-only change: deploy tested source through the existing Vercel-linked `main` branch. Production remains `erp.destinlane.in`, designated MD user ID 1. Preserve prior READY deployment `dpl_HTJWFZFx1QWt6ugKxJEh3NquPGkZ` / source `4f4c407f179f49b2054de74090a743750672444d` as application rollback. No schema downgrade, seed or financial table rewrite is involved. A deployment rollback must retain all user-created vouchers and references.

Verify source SHA/READY status, public domain/bundle, anonymous denial on new endpoints and existing accounting endpoints, and CI. Production financial records must not be fabricated for tests. Actual MD sign-in, genuine openings and complete bank statements remain business acceptance. Prior protected snapshot is not an offsite/restore-tested backup; see the previous release record.

Local final validation: **10 browser cases passed** across Staff (7), Travel (1), Advanced Accounting (1) and Company Money (1). The Company Money case also verifies direct draft handoff into Advanced, posting there, and refreshing the acknowledged status/version on return. Frontend lint passed with existing warnings; production build passed with the existing large-bundle warning. No dependency installation or reusable environment configuration change was needed.

## Verified production release

Application source `2f2338b618cf1c4a7e27e3bc5c8ce768f0731cc3` pushed to `main`. Vercel production deployment `dpl_4ASDhWoqD6vXB6i46XZRXsWyzPCT` is **READY** and the project's production target, serving `https://erp.destinlane.in` (HTTP 200). Live JavaScript contains Company Money, Money Out, Money In, Bank Review and Advanced Accounting. Anonymous requests to new options/dashboard and existing auth/setup/travel APIs returned JSON 401. Read-only database verification found zero vouchers and zero travel claims; no business test data was created. No migration or MD configuration change was applied.

GitHub Actions runs were queued at the production check; they are not recorded as passed. Local validation above completed independently. Actual authorised MD browser sign-in and real opening/bank records remain business acceptance; live checks used public/read-only provider operations and anonymous denial, not fabricated posted transactions. A follow-up documentation-only commit records this evidence and can trigger an equivalent application rebuild.
