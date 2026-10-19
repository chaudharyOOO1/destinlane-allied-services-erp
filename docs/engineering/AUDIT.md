# Baseline audit and defect register

Audit date: 18 October 2026. Starting revision: `d2fc92f`. Scope: initial repository inspection, staff save failure reproduction, backend regressions and disposable PostgreSQL workflows. No new live health check, production write or deployment is claimed.

## Evidence and coverage

| Area | Evidence inspected/executed | What this establishes | Remaining gap |
|---|---|---|---|
| Access and company | `test_account_access.py`, `test_authentication.py`, `test_company_setup.py`; auth/access contexts and hierarchy docs | Local regression coverage exists | Real operator acceptance and deployed configuration |
| Client/site/contract masters | `test_client_master.py`, `test_site_contract_master.py` | Backend regression coverage exists | Browser save/error/reload and business-data checks |
| Employees/joining/docs | `test_employee_master.py`, `employee_workflow.py`, `Employees.jsx` | Versioned drafts, validation and backend tests exist | SAVE-002; real Supabase storage and operator workflow |
| Staff | `test_internal_staff.py`, PostgreSQL workflow, new browser regression | Local creation, permissions and save feedback evidence | Real Supabase provisioning and broader UI lifecycle checks |
| Roster/attendance | `test_roster_deployment.py`, `test_attendance_master.py`, `test_geofence.py` | Local automated coverage exists | Physical GPS/camera/device behaviour and field acceptance |
| Payroll/payslip/invoice | `test_postgres_workflow.py` | Representative backend workflow with checked amounts and repeatability | Business-approved monthly reconciliation and full accounts |
| Production/recovery | Historical release documentation only in this batch | No fresh live readiness conclusion | Full backup restore, live review and production acceptance |

## Defects and investigation queue

### SAVE-001 — Successful staff write reported as failure after read outage

Status: fixed locally; not deployed.

Trigger: POST/PUT succeeds, then GET of saved record fails. Previously the form remained in creation mode after a successful create, retained the temporary password and displayed a generic failure. Directory-refresh failure also displayed an action-failure message despite a successful write.

Cause: mutation and follow-up reads shared the same failure handler; the mutation response was discarded before refreshing the form.

Correction: `StaffMaster.jsx` applies the returned record/ID/version first, clears the password, then refreshes. Read failures produce saved/refresh warnings. The same handler is used by details, access and status writes. No database migration is needed.

Evidence: browser tests simulate successful writes followed by detail/list outages and compare creation/edit state, messages, password clearing and acknowledged versions. Rejected writes retain input and do not show success. API is simulated: this is frontend evidence, not production provisioning evidence.

### SAVE-002 — Employee draft confirmation depends on unrelated reads

Status: code-path finding, not yet reproduced/fixed.

`Employees.jsx` draft save PATCH is followed by `openRecord` (joining/documents/history) and `load` (directory/options/approvals/categories/compliance). Any later failure reaches the generic action handler despite a possibly committed draft. Next: reproduce read outages with a browser test, then retain authoritative response/version and isolate refresh errors.

### SAVE-003 — Uncertain mutation outcome after lost response

Status: investigation pending.

Axios uses a 20-second timeout. A timeout does not prove the server rolled back. Audit create/payment workflows before introducing retry behaviour; assess idempotency and record lookup. No general idempotency guarantee has been added.

### ACCOUNT-001 — Cross-service provisioning and compensation

Status: investigation pending.

Review Supabase Auth provisioning and database commit/rollback as separate service operations. Existing local mocks/password fallback do not establish production provisioning or cleanup of orphaned external accounts.

### DOC-001 — Historical documentation and setup mismatch

Status: partially addressed.

Root README previously claimed an APEX production-ready demo with machine-local screenshot paths. It is archived and clearly labelled historical. Added a current index, plan, functional/user guide, review contract and handover. Older AGENTS/backend architecture text and historical release limitations still need reconciliation. Root `pyproject.toml` requires Python 3.13 while regression CI uses 3.12; duplicate CI definitions remain. Do not expand this save fix into a toolchain rewrite.

## Verification log

- Initial backend run: **215 passed, 3 skipped** (PostgreSQL integration variable absent); one Starlette/AnyIO deprecation warning.
- Enabled the existing local PostgreSQL 17 cluster and ran the integration file: **4 passed** (three previously skipped workflows plus one route assertion).
- New browser regression after SAVE-001: **7 passed** with simulated API; covers create/detail failure, list failure, edit/detail failure, access/status refresh failure, rejected save and normal save.
- Initial frontend lint/build: passed with existing React lint warnings and a bundle-size warning. Final results are appended below after verification.

Full business acceptance, real external provisioning/storage, deployed behaviour and restore testing remain unverified. Passing local tests does not close those gaps.

### Final local verification

- Complete backend run with local PostgreSQL enabled: **218 passed, zero skipped**; one existing Starlette/AnyIO deprecation warning.
- Frontend lint and production build: passed; existing React lint warnings and bundle-size warning remain.
- Browser regression runner: **7 passed**, including access/status post-write refresh failures. The runner starts and cleans up its own local server; a corresponding CI step is added but remote CI has not run in this batch.
- No database migration, production data write, Git push or deployment performed.
- Regression sensitivity: against the original Staff Master source, the same browser suite produced **5 expected failures and 2 passes**. Restored the corrected source immediately afterward. This confirms the checks detect the refresh-handling defect.

## Added segment — TRAVEL-001

User authorised Travel Expenses after the initial save audit, with HR approval and Management reimbursement. New claim/receipt/history models, versioned/scoped APIs, private receipt storage, office-role permissions and a Finance navigation page are implemented locally. Payment records an already-made reimbursement and posts the existing expense exactly once per claim within the database transaction. No bank transfer or automatic tax credit is included.

Evidence so far: 15 focused backend tests passed with disposable PostgreSQL enabled, including concurrent payment attempts (one success, one conflict), no duplicate accounting entry, Management reimbursement, private browser grants, rejection/resubmission, permission/ownership checks and receipt validation. A real-browser journey against a simulated API passed creation with list-refresh failure, attachment, HR rejection/correction/approval, Accounts payment and mobile layout.

Required release migration: `20261018120000_travel_expenses.sql` / Alembic `0008_travel_expenses`. No production migration, push or deployment performed. Actual Supabase private storage and deployed role acceptance remain unverified. See [travel release handover](TRAVEL_EXPENSES_RELEASE.md).

### TRAVEL-001 final verification

- Full backend suite with PostgreSQL enabled: **233 passed, zero skipped**; one existing Starlette/AnyIO deprecation warning.
- Travel browser journey: **1 passed** (multi-role lifecycle, receipts, failed-refresh recovery and mobile layout; simulated API).
- Staff save browser suite: **7 passed** after the shared runner change.
- Frontend lint/build: passed with existing warnings; no new Travel Expenses lint warning. Documentation links, shell syntax and diff whitespace checks passed.
- An initial full regression failed only because its migration-head assertion was hard-coded to 0007. Updated it to assert the actual current Alembic head, then reran the full suite successfully; no business assertions were removed.
- Production remains unchanged. Remote CI and real Supabase storage acceptance have not been executed by this task.

## Added segment — MD accounting / bookkeeping

The user designated DestinLane Administrator (ADMIN-001) and delegated the basis choice. Implemented INR accrual double-entry with April–March starting policy, designated-user-only access, chart/bank setup, opening confirmation, drafts/immutable posted vouchers, reversals, period locks, bank CSV matching/reconciliation, detailed ledgers, trial balance/P&L/balance sheet, audit and CSV exports. Scope and statutory/source-reconciliation limits are explicit in the functional/user/release guides.

Final local checks: **241 backend tests passed with PostgreSQL enabled**, plus **nine browser cases** (seven staff save, one multi-role travel journey, one MD bookkeeping journey); frontend lint/build and documentation/whitespace checks passed. Lint retains existing warnings and two async-effect warnings in the MD load hooks; build retains the bundle-size warning. A test-only UTC/India midnight mismatch was corrected by freezing the contract examples to the same India business date; production rate protections were unchanged.

Production preparation: verified designated account ID 1 and prior READY deployment dpl_Fr8Jnp5AEnNGLnUe4cuN5TcBJDMx (d2fc92f). Created protected in-database pre-release snapshot `erp_release_backup_20261018`: 60 public tables / 264 rows, row-digest checked, browser schema usage denied. Provider backup API returned no backups; this snapshot is not off-site disaster recovery and has not been restore-tested. Applied only new forward migrations 20261018120000 and 20261018150000 and registered them in Supabase history. Production MD binding configured separately before application release. No financial vouchers or fabricated business claims were created.

Deployment confirmation is recorded separately after production promotion. Actual MD sign-in, bank statement completeness, real private receipt upload, reconciled opening figures and statutory accountant acceptance remain business checks.

Production promotion confirmed: app source 8ffe9b5, Vercel dpl_A9gHvxrsaKAGgr3oigUV843d9sR7 READY. Domain/front-end labels and anonymous API denial verified; private bucket/table grants and zero fabricated financial/business records confirmed. See RELEASE_20261018.md for rollback, acceptance limits and CI follow-up.

## Company Money — 19 October 2026

Approved simplification implemented over the existing MD ledger: everyday Money Out/In/Transfer forms, read-only preview, saved draft then explicit posting, Bank Review, business summaries and Advanced Accounting. Functional/user guides, source map and review invariants updated. No schema/dependency change. Exact amounts, classification, date/opening guards and the MD identity boundary are backend-owned. Operational records and bank imports do not silently recognise revenue/expenses.

Evidence: 255 backend tests passed with local PostgreSQL integrations enabled (none skipped); 10 Chromium browser cases passed using simulated APIs; lint/build passed with existing warnings. Browser regression includes failed draft-list refresh, failed matching after successful posting, mobile widths and return from Advanced with a refreshed voucher version/status. Live deployment evidence belongs in `EVERYDAY_MONEY_RELEASE.md`; local checks alone are not live acceptance. Genuine openings, source classifications, complete statements and statutory review remain business/accountant tasks. Unknown mutation-response outcomes still require inspection before retry; no general idempotency layer was added.

## Professional workspace — 19 October 2026

Replaced the default and Management overviews with permission-scoped real source sections. Removed hardcoded administrator identity, synthetic growth/sparklines, 98% attendance fallback, inert LIVE/notification controls, unused demo pages and random-ID/timer-save forms. Shared navigation/search and light controls now support mobile keyboard/focus behavior. Invoice generation/listing use mounted backend routes and persisted drafts; local-only Mark Paid is removed. Employee and other affected saves preserve confirmed responses across follow-up read failures.

Read-only review found and corrected two additional issues: a paid invoice status was incorrectly overridden by PENDING clearance, and a stale account-check failure could revoke a newer successful login. Browser regressions cover both. Management no longer presents gross invoicing/duplicated payroll joins as final P&L; the contract is now source sections with permission/error states. MD posted accounting remains separate.

Official logo art is visible in chat but no original downloadable file/URL was exposed to the workspace; shared placements use a navy/gold text fallback pending the asset. Do not claim the supplied image is deployed. See professional release handover for final validation, production evidence, API compatibility and remaining business/accounting acceptance.
