# MD accounting release and handover

New revision `0009_md_accounting`, SQL `20261018150000_md_accounting.sql`, follows Travel revision 0008. Migrations are additive and seed only chart/configuration; no financial balances/vouchers are fabricated. Existing operational data is not reposted automatically.

## Access configuration

Production binding: `MD_ACCOUNTING_USER_ID=1` for the user-confirmed DestinLane Administrator / ADMIN-001. Set only server-side. Unset denies everyone. Changing roles or individual flags cannot delegate this workspace to another identity. Preview environments should remain unbound unless intentionally configured for a suitable test identity. No passwords/credential values belong in code, docs or release logs.

## Entry points and controls

- `models/md_accounting.py`, `schemas/md_accounting.py`: setup, chart, journals/lines, statements and audit.
- `services/md_accounting.py`: exact Decimal reports/ledger/reconciliation and posting rules. Do not reuse the old dashboard's float totals as accounting truth.
- `api/v1/endpoints/md_accounting.py`: MD identity guard; version checks; single setup-row lock serialises accounting mutations; posted-voucher immutability; atomic imports, matching and audit.
- `api/permissions.py`/`api/deps.py`: identity-aware effective keys and action mapping; owner bypass occurs only after the MD identity check.
- SQL triggers: protect posted header/lines and check balanced posting at commit. Browser roles have neither direct table privileges nor RLS policies granting access.
- `frontend/src/pages/MDAccounting.jsx`: Setup, Books, Bank reconciliation, Reports and Audit. Mutation response retained independently of refresh. Posted fields disabled; CSV templates/import and export use authenticated API.

Review monetary algorithms, sign conventions, date/closing rules, opening confirmation, reversal linkage and anti-duplication separately from UI appearance. Bank matching must use opposite statement/book sides, same account and exact amount. Reports exclude drafts and retain prior unclosed earnings in equity.

## Verification

Backend: local virtual environment, `TEST_POSTGRES_ADMIN_URL` to a local CREATEDB role, then `python -m pytest tests -q`. Focused: `tests/test_md_accounting.py`. PostgreSQL fixture applies migrations twice and drops its own disposable databases. Never target production.

Frontend: `npm run test:staff-save`, `npm run test:travel-expenses`, `npm run test:md-accounting`, lint and production build. Browser fixtures use simulated API and fictional data; no test credential is a production login. CI runs all suites; remote CI must be inspected after pushing.

Before deployment: inspect real migration history/target; preserve current deployment SHA; take a protected pre-release snapshot/recovery copy and inspect provider backup availability. Apply only unapplied Travel/MD SQL, then set the server MD binding and deploy the tested source. Verify actual schema/RLS/bucket privacy, deployment SHA/health, anonymous denial and frontend bundle. Do not fabricate production financial vouchers to test functionality. Actual MD sign-in, true opening figures and real complete bank statements remain business acceptance steps.

## Recovery and limits

Application rollback uses the previous deployment while retaining additive tables and issued references. Never delete/rewrite posted vouchers; use reversing/adjusting entries. Do not auto-delete or reset financial tables during rollback. Provider backups/off-site recovery require separate operational validation; a protected in-database snapshot is not a provider disaster-recovery backup.

This is an accountant-reviewed management bookkeeping foundation. It does not automate complete statutory statements/notes/comparatives, tax-policy determination/returns, bank feeds, source ERP-to-ledger migration, asset depreciation, payroll tax rules, multi-currency or annual closing. See functional/user guides for the exact scope. Before real financial use, obtain reconciled opening balances and review classifications/policy. No legal-compliance certification is claimed.

## Release preparation evidence

241 backend tests and nine browser cases passed; lint/build passed with the warnings recorded in the audit. Protected pre-release database snapshot: `erp_release_backup_20261018` (60 public tables / 264 rows, row digests checked, browser access denied). This is not an off-site/provider backup and was not restore-tested. Applied/registered only new migrations 20261018120000 and 20261018150000. MD server binding is user ID 1. No production financial vouchers or fake travel claims were created. Application deployment results are recorded separately after promotion.
