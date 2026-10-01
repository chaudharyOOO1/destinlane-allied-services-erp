# DestinLane ERP — Unified Architecture & Security Review

## Target architecture

- One GitHub repository: `destinlane-allied-services-erp`
- One Vercel project using Vercel Services.
- Frontend service: `frontend/`
- FastAPI service: `backend/`
- Employee mobile web/PWA service: `employee-app/`
- One shared public domain with path routing.
- Supabase/PostgreSQL remains the system of record; database schema changes are tracked with Alembic migrations.

Vercel Services is intentionally used instead of separate Vercel projects so frontend, backend, and employee app deploy together and roll back together.

## Security fixes applied

1. Removed committed frontend demo account credentials and deleted `frontend/src/api/mockData.js`.
2. Production API URL is same-origin `/api/v1`; no hard-coded backend Vercel hostname remains in the frontend client.
3. Production FastAPI debug/docs are disabled by default.
4. JWT signing secret is now required from environment configuration rather than using a repository default.
5. Vercel/serverless database connections use `NullPool` to reduce managed PostgreSQL connection exhaustion.
6. Added security response headers.
7. Unknown backend API routes fail closed in the permission dependency.
8. Per-user permission overrides can explicitly deny permissions instead of being ignored for administrator roles.
9. Added administrator role-management hierarchy checks and self-disable/self-delete protection.
10. User creation, password reset, and password change synchronize passwords with Supabase Auth.
11. Local password verification is disabled by default and is available only through an explicit migration fallback flag.
12. Passwords exceeding bcrypt's 72-byte limit are rejected instead of silently truncated.
13. Employee login and attendance were moved behind the FastAPI mobile API instead of anonymous direct table access from the browser.
14. Employee selfie uploads now go through the backend and use server-side Supabase Storage credentials; mobile reads can return signed URLs.
15. Employee attendance retains GPS/geofence and device-binding checks.
16. Salary amounts are no longer displayed directly on the employee dashboard; the employee sees the salary-slip action.

## Database consistency

Alembic migrations now include:

- `0003_login_id.py` — administrator Login ID support.
- `0004_user_permissions.py` — per-user permission overrides.

The migrations are written to be safe against the corresponding objects already existing in the current Supabase database.

## Remaining hardening items

- The main ERP browser session still stores the application JWT in `localStorage`. This should be migrated to an HttpOnly, Secure, SameSite cookie session before treating the application as security-complete against XSS token theft.
- Phone-only employee login is intentionally retained because it is a stated product requirement. It is weaker than OTP/password/device-bound authentication; the backend therefore enforces active-employee status, short-lived mobile JWTs, GPS geofencing, and device binding for attendance.
- Existing legacy employee-app dependencies/files that are no longer used should be removed after a clean production build confirms there are no remaining imports.
- Production environment variables must be configured in the single Vercel project before deployment: `SECRET_KEY`, `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `ADMIN_SETUP_TOKEN`.

## Deployment acceptance checks

Before production is considered healthy:

1. Frontend loads from the root domain.
2. `/api/v1/auth/login` reaches the FastAPI service through the same origin.
3. `/health` returns a healthy response.
4. `/setup-admin` synchronizes the administrator with Supabase Auth.
5. Login works with the administrator Login ID.
6. A non-admin account cannot create or modify administrator accounts.
7. Explicit permission denial removes both UI access and API access.
8. Employee phone login returns only the matched active employee.
9. Employee attendance rejects missing GPS, out-of-geofence punches, and device mismatches.
10. Employee selfie uploads do not require the browser to hold a Supabase service credential.
