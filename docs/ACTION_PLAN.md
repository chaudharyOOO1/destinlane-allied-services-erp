# Action plan

Current status (25 October 2026): see the [development and readiness ledger](engineering/DEVELOPMENT_20261025.md). The dated sections below describe earlier snapshots.

Updated: 18 October 2026. Baseline source: `d2fc92f`. Current work is local and has not been deployed.

## Direction

Improve the current Vercel/Supabase application. Use ERPNext/HRMS to study proven workflows, with licence review before code reuse. Pause Oracle/full ERPNext deployment. Keep production operating while changes are validated separately.

| Phase | What | How | Why | Acceptance gate | Status |
|---|---|---|---|---|---|
| 1 | Establish baseline and diagnose saves | Inventory code/tests, trace mutation and read paths, reproduce errors | Avoid duplicate work and unsupported completion claims | Evidence register and reproducible defects | Initial code/test audit recorded; broader browser/live audit pending |
| 2 | Reliable saving | Fix confirmed failures, preserve input, handle concurrency and uncertain outcomes | Prevent data loss and misleading results | Create/edit/reload/error/retry checks for affected workflows | SAVE-001 fixed locally; further save audit pending |
| 3 | Personnel and access | Verify hierarchy, DASE/DASS codes, simple staff/login creation and role restrictions | Dependable onboarding with controlled authority | Realistic role-by-role acceptance and account lifecycle | Existing implementation; acceptance pending |
| 4 | Operations | Verify masters, joining/documents/approvals, deployments, rosters and attendance | Reliable inputs to money calculations | Employee moves from onboarding to approved attendance | Representative backend workflow exists; full acceptance pending |
| 5 | Payroll and accounts | Agree expected calculations; verify salary, payslips, invoices, GST, receipts, expenses and compliance | Explainable reconciled amounts | Complete monthly example reconciles | Existing code; business acceptance pending |
| 6 | Release and recovery | Focused tests, separate test data, restorable backups and small releases | Recoverable production changes | Acceptance, restore evidence and deployment checks | Not signed off |

Documentation and reviewer/handover safeguards apply to every phase; they are part of completion, not a later activity.

## Mapping to the original 22 steps

| Original steps | Current disposition |
|---|---|
| 1 company; 2 permissions; 3 clients; 4 sites; 5 contracts | Implementations and module tests exist; verify actual business configuration and UI workflows |
| 6 employee; 7 staff | Current first implementation focus; saving, account provisioning and real role acceptance remain |
| 8 recruitment; 9 joining; 10 documents; 11 approvals | Backend workflow tests exist; private storage and real operator acceptance remain |
| 12 deployments; 13 attendance; 14 mobile | Deployment/attendance tests exist; physical GPS, camera, device and mobile acceptance remain |
| 15 payroll; 16 payslips; 17 invoices; 18 accounts | Representative integration covers salary/PDF/invoice, not full monthly accounting acceptance |
| 19 compliance; 20 dashboards; 21 reports/notifications | Existing implementation must be verified against agreed business examples |
| 22 full verification | Outstanding; no production-ready claim |

## Explicit exclusions for now

Full rewrite, broad visual redesign, hosting migration, unused ERPNext modules, staff branch creation (cancelled), and general expense-request development before accounts. Travel Expenses is now explicitly authorised as an additional focused segment. New dashboards follow trustworthy underlying data.

## Next handover checkpoint

Continue SAVE-002 (employee draft write followed by dependent reads), then test personnel account lifecycle and permissions. Update the audit with evidence before expanding scope. Missing real-world failure details are useful but do not block independent local investigation.

## Added scope — Travel Expenses

Authorised after the first saving/documentation batch. Implement staff-owned travel claims with receipts, HR/Management/IT approval and Accounts/Management/IT payment recording. Independent review, versioned changes, audit and exactly-once accounting posting protect the workflow. See the functional specification, user guide and release handover through the documentation index. This does not complete the broader accounts phase.

## Added scope — MD bookkeeping and accounting

User authorised deployment and a separate accounting area for DestinLane Administrator (ADMIN-001), including all company-current-account bookkeeping. Chosen basis: INR, accrual double-entry, April–March. Scope includes chart/bank setup, confirmed openings, versioned drafts/immutable posting, reversals, period locks, bank CSV matching/reconciliation, general ledger, trial balance, P&L, balance sheet, audit and exports. Actual opening figures/bank completeness and statutory accountant review remain required. This does not complete every statutory/accounting automation item in phase 5.

## Professional workspace delivery — 19 October 2026

The user requested a professional dashboard across the ERP and removal of dummy/play-card behavior. This delivery standardises shared navigation, light presentation, source-backed overviews, real invoice actions, save/reload recovery and module loading. It does not mark every operational/payroll/compliance/production-readiness gate above complete. See [workspace functional scope](functional/PROFESSIONAL_WORKSPACE.md), [operator guide](user-guides/ERP_WORKSPACE.md) and [release evidence](engineering/PROFESSIONAL_ERP_RELEASE.md). Official logo placement is implemented, with the original downloadable asset still required.
