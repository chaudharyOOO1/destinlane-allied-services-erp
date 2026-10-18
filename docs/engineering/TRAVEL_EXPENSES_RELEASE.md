# Travel Expenses — developer/release handover

Release preparation update: production forward migration applied with the MD accounting release. Application deployment is tracked in the release record; historical verification notes below describe local checks.

## Review map

1. `models/travel_expense.py` and `schemas/travel_expense.py`: amounts, dates, states and retained audit/evidence.
2. `api/permissions.py` and `api/deps.py`: new office module, HR approval, Accounts/Management payment, unsupported actions and route-to-permission mapping. UI permission editor includes the new module and pay column.
3. `api/v1/endpoints/travel_expenses.py`: requester scoping → version/row lock → validation → mutation → `finish`. Payment inserts the existing expense and updates claim/audit in one transaction. Receipt upload holds the same row lock as submission and confirms metadata before compensation.
4. `services/travel_storage.py`: backend-only private object access and signed links. Never add browser storage keys or public object URLs.
5. `frontend/src/pages/TravelExpenses.jsx`: authoritative response handling via `mutate`; independent list-refresh warning. Route, sidebar, command palette and AccessContext are connected.
6. Tests and guides: see the [functional specification](../functional/TRAVEL_EXPENSES.md) and [operator guide](../user-guides/TRAVEL_EXPENSES.md).

## Migrations

New local Alembic revision: `0008_travel_expenses`, after `0007_compact_personnel_ids`.
Supabase SQL: `supabase/migrations/20261018120000_travel_expenses.sql`.

This adds claim/receipt/history tables, restrictive browser grants/RLS, an existing-expenses FK, private receipt bucket and restrictive storage policy when Supabase storage exists. Plain PostgreSQL skips storage DDL; it is not evidence of a real Supabase bucket test. No existing staff/employee IDs, passwords or counters change.

For an existing production Supabase database: inspect migration history, take a restorable backup and apply only the new unapplied SQL through the existing migration process. Do not replay the local bootstrap. Confirm a pre-existing bucket is intended for this module before changing it to private; this migration enforces private access. Apply schema before serving the new code and verify grants for the backend connection role. Server-only Supabase settings are required for actual uploads/signing.

## Verification commands

From backend with its virtual environment and a local PostgreSQL admin URL configured:

```bash
python -m pytest tests/test_travel_expenses.py -q
python -m pytest tests -q
```

The PostgreSQL fixture creates/removes its own database and applies migrations twice. Without `TEST_POSTGRES_ADMIN_URL`, payment integration is explicitly skipped. Never point this at production.

From frontend:

```bash
npm run test:travel-expenses
npm run test:staff-save
npm run lint
npm run build
```

Browser commands use Bash/curl/Chrome and a self-managed loopback Vite server on port 5179, with simulated API responses. `scripts/test-browser.sh` supports the two named suites. CI runs both; remote CI results must be checked separately after a future push.

Before release, verify in a suitable test environment: actual private receipt upload/signing, staff/HR/Management/Accounts permissions, rejection/resubmission, concurrent payment attempts and Accounts expense/P&L totals. Confirm bank reimbursement policy and missing-receipt rules with the business. No automatic bank transfer, GST ITC, liability posting, partial payment, receipt deletion, advances or notification delivery is included.

## Recovery

Roll back application deployment if needed; retain additive tables, evidence, audit and posted expenses. Do not delete a paid claim or repost its expense. Database rollback is deliberately blocked by Alembic: financial/audit deletion needs a reviewed forward correction. Uncertain uploads may leave private orphan objects; reconcile against metadata before cleanup. A payment already made outside ERP must be reconciled against its reference before retrying.

## Results

Final local results: 233 backend tests passed with PostgreSQL enabled; the travel browser journey and seven Staff Master browser cases passed; lint/build passed with existing warnings. Documentation links, shell syntax and whitespace checks passed. Detailed evidence and limitations are in the audit register. This handover does not claim deployed acceptance.

Production application deployment is verified in the [release record](RELEASE_20261018.md). Real staff receipt acceptance remains a business check.
