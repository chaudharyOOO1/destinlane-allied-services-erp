# Professional ERP workspace — functional specification

19 October 2026. Goal: one consistent business interface, genuine source records, working navigation/actions and clear recovery. This is an application change, with no schema reset, seed or change to issued personnel codes.

## Workspace and permissions

`/erp` and `/dashboard` show the same Business overview; existing bookmarks remain valid. `/owner-executive` retains the Management permission gate and shows Management overview over the same source-section contract. Navigation/search share `frontend/src/config/navigation.js`; AccessContext's server permission snapshot and role list control visibility. Search is module navigation, not an assertion that every stored record is indexed. No inactive notification bell, fabricated LIVE indicator, persona switch or unsupported quick action is shown.

The shell uses the authenticated name/role and company profile. Mobile navigation and search support keyboard focus, Escape, focus return and body scroll locking. Primary buttons preserve true foreground/background colours; no global `.text-white` or `.bg-slate-900` override may corrupt modules. Shared tables, filters, panels, dialogs and drawers use a restrained light interface. Navy/gold identity and the logo integration are described in [branding](../engineering/BRANDING.md).

## Source-owned overview

`GET /api/v1/erp/dashboard` requires existing `dashboard.view` and its office-role gate. The Management overview source requires `owner.view` and Management/IT role. Each independently permitted source contributes a section with `status=ready|restricted|error`. Restricted/error sections have no zero metrics. Source queries use separate savepoints so one database error does not hide successful sections.

- Workforce: persisted employee/staff totals and active counts; each source requires its own view permission. No assumed administrator identity or fake growth.
- Deployment: active sites, today's scheduled/completed shifts and the next seven days; requires Sites and Rosters access. Up to six scheduled rows show real employee/site/date.
- Attendance: today's recorded statuses, open check-ins and review queue. When Rosters is permitted, missing attendance is scheduled non-cancelled shifts without a linked attendance row. No record means zero recorded attendance, never 98% or assumed presence.
- Billing: current-month issued invoice value/count/output GST and all-period invoice face value not marked paid. Draft, cancelled and future invoices are excluded. Financial values are server Decimal strings. Recent rows are latest issued invoices, up to six, across periods.
- Compliance: pending/due/overdue corporate records and, only with Employee access, expiring/expired employee documents. Up to six overdue/next-30-day reminders.

The current operational schema has **no receipts/allocation ledger**, so actual collections and an allocated outstanding balance are explicitly unavailable. A PAID flag is not used as proof of cash received. Unpaid invoice face values do not deduct partial payments. Output GST minus approved/reconciled ITC is an operational estimate, not an established statutory payment due. ITC is queried only with Finance access. No dashboard query accesses MD journal tables. Company Money remains the separate identity-bound posted books.

The old Management revenue/profit formula (gross invoicing, float arithmetic and repeated payroll joins) is retired. The API now returns the same permission-scoped section contract. It does not claim final profit from operational registers.

## Working actions and record integrity

Obsolete unmounted demo views and their random-ID/timer-save forms are removed. Overview links open the actual masters, rosters, attendance and finance workflows. Invoice creation uses `POST /erp/billing/generate`, and saved invoices are read from the new narrow `GET /erp/billing/invoices` using Billing permission; Finance access is not required just to view Billing. Invoice generation uses the existing verified-attendance/rate policy and creates persisted drafts. The UI warns that the existing 18%/regional GST policy needs review before issue. No local-only Mark Paid control remains. Printing uses the actual company/invoice details, not invented terms or digital-verification claims.

Confirmed saves are acknowledged before optional reads. Employee draft/intimation/submission/approval/document/status, approver setup, recruitment changes, roster cancellation/save, attendance correction/review and payroll actions preserve success if a follow-up list cannot refresh. The issued response/version is retained where available; warnings direct the user to refresh or reopen. Existing Staff, Travel and MD safeguards remain. Unknown mutation response outcomes still require inspection before retrying; no general write retry/idempotency system was added.

A temporary non-401 failure during account checking retains the token but blocks protected content behind a Retry account check screen. A genuine 401 follows existing sign-out handling. A delayed response from an old token cannot revoke a newer login; both account-state handling and the HTTP interceptor guard the credential identity. Unexpected page-render/chunk failures show a reload/recovery screen. Pages load on demand so opening one module does not load the full ERP bundle.

## Acceptance and limits

Check permission-scoped navigation and sources; no synthetic trends/sparklines/percentages; real zero versus unavailable; partial and total request failures; real invoice persistence; confirmed-save/read-failure recovery; mobile width/focus; actual user/company identity; posted accounting and role restrictions. Browser tests use simulated APIs; PostgreSQL tests use disposable databases. Neither replaces authorised production business acceptance or accountant review.

The supplied logo is visible in chat; original downloadable bytes were not made available to the workspace. The shared placements and configurable approved-asset URL are implemented; using the actual artwork remains blocked until a usable file/URL is supplied. No replacement trademark has been invented.
