# ERP account access controls

Business designation and account role remain separate. The Owner creates administrator accounts; all other administrative changes obey account hierarchy. Account access is constrained by the backend module role catalog, and explicit permissions grant or deny supported actions. Navigation uses the same effective permissions. Upper management uses Owner or Super Admin roles; legal company changes after submission remain Owner-only.

New accounts and administrator password resets require a password change before ERP access. Password changes, resets and account disabling invalidate earlier ERP sessions. Account deletion disables the account and retains history. Account actions and permission changes are audited without passwords. Existing accounts retain credentials and do not require a forced reset.

Approved S-DAS staff records can be linked to accounts through User Management. Staff approval assignment is configured independently in Staff Master. Client accounts see only their linked company.

Validation: account, client, staff, company and authentication regression suites; frontend production build and lint. Live checks verify authentication, permission catalog, master endpoints and anonymous rejection.
