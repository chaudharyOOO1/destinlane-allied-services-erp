# Using the DestinLane ERP workspace

Sign in with your existing login. The workspace displays your name, role and permitted modules; another account may see a different menu.

## Find your work

Use the left navigation, or **Search modules** / **Ctrl K** (Cmd K on Mac) to open a permitted module. On mobile, open the navigation button; Escape or Close returns to the page. **My Account** opens password/account settings; the account menu provides Sign out.

**Business overview** shows saved records available to your account. **Refresh overview** reloads the snapshot; its time is displayed at the bottom. There are no generated growth figures or assumed attendance percentages. Click a summary or **View records** to open its master. **Your workspaces** lists module purposes.

## Read the overview correctly

- Missing attendance means a scheduled shift without an attendance record. It is not automatically an absence or a present employee.
- Needs attention links to available attendance/compliance queues. “No listed exceptions” describes the loaded records only.
- Finance shows issued invoice values and GST on invoices. “Invoices not marked paid” is full invoice value based on status; it is not a part-payment-adjusted outstanding balance. Cash collections are unavailable until receipt allocation is implemented.
- GST differences are operational estimates. Use your accountant's reviewed tax records for filings/payments.
- Company Money remains the MD's posted bookkeeping, bank review and financial reporting workspace. Operational records are not silently posted into it.

A failed section says it could not load; it does not show zero. A failed refresh keeps the previous snapshot with a warning. Refresh or open the source module to retry.

## Create and review invoice drafts

Open **Billing & Invoices → Generate invoice drafts** if your account has creation permission. Select the client and billing month, then **Generate drafts**. The server uses completed verified attendance and effective site rates; existing month/site invoices are skipped. The result shows saved invoice references and amounts. A zero result means nothing new was generated; review attendance/rates and existing invoices before retrying.

The existing generator applies a fixed 18%/regional split policy. Review draft tax and invoice details with Accounts before issue. Invoice statuses show saved records; there is no screen-only payment button. View/print the recorded invoice with company identity. Record genuine bookkeeping/payment separately through the authorised workflows.

## Recover from interruptions

If a save succeeded but the list could not refresh, keep the reference and refresh/reopen it; do not create it again. If the save response was lost, check existing records before retrying. No automatic retry sends financial or personnel changes twice.

If the account check cannot connect, use **Retry account check**. A temporary server outage does not automatically discard your login. An expired/revoked session requires signing in again. If a workspace cannot open, use **Reload workspace** and check whether any pending save already succeeded.

The navy/gold company identity is shared across the sign-in screen, navigation and invoice printouts. The official logo file can be installed in those shared placements when its downloadable original is supplied.
