# ERP account access controls

Business designation and account role remain separate. The Owner creates administrator accounts; all other administrative changes obey account hierarchy. Account access is constrained by the backend module role catalog, and explicit permissions grant or deny supported actions. Navigation uses the same effective permissions. Upper management uses Owner or Super Admin roles; legal company changes after submission remain Owner-only.

New accounts and administrator password resets require a password change before ERP access. Password changes, resets and account disabling invalidate earlier ERP sessions. Account deletion disables the account and retains history. Account actions and permission changes are audited without passwords. Existing accounts retain credentials and do not require a forced reset.

Approved S-DAS staff records can be linked to accounts through User Management. Staff approval assignment is configured independently in Staff Master. Client accounts see only their linked company.

Validation: account, client, staff, company and authentication regression suites; frontend production build and lint. Live checks verify authentication, permission catalog, master endpoints and anonymous rejection.

## Travel Expenses

Internal office roles can submit their own travel claims. HR, Management and IT Super Admin can approve another person's submitted claim; Accounts, Management and IT Super Admin can record another person's approved reimbursement. The `travel_expenses` module has view/create/edit/approve/pay keys; pay is unsupported for other modules. Individual deny rules remain effective. Deployed Employee and Client accounts are excluded. See the [travel specification](functional/TRAVEL_EXPENSES.md) for exact role/state/ownership boundaries.

## MD accounting exception

The new bookkeeping workspace is restricted to the server-configured designated MD user ID, regardless of other Management or IT roles. It cannot be delegated through ordinary permission toggles. Unconfigured environments deny all access. See [MD accounting](functional/MD_ACCOUNTING.md).
