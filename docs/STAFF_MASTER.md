# Internal staff master

Internal company staff run the business: MD, partner, operations heads, branch heads, accounts and field officers. Employees remain the workforce deployed to client sites. Staff records use a separate table and do not appear in employee, deployment, attendance or payroll lists until dedicated integrations are implemented.

The live route is `/staff`; API routes start `/api/v1/erp/internal-staff`. Codes start at `S-DAS-0010`, are allocated transactionally, unique and immutable. The checker distinguishes valid format from an actual registered record. Phone numbers are normalized and unique. Records are retained on termination. Version checks reject stale edits and all record changes create audit snapshots.

## Positions and access

Business designation (such as MD) and management level are separate from ERP account roles. Regions support Uttarakhand, Uttar Pradesh, Delhi NCR (including Noida), and all regions. Staff select active branch codes configured in Company Profile & Docs. Headquarters staff can leave branch blank. Branch accounting and expense coordination require the later accounts stages.

Owner/Super Admin/Admin have staff module access by default. HR can view, with create/edit/approve individually granted by administrators. Operations/Accounts require explicit staff permissions. Employees/clients/supervisors cannot access this master even if granted its module flags. Private bank and statutory details are omitted from directory responses.

The proposed ERP role is a recommendation; saving a profile never grants access. The Manage Login link prefills User Management with staff code as Login ID. Account creation remains administrator-only, and creating Owner/Super Admin/Admin accounts remains Owner-only. Staff status and login activation are separate controls. Inactive or terminated staff login accounts must also be disabled in User Management.

## Staff approval

Save a draft, enter department/designation/joining date, then submit. Owner submissions activate immediately. Other submissions wait for approval. Owner can assign the staff approver to an active internal office account with `staff.view` and `staff.approve` permissions. Each submission stores its assigned approver; changing the rule affects future submissions. The assigned approver or Owner can approve or return with remarks. A returned draft can be corrected and resubmitted. No role, superuser flag or unassigned approval permission bypasses the assignment. Disabled approvers cannot act; new submissions fail clearly if the configured approver becomes unavailable.

Status changes require administrator access, edit permission and a reason. Terminated records are read-only. Automatic payroll, staff document upload, branch expense ledgers and approval routing for other modules are separate stages.

## Storage and verification

Four tables (`internal_staff`, code counter, history, approval settings) use RLS and deny direct anon/authenticated access. Backend authentication and current per-account permissions enforce access. PostgreSQL protects staff codes with an immutable-code trigger. No credentials or personal staff records are seeded by the migration.
