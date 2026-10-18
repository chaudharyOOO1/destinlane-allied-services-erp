# Saving and Staff Master — functional specification

Status: existing backend contract plus local SAVE-001 frontend correction. Production acceptance remains pending. Read alongside [Staff Master](../STAFF_MASTER.md) and [hierarchy](../LOGIN_HIERARCHY.md).

## Business rules

- Staff are internal business operators; deployed employees are separate workforce records.
- IT Super Admin, Management and HR may create staff, subject to backend permissions and target-role protections. Ordinary staff cannot create staff even with a manually supplied allow flag.
- New staff creation collects name, mobile, email, department, designation, optional existing branch/joining date/employment type/notes, departmental role, permissions and temporary password.
- Creation issues a DASS ID and linked ERP login together. The temporary password requires first-sign-in change. Existing legacy IDs remain valid and immutable.
- Departmental roles and individual permissions define working capacity. Staff cannot grant authority beyond supported/backend-authorised controls.
- Updates use the current record version. A stale write is rejected; do not overwrite a newer record silently.
- Inactive/terminated staff lose login access; reactivation does not automatically re-enable the login. Terminated records remain retained/read-only.
- Branch creation and expense requests are excluded from this phase.

## Source and API ownership

| Layer | Source | Responsibility |
|---|---|---|
| UI | `frontend/src/pages/StaffMaster.jsx` | Form, feedback, password clearing, confirmed-write state |
| HTTP client | `frontend/src/api/axios.js` | API base, token, timeout and authentication errors |
| Endpoints | `backend/app/api/v1/endpoints/internal_staff.py` | Create/read/update, permissions, versions, status and account links |
| Schemas | `backend/app/schemas/internal_staff.py` | Input validation |
| Account integration | `backend/app/api/v1/endpoints/users.py` | Account provisioning and management rules |

Base API path: `/api/v1/erp/internal-staff`. POST base creates; PUT `/{id}` edits; POST/PUT `/{id}/login` creates/updates access; POST `/{id}/status` changes lifecycle state. Successful mutations return the record, ID, version and account summary. GET `/{id}` additionally supplies effective permissions for authorised administrators.

## Save outcome contract

| Outcome | Required UI behaviour |
|---|---|
| Mutation succeeds and reads succeed | Apply returned ID/version, clear temporary password, show success, refresh |
| Mutation succeeds but detail read fails | Retain confirmed record and version; show saved + refresh warning; do not return to creation mode |
| Mutation succeeds but directory read fails | Keep confirmed record; show success and stale-directory warning |
| Server rejects mutation | Show validation/conflict message; retain input; do not show success |
| Mutation times out/response is lost | Outcome may be unknown; no automatic retry; user checks directory/existing record before creating again |
| Record version conflicts | Reopen latest record and reapply intended changes; do not force overwrite |

The current fix covers confirmed success followed by failed reads. General timeout recovery, idempotency and cross-service account-provisioning compensation remain separate audit items.

## Acceptance evidence

`frontend/tests/staff-save.browser.test.mjs` uses a real browser with simulated API responses. It checks create/detail-refresh failure, directory-refresh failure, edit/detail-refresh failure, access/status refresh failures, rejection/input retention and normal saving. It checks no duplicate create, ID retention, cleared temporary password and use of acknowledged version for subsequent edits.

Backend rules are exercised by `backend/tests/test_internal_staff.py`; disposable PostgreSQL account/working-permission coverage is in `backend/tests/test_postgres_workflow.py`. These do not prove actual production Supabase provisioning or user acceptance.
