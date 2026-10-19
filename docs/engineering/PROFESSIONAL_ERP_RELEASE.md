# Professional workspace — release and handover

19 October 2026. User-approved scope: replace dummy/play-card presentation with a professional ERP workspace, working business actions and consistent company branding. The separate ₹1,00,000 personal contribution remains unrecorded; no financial data entry is part of this release.

## Source map and review order

1. `frontend/src/config/navigation.js` → `layouts/MainLayout.jsx` → `components/CommandPalette.jsx`: shared permission-filtered route catalogue, real identity, desktop/mobile navigation and keyboard behavior. No fake connectivity or inactive notification controls.
2. `pages/Dashboard.jsx` with `/erp` alias `ERPModules.jsx`; Management wrapper `OwnerExecutiveView.jsx`. Read `services/dashboard.py` before changing labels or metrics. No fabricated frontend totals.
3. Backend `api/v1/endpoints/dashboard.py`, `owner.py`, `api/deps.py`, `api/v1/api.py`: existing per-page gates, effective source permissions, section savepoints and read-only real sources. No MD bookkeeping queried. Financial values are strings; no inferred cash collections or final P&L.
4. `modals/GenerateInvoiceModal.jsx`, `pages/InvoicesView.jsx`, backend `endpoints/payroll.py` Billing invoice reader: actual generation/listing rather than local objects. Review existing attendance/rate/GST policy independently; this release does not certify that policy.
5. `pages/Employees.jsx`, `Personnel.jsx`, `Rosters.jsx`, `Attendance.jsx`, `PayrollView.jsx`: acknowledge mutations before follow-up reads. Existing Staff/Travel/MD paths retain their earlier regression coverage.
6. Shared Table/FilterBar/GlassCard/StatCard/StatusBadge/Modal/DetailDrawer and `index.css`: accessible light presentation and accurate content. Synthetic trends/sparklines removed; unrelated Tailwind utilities are not globally rewritten.
7. `context/AuthContext.jsx` / `components/ProtectedRoute.jsx`: retain token on temporary non-401 account-check outage, block content and offer retry; no automatic mutation retry. `App.jsx` lazy route imports plus WorkspaceErrorBoundary limit initial load and provide recovery.
8. `CompanyLogo.jsx`, `company-branding.css`, Login, invoice preview and [branding handover](BRANDING.md): shared approved-asset integration, text fallback, real company profile and isolated invoice printing.

Unreferenced demo ClientsView, SitesView, RosterView and AttendanceView, plus fake Guard/Client/Site/Roster/BulkAttendance modals, are deleted. Actual routed masters remain. No model, migration, role enum or issued ID was reset.

## API contracts

`GET /erp/dashboard` and Management `/owner/executive-summary` now return the sectioned contract documented in the functional specification. The old gross-invoice/duplicated-payroll Management P&L response is retired. No other repository consumer relied on that response. If an external integration consumed the legacy endpoint, update it to the sectioned contract; this is the API behavior change to review.

`GET /erp/billing/invoices` is a narrow Billing-permission read of persisted invoice/client details, without requiring Finance access or exposing its other registers. Draft generation continues through existing `POST /erp/billing/generate`. No new schema.

## Validation and release gates

Run backend from `backend` with the existing virtual environment and loopback `TEST_POSTGRES_ADMIN_URL`: `python -m pytest tests -q`. Disposable PostgreSQL tests check actual permission-source queries, India date boundaries, zero versus error and persisted invoice generation/listing.

From `frontend`: lint, `test:dashboard`, `test:module-workflows`, `test:staff-save`, `test:travel-expenses`, `test:md-accounting`, `test:md-everyday`, then build. All browser suites use simulated API/fictional records, not production credentials. Dashboard cases check source values, forbidden modules, zero/error/stale refresh, mobile navigation/focus and temporary account-check recovery. Module cases check employee/intimation acknowledgement and server-backed invoices.

Temporary separate branding/shell browser checks verified login pending/error recovery, mobile width/focus, actual light/dark contrast and a one-page A4 invoice print with no shell/actions. These are manual session evidence, not permanent CI tests; generated mock artifacts are outside the repository.

Do not describe queued CI as passed. Inspect source/deployment SHA and real domain after promotion. Do not fabricate production financial or personal records.

## Rollback and known limits

Application-only release; no SQL migration/configuration change is needed. Prior READY production deployment `dpl_B5eEDUHK6MW37MeG9YiSjVtSxbuU`, source `3a98532828ae270a53f331d88c44ee879fc75e73`, is the application rollback target. Retain all genuine records and issued references. Restoring an application does not restore a database; previous protected snapshots are not offsite/restore-tested backups.

Official logo artwork is visible in chat, but its original downloadable file/URL is unavailable to this environment. Shared placements and approved-asset configuration are ready; the shipped text wordmark must not be described as the supplied artwork. No replacement trademark was generated.

No complete statutory certification, collection allocation ledger, automatic operational-to-MD posting, general write-idempotency layer or exhaustive end-to-end business acceptance is claimed. Existing billing tax policy and payroll formulas require their own functional/accountant review. This work validates the workflows listed above and the shared presentation; preserve separate action-plan gates for the remaining business processes.

## Final local verification

Backend full regression: **261 passed, none skipped**, with disposable PostgreSQL integrations enabled against the loopback development cluster (124.02s). One existing Starlette/AnyIO deprecation warning. No production database was used for tests.

Frontend: **22 browser cases passed** — Dashboard/navigation/session recovery (6), module save/billing workflows (6), Staff saving (7), Travel (1), Advanced Accounting (1) and everyday MD bookkeeping (1). Lint passed with remaining existing warnings; production build passed with lazy page chunks and no large-chunk warning. Final entry is approximately 193 kB uncompressed versus the previous 659 kB. Desktop 1440px and mobile 390px overview screenshots were inspected; no horizontal page overflow. Separate mocked branding/shell checks inspected invoice printing, dialogs and contrast.

A read-only review found the mixed paid-marker and stale-session-response issues; both were corrected and have permanent browser regressions. All tracked changes passed `git diff --check`. Documentation, functional scope, user steps, API compatibility and review checklist accompany the source.
