# Staff Master

Company staff run the business; employees are the workforce deployed to client sites. Staff records remain separate from employee deployment, attendance and payroll.

Owner and HR can create staff and manage their ERP access, subject to individual staff module permissions. Other roles cannot create or edit staff, even with an explicit allow flag. Only the Owner may assign administrator roles or manage administrator accounts through Staff Master.

At `/staff`, enter basic name, mobile, email, department, designation and optional joining date, existing branch and notes. Choose the departmental ERP role, a temporary password of at least 12 characters, and working permissions. One save creates an active staff record and linked ERP account. There is no employee diligence or staff approval step. Failure to provision an account rolls back the local record and code allocation. Existing legacy drafts can be activated and receive a login separately.

New staff IDs begin at `DASS0010`; new employee IDs begin at `DASE0070`. Existing `S-DAS-` and `E-DAS-` IDs are retained and remain valid, including existing login IDs. Counters continue rather than restarting. IDs are allocated by the backend, unique and immutable; a code check distinguishes valid format from an actual registered record.

Staff use their ID, registered mobile or email to sign in. Temporary passwords must be changed before accessing business modules. Role limits and individual permissions control actions and navigation; for example `employees.view` and `employees.create` allow employee entry. Ordinary Operations or Accounts staff cannot receive staff creation permissions. HR role holders may create staff as authorized by the business.

Owner and HR can adjust linked account role, permissions and enabled status. Changes revoke existing sessions. Marking a staff record inactive or terminated also disables its login and revokes sessions. Reactivating staff leaves the login disabled until it is explicitly enabled. Terminated records are retained and read-only. Linked login email and staff ID cannot be changed through staff editing; basic name/mobile changes synchronize to the account.

Version checks reject stale edits. Staff history and account audits record changes without storing plaintext passwords. Direct database access by anon/authenticated roles is denied through grants and RLS. Apply Alembic through `0007_compact_personnel_ids` for account links and new ID formats.

Branch creation and expense requests are deferred. Only assignment to an existing active company branch is included. Production Supabase account provisioning needs valid server-side Auth credentials; local cloud tests use the explicitly configured local password fallback or a mocked provisioning call, not production Supabase.
