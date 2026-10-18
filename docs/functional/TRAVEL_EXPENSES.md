# Travel Expenses — functional specification

Status: implemented locally; migration and production release pending. User decisions: HR can approve; Management can record reimbursements. This adds travel reimbursement claims; it does not implement general personal expenses or branch creation.

## Purpose and permissions

Internal business users request reimbursement for completed business travel. Deployed Employee (`STAFF` backend enum) and external Client accounts have no access to this office module.

| Capability | Default access | Boundary |
|---|---|---|
| View/create/edit own claims | IT Super Admin, Management, legacy Administrator, HR, Operations, Accounts, Supervisor | Backend requester ID comes from login; edits/receipt uploads/submission are owner-only |
| View all claims | Users with approval or payment permission | Ordinary staff cannot access another person's claim/receipts/history |
| Approve/reject | IT Super Admin, Management, HR | Submitted claims only; no self-review; rejection requires remarks |
| Record reimbursement | IT Super Admin, Management, Accounts | Approved claims only; no self-payment; full amount only |

Individual permissions can deny supported actions. Unsupported grants do not bypass role boundaries. Keys: `travel_expenses.view/create/edit/approve/pay`. The new `pay` action is unsupported for all other modules. User Management displays it explicitly. Legacy `ADMIN` remains a limited administrator rather than receiving Management's approval/payment authority automatically.

## Claim data and validation

- Server-issued reference `TRAVEL000001` onward, requester account, business purpose, origin/destination, travel start/end, optional existing active company branch, INR currency.
- One to 100 item rows: expense date, Transport/Lodging/Meals/Other category, description, positive amount with at most two decimal places, optional bill/ticket number.
- Every item date is inside the trip dates; end cannot precede start. Drafts may describe future travel, but reimbursement submission requires the trip to have ended in the Indian business date.
- Total is calculated on the server using Decimal; browser totals/status/requester IDs are not accepted as authoritative inputs. Supported total is at most INR 9,999,999,999.99.
- Submission requires at least one receipt or a nonblank explanation of unavailable receipts. Approval remains a human assessment; an explanation does not establish receipt verification.
- An optional branch is a company branch, not permission to create a branch or attribute costs to an arbitrary client.

## Lifecycle

| From | Action | To | Required actor/conditions |
|---|---|---|---|
| New | Save draft | DRAFT | Authenticated eligible requester |
| DRAFT/REJECTED | Edit | DRAFT | Owner, current version |
| DRAFT/REJECTED | Attach receipt | Same state | Owner, current version |
| DRAFT/REJECTED | Submit | SUBMITTED | Owner, ended travel, receipts or explanation |
| SUBMITTED | Approve | APPROVED | Different authorised reviewer |
| SUBMITTED | Reject | REJECTED | Different authorised reviewer, remarks |
| APPROVED | Record reimbursement | PAID | Different authorised payer; valid date/reference |

Submitted/approved/paid details cannot be edited. Rejected claims retain their ID, receipts and history; correction and resubmission keep prior rejection remarks in the audit. There is no automatic self-approval exception, including for Management/IT. Another eligible person must handle their claim. No deletion or receipt removal is provided in this initial version; uploaded evidence remains retained.

## Receipts and privacy

PDF/JPEG/PNG only, up to 3 MiB each, maximum ten per claim. File signatures, size and same-claim SHA-256 duplicates are checked server-side; filenames are sanitised. Storage bucket `travel-expense-receipts` is private. Browser roles are denied direct table access and storage access. Receipt reads require claim access and a 60-second signed link; metadata responses omit storage paths. Treat a signed link as sensitive until expiry.

Upload and submission share the claim row lock, so an upload cannot attach after another transaction submits. A failed metadata write attempts cleanup only after confirming that no metadata was committed. If database confirmation is unavailable, retain the private object for reconciliation. No antivirus scanning or cross-claim duplicate/fraud detection is claimed.

## Accounting and payment

Recording reimbursement documents a payment already made; it does not initiate a bank transfer. Require a payment reference and payment date on/after approval (India date), not in the future. Only the complete approved amount is supported; no advances, partial payments or currency conversion.

Payment locks the claim, checks its version/status, inserts one `expenses` record with category `TRAVEL`, and stores that expense UUID, payer, date/reference, PAID state and audit in the same transaction. Failures roll back both accounting and claim changes. Concurrent or repeated payment attempts cannot post the same claim twice. The resulting expense is visible to existing Accounts and Management expense/P&L reads.

Expenses are recognised at recorded reimbursement in this initial workflow. Approval alone does not post an expense/liability. No GST input credit, tax breakup or bookkeeping/bank ledger entry is inferred automatically; those need a separate accounting-policy change. Do not manually duplicate the same paid claim through the generic expense endpoint.

## APIs and source map

Base `/api/v1/erp/travel-expenses`:

- GET base: own claims by default; `scope=all` requires approval/payment access; optional status filter. Latest 200 matching claims with `has_more` flag.
- POST base / PUT `/{id}`: create/update; PUT includes current version.
- GET `/{id}`: record, receipts and ordered history.
- POST `/{id}/submit`, `/decision`, `/pay`: lifecycle actions with version.
- POST `/{id}/receipts`: multipart file + version; GET `/{id}/receipts/{receipt_id}/sign`: short-lived viewing URL.
- GET `/options`: active branch choices.

Sources: `backend/app/models/travel_expense.py`, `schemas/travel_expense.py`, `api/v1/endpoints/travel_expenses.py`, `services/travel_storage.py`; permission catalog and request mapping in `api/permissions.py` and `api/deps.py`; UI `frontend/src/pages/TravelExpenses.jsx`.

All mutations return confirmed current record/version; UI retains it independently of list refresh. Server validation errors retain unsaved form input. A lost mutation response remains uncertain: no automatic retries, check existing record first. Before uploads/submission, save pending detail edits.

## Verification and limits

Backend `tests/test_travel_expenses.py` covers ownership/role restrictions, HR review, self-action denial, rejection/correction, stale versions, dates/amounts, malformed/duplicate receipts, private access and storage failures. Disposable PostgreSQL coverage checks two concurrent reimbursement attempts, exactly one accounting posting, Management payment and denied browser table access. Storage calls are mocked in file tests; actual Supabase bucket/provisioning remains a release check.

`frontend/tests/travel-expenses.browser.test.mjs` exercises a real browser against a simulated API: failed directory refresh after creation, receipt upload, submission, HR rejection/correction/resubmission/approval, Accounts payment and mobile overflow. Existing Staff Master browser checks protect the earlier saving fix.
