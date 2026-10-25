# Development ledger — 25 October 2026

This is a development/pre-production project for a new company. Empty client, employee, attendance and invoice tables are expected. Oracle is abandoned; Vercel and Supabase remain the target. Gmail integration is deferred. Do not interpret a successful build as full business readiness.

## Implemented in this batch

- AUD-01: explicit commits on the identified legacy writes; durable-save regressions use new database sessions. Account creation/update commands now validate dates, amounts and tax modes; some other legacy payloads still use field whitelists.
- AUD-02: effective-dated employee wage API, private history table and office UI; missing attendance-date coverage blocks calculation. End-to-end test uses the API instead of direct wage SQL.
- AUD-03: finalised run/slip recalculation and hold protection, monthly transaction serialization. Employee approval/payment/adjustment lifecycle remains incomplete.
- AUD-04: canonical employee salary list and owned server PDF. Only approved/disbursed records are visible.
- AUD-05: profile field mapping, attendance dates, authenticated private verified documents. The active 404 route no longer imports Base44; obsolete Base44 login/settings screens and SDK dependencies were removed. Employee build no longer replaces public source assets. Physical camera/GPS/device acceptance still required.
- AUD-06: Decimal payroll money and valid draft due dates. State/registration-based statutory policy and GST place-of-supply review remain open.
- AUD-07: reproducible generated-data local dump/restore drill. Production offsite recovery remains unverified; Supabase is the backend, not evidence of a recoverable backup.
- AUD-08: manual invoice insertion supplies issue_date on both fresh and deployed schemas; no reliance on the differing database default.
- AUD-09 recruitment: verified candidate creates one linked joining draft atomically; retries reuse the file; final joining approval updates recruitment. Receipt/partial-payment allocation remains open.
- AUD-10: collapsed account creation/custom permissions, staged atomic permission save, revision conflicts and server protections. Progressive per-module access UI can be improved further.
- AUD-11: shared account sign-in lockout, constant-cost unknown-account verification and Vercel response headers. Cookie-based session hardening and network-wide rate limiting remain separate work.
- AUD-12: contributor guide replaced with current routes/workflow constraints; new functional/user guides and this completion ledger.
- Management clarification: internal staff pay is proposed by branch/month and requires Management approval every month. No automatic salary from active staff. Revisions, decision notes, payment references and audit history are retained. No salary/capital amounts were inserted in production.

## Review map

| Concern | Primary code / evidence |
| --- | --- |
| Durable writes | accounts_master.py, erp_controls.py, test_save_durability.py |
| Wage coverage and protected payroll | payroll.py, 0010_employee_wages, PayrollWages.jsx |
| Staff monthly pay | staff_payroll.py, 0012_staff_monthly_pay, StaffMonthlyPay.jsx |
| Login lockout | auth.py, User security fields, 0011_login_lockout |
| Private employee data | mobile_sync.py, backendClient.js, EmployeeProfile.jsx, SalaryCard.jsx |
| Candidate linking | recruitment.py, employee_workflow.py endpoint/service, Employees.jsx |
| Atomic permissions | users.py, UserManagement.jsx |
| Recovery drill | scripts/verify_local_restore.py (strictly loopback/generated data) |

All new financial/security tables have RLS enabled with browser-role grants revoked. Existing MD access restrictions are retained. New migrations are additive and deliberately refuse destructive downgrades. Recovery favours a reviewed forward fix; revert application code only when schema compatibility is verified. Do not remove wage/pay audit history.

## Still required before complete business readiness

1. Configure and review employee statutory rules when deployment states, PF/ESIC registrations and employment terms are known. Confirm staff deductions for actual proposals. No active deployed employees exist currently.
2. Complete canonical employee payroll approval, recorded payment and reviewed adjustment workflows.
3. Complete receipt/part-payment allocation, GST registration/place-of-supply handling and invoice issuance controls. Do not derive collections from PAID labels.
4. Establish encrypted offsite backups of database and private object storage with retention and prove a production-data restore in an isolated destination. Confirm Supabase plan backup availability separately.
5. Physically test phone camera, GPS boundary, overnight shifts and device changes; complete operator acceptance of real business workflows.
6. Maintain accurate release evidence and a human review of these changes before treating the ERP as production ready.

Validation and live deployment evidence are appended below after execution. No whole-ERP completion claim is made while these remain open.

## Validation and database release evidence

- Entire backend suite before the final typed account-command refinement: 274 passed. Focused final save/payroll/recruitment/access/security regressions: 10 passed, including invalid account amounts. All use generated data; disposable PostgreSQL applies migrations twice.
- Office frontend lint/build passed (existing lint warnings remain). New Chromium tests verify staged permission saves and staff-pay proposal creation; module save/billing suite passes.
- Employee portal passed a clean lockfile install, lint and production build. Main JS reduced from approximately 821 kB to 439 kB after removing active Base44/unused provider imports. Camera/GPS hardware acceptance is not implied.
- Local custom-format PostgreSQL dump/restore passed for 67 application tables, row counts, RLS metadata and a generated company marker. Both disposable databases and temporary dump were removed.
- Live additive migrations: 20261025100000 employee_wages, 20261025110000 login_lockout, 20261025120000 staff_monthly_pay.
- Before migration, 69 live application tables / 296 rows were copied and digest-verified in protected schema erp_release_backup_20261025. Browser schema usage is denied. This in-project snapshot is not an offsite backup.
- New wage/pay/audit tables have RLS enabled and anon/authenticated SELECT denied. No production business salaries or accounting entries were inserted.

All seven office Chromium suites passed: 24 cases in total (dashboard, staff saves, travel, MD books, everyday money, module saves and payroll/access). Application deployment evidence will be recorded after verification.

### Release follow-up

GitHub's npm 10 clean install exposed missing optional chokidar/readdirp records in the npm 11-generated employee lockfile. Regenerated with npm 10; both installer versions must accept it. The live employee JavaScript URL also returned HTML because the service retained the /employee prefix when resolving static assets. Added an explicit employee asset rewrite before the SPA fallback; verify actual JavaScript/CSS MIME and content on the live domain after deployment. These findings are not covered by an HTTP-200 page check.

### Native employee build follow-up

- Web stays under /employee and uses same-origin API requests. Installed apps use a local hash router, relative bundled assets and the explicit HTTPS ERP API. VITE_ERP_API_BASE_URL can select another HTTPS backend for a native build; no credentials/query tokens belong in this public setting.
- Capacitor core, Android, CLI and geolocation are now declared/locked dependencies. Native builds request precise location through the native plugin; generated Android projects declare camera/fine/coarse location permissions.
- Added a checked-in Capacitor config and reproducible Android-generation script. The legacy application identifier is retained for upgrade compatibility; the display name/artifact uses DestinLane.
- Three runtime-configuration tests passed. Native-origin CORS and authentication tests passed (26 focused backend cases). CORS permits the two explicit native local origins; authentication/ownership checks still return 401 without a session.
- Generated an isolated Android project, synchronized plugins and verified permission declarations and relative packaged asset paths. Removed the generated project after verification. APK compilation/physical-device behaviour are separate checks.
- Removed broken favicon/PWA-manifest links pending actual branded assets. Management will supply the approved PNG; do not recreate the logo.
- User Management displays configured permissions for inactive accounts, allowing access planning without incorrectly showing every grant as denied.
- scripts/verify_public_routes.py now checks actual JS/CSS content types and rejects SPA HTML at asset URLs, as well as anonymous API access.

The d79fef4 release passed all five GitHub workflows, including the Android build. Its employee JavaScript is served as application/javascript on the live domain. The native follow-up requires its own matching deployment/CI checks.

### Verified native code release

Code commit de44151dc80dd3b639e55400ed11fe38387097b2 is live as Vercel deployment dpl_AYicHPJvsuBQRf9xspRfHACRu7on (READY). All five matching GitHub workflows passed, including full PostgreSQL regression and Android APK compilation. Native-origin preflights return 200 for the configured native origins; an unknown origin returns 400. The live public employee login rendered at a 390×844 viewport without JavaScript errors or Base44 requests; no login was submitted. Public JS/CSS MIME and anonymous protected-route checks passed. Real-device acceptance is still pending.

The employee README now contains the actual web/native commands instead of obsolete Base44 setup instructions. Local Vite development proxies /api to the backend, with an optional EMPLOYEE_DEV_API_ORIGIN override, so a handover does not require changing production API configuration.

### Save-state and handover follow-up

The staff-pay mutation response is applied to the visible list before a follow-up read. A simulated 503 after saving leaves the new DRAFT/version/net amount visible. The payroll month is disabled while child financial writes run; manual refresh buttons reload the correct child register. Wage reads use a generation guard so an older read cannot replace a newly saved wage. Account validation errors are rendered as text, including structured FastAPI validation lists.

The strengthened Chromium staff-pay test delays the write response, checks the month lock, then forces a list-refresh outage and verifies the saved result remains. Both payroll/access browser cases pass, and office lint/build pass. The local employee development proxy was verified against a generated local HTTP server, including API path and dummy Authorization forwarding; no production data was used.
