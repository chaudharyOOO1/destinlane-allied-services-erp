# Employee management

Employee records represent workforce deployed to clients. Company operators and management are held separately in Internal Staff Master.

The employee page contains four sections: Employee Master, Employee Creation, Employee Compliance Documents and Employee Reports. Payroll remains a separate module.

## Creation and approval

Intimation requires employee name, father's name, Aadhaar, mobile number, an active client and an active company branch. Submission atomically creates an intimation, employee and joining file. PostgreSQL issues the permanent `E-DAS-0070` onward ID immediately. Codes cannot be changed. Unique Aadhaar and mobile constraints prevent duplicate files.

Joining files support partial saves, resumption, version conflict detection and returned corrections. Details include personal and employment information, identity, emergency contact, verified bank/branch/IFSC, nominee, UAN/ESIC, gunman information and uniform issue/EMI. Dates, Aadhaar checksum, PAN, phone and bank formats are validated on the server. Final submission requires an adult employee, required details and valid document uploads. Approved IFSC, bank and branch must match the imported bank master; browser verification flags are never trusted.

Office operators, including Operations and Accounts, can receive explicit Employee access and approval permissions from administrators; their existing default permissions are unchanged. Deployed employee and client accounts cannot access these office records.

Internal submissions snapshot the configured approval chain. Each step is restricted to its assigned approver; the Owner can intervene. Only the last step activates the employee. Return requires remarks and preserves the employee ID. Owner submissions can activate directly after all required documents are verified. Submitted files cannot be edited or have uploads replaced until returned. Approval setup is Owner-only. Inactive or unavailable approvers block progression.

Activation creates a workforce deployment profile without creating an ERP login. Pending joining files cannot be deployed, punch attendance or log into the employee mobile endpoint. Recruitment and older direct workforce/document-write endpoints cannot bypass this workflow.

## Documents and compliance

Files upload to private Supabase storage. PDF, JPEG, PNG and WEBP are accepted up to 3 MiB, with signature checks, SHA-256 duplicate checks, storage/metadata compensation and 60-second signed viewing links. Uploads and review actions are recorded in employee history. Review requires Employee approval permission; submitted-file review is restricted to the assigned approver or Owner.

Required files: photograph, Aadhaar, PAN, Form 11, ESIC form, bank passbook (or cancelled cheque), police verification and medical fitness. Gunmen also require a gun licence. Documents must be valid and verified before activation. Critical documents require expiry dates. Medical fitness validity is capped at one year from the issue date. Older files are retained when renewing documents.

Missing, rejected or expired police verification/medical fitness, plus gun licence for gunmen, block deployment. Compliance refresh benches approved active employees, never activates drafts and never reactivates inactive or terminated employees. Manual bench decisions are preserved. Deployment and mobile attendance independently check current compliance, without depending on a stale stored bench flag. Alerts show police verification within 45 days and gun licences within 60 days.

## Directory, reports and operational setup

Directory and exports mask Aadhaar and omit bank, storage paths and identity numbers. Full joining files are restricted to the employee module's authorised office roles. Employee code checking distinguishes a registered ID from a merely valid format.

Reports provide filtered master, actual daily/monthly-range attendance (present/absence/night/OT/late/exception fields), and 30/60-day compliance reports. Downloads support XLSX, PDF and CSV. Export permission is required; formula-like spreadsheet values are escaped. Unrecorded attendance is not counted as absence.

Before operational use, the Owner must configure company branches, create active clients, import an approved IFSC bank dataset and assign joining approvers. No sample employees, clients, banks or documents are added to production.

Automated tests use an isolated database and cover identity creation, duplicate rollback, partial saves, stale versions, assignment, file locking, Owner activation, returns, immutable approval snapshots, unverified document blocking, bank verification, expiry benching, validation, permission routing and private exports. Frontend build/lint and authenticated production read-only checks supplement these tests. Actual employee document upload and complete production joining require real company records and have not been fabricated for testing.
