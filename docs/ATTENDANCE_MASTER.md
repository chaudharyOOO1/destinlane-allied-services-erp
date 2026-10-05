# DestinLane Attendance Master

Attendance belongs to deployed workforce employees, separate from internal office staff. The ERP page has the register, date/site filters, CSV reports, punch review, assigned correction requests, owner-only shift rules and employee PIN/device administration.

## Setup and attendance

1. Complete company/client/site/approved employee setup and schedule the deployment.
2. Owner sets the actual start time, regular duty hours and grace period for each site's DAY, NIGHT or GENERAL shift. No invented start time is used when a rule is absent.
3. Owner enables an employee's attendance PIN (8–12 digits). Employees sign in with their registered phone and PIN, without Google login. Five failed PIN attempts lock access for 15 minutes; PIN/device resets revoke sessions. Old phone-only sessions are rejected.
4. Each explicit check-in or check-out requires GPS and a fresh selfie. Server checks employee ownership, roster status, Indian roster date, joining/compliance/site/contract eligibility for check-in, configured geofence and reported accuracy (at most 100 metres and within site radius). Check-in opens two hours before shift start. Server time determines worked hours.
5. First accepted punch binds the employee device across roster days. Owner reset requires a reason and no unresolved open shift. This is an application device identifier; native hardware attestation and protection against a compromised phone or forged GPS are not implemented.
6. Selfies are backend-uploaded privately, bound to employee/kind, limited to 3 MiB, signature-checked, hashed and usable once within ten minutes. Reviewers request signed viewing links valid for 60 seconds. Existing eight storage objects are retained privately, without attaching them to new attendance.
7. Checkout finds an open overnight shift before today's new roster and retains its starting date. Regular/OT hours use the check-in rule snapshot. Deployment becomes COMPLETED and attendance PENDING_REVIEW. Shifts exceeding 24 hours require correction. GPS and human review are separate flags.
8. Office users with attendance approval access review completed punches and overtime with remarks. Only VERIFIED, completed present/late attendance enters payroll/billing. Approved manual corrections can enter those calculations but are never labelled GPS verified.

## Corrections and audit

Direct PATCH edits are closed. Office users with attendance.edit submit a current/past non-cancelled roster, expected attendance version (zero for missing attendance), corrected present/late times or absent/leave status, reason and active assigned approver. Positive times start on the roster day, include a timezone, cannot be future and span at most 24 hours. Hours and lateness are computed; the shift policy is snapshotted for review.

One pending request per roster is enforced. Attendance remains unchanged until approval. Only the assigned approver or owner may decide; non-owner submitters cannot self-approve. Stale requests cannot overwrite a newer punch. Rejection retains remarks and allows a fresh request. Accepted corrections preserve original punch/selfie evidence and before/after history. Attendance is locked once included in a non-draft/non-cancelled payroll run.

Permission routing uses attendance.view/edit/approve/export for corresponding actions. Owner clearance additionally protects shift rules, PINs and device resets. Six new tables have RLS and revoked public/client grants. Backend uses existing server-only database/storage credentials. Employee endpoints omit identity documents, bank details, salary amounts, device hashes and private selfie paths.

Canonical employee API paths are `/api/v1/mobile/login`, `/selfie`, `/me`, `/me/attendance`, `/me/salary` and `/punch`; old double-mobile routes remain compatibility aliases with the same authorization and controls.

## Verification and remaining setup

Isolated SQL tests cover punches, date/ownership/geofence/accuracy boundaries, no retry toggling, selfie ownership/expiry/reuse, devices, overnight shifts, compliance, hours/rule snapshots, approvals/corrections, payroll locks, PIN attempts/revocation, direct edit closure and permissions. Frontend and employee production builds and lint are checked. Live verification uses read-only and malformed/negative requests; no fake business records are inserted.

Actual site rules, PIN enrollment, phone camera/GPS permissions and a full physical-device check await real business setup. Recruitment remains deferred. Payroll statutory calculations and the complete invoice lifecycle belong to following modules.
