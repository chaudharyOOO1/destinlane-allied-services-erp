# Company profile and legal documents

Open **Company Profile & Docs** in the ERP navigation (`/company`).

- The confirmed company name is seeded; unprovided legal identifiers, dates,
  addresses and contact details stay blank.
- OWNER, SUPER_ADMIN and ADMIN can prepare and submit a draft.
- After submission, only the OWNER can change the profile or upload more files.
  SUPER_ADMIN privileges do not bypass this submission lock.
- HR, OPERATIONS and ACCOUNTS can view the internal profile and current documents.
  STAFF, CLIENT and field SUPERVISOR accounts are excluded. Per-account
  `company.view` permission denials are enforced by the API as well.
- Submission requires the actual incorporation/registration date. Registration
  formats and GSTIN/PAN consistency are checked; this does not verify issuance
  against government records.
- COI, MOA, AOA, GST, PAN, TAN, Udyam, PF, ESIC, PSARA, labour registration and
  other legal records accept PDF/JPG/PNG files up to 3 MB each.
- Files live in a private `company-legal-documents` bucket. Supabase browser roles
  cannot read/write this bucket or the company tables directly. ERP authorization
  precedes a signed download link that expires after 60 seconds.
- Uploaded files are immutable. Only the OWNER can archive a record. Archived
  files remain available to the OWNER; staff cannot access them.
- Every profile save records an actor, version and snapshot. A stale editor receives
  a conflict instead of overwriting a newer save. Saved branch codes remain fixed;
  closing a branch uses its inactive flag.
- Invoice headers and salary-slip company names use the saved company master.
  The financial-year preference is stored here; applying it to calculations belongs
  to the later payroll, billing and accounting stages.

Database migrations for this stage match the applied Supabase migration versions.
Authentication/permission/persistence/upload checks are in
`backend/tests/test_company_setup.py` and `backend/tests/test_authentication.py`.
