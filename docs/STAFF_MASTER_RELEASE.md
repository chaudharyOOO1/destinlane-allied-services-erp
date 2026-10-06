# Staff Master production release

Target: https://erp.destinlane.in (FastAPI/Vercel, Supabase PostgreSQL/Auth).

Validated locally: 218 backend tests including disposable PostgreSQL integration, frontend lint/build, and browser combined staff/login creation with mobile dialog.

## Required order

1. Identify the Vercel project serving this domain and the Supabase database attached to its production backend. Check deployment SHA and database migration history. Take a restorable backup using the production provider before schema changes.
2. Inspect the existing schema. This release adds `internal_staff.user_id`, and all authenticated backend requests query that link. The database migration must precede code promotion.
3. For the existing Supabase installation, apply only unapplied forward migrations through its normal migration process:
   - `20261006120000_runtime_schema_alignment.sql`, only if not already applied and its preconditions match the inspected schema.
   - `20261006130000_staff_login_link.sql`.
   - `20261006140000_compact_personnel_ids.sql`.
   Do not replay the new local-bootstrap baseline or historical SQL against a populated production database. Do not run Alembic's enterprise bootstrap over an existing Supabase-managed schema or stamp its history without assessment.
4. Confirm staff links/backfill, code checks accepting legacy and compact IDs, immutable-code triggers, uninterrupted counters, and denied direct anon/authenticated access. Inspect existing staff/account email consistency and duplicate identities before provisioning.
5. Promote the tested release commit to the production branch/deployment. Keep production `ALLOW_LOCAL_PASSWORD_FALLBACK` disabled; reuse the production `DATABASE_URL`, `SECRET_KEY`, `SUPABASE_URL`, and server-only `SUPABASE_SERVICE_ROLE_KEY`. Never put credentials into source or browser bundles.
6. Verify `/health`, actual deployment SHA, authenticated company/employee/staff reads, and rejection of anonymous requests. Verify Owner/HR creation permissions and other roles denied. Test actual Supabase provisioning with an authorized real staff onboarding (or a separately agreed test identity); do not fabricate business records in production. Verify first-password-change, employee permissions, role-based navigation, and session revocation.

## Rollback

Restore the prior Vercel deployment if application checks fail. Keep additive schema columns and issued IDs; old staff/employee IDs remain valid. Do not reset counters or rewrite issued IDs. Database restoration is a separate operational action requiring assessment of writes after the backup.

## Current limitation

At release preparation, this cloud's network proxy denied requests to `erp.destinlane.in` and `api.github.com`. Production Vercel/Supabase access has not been established. A Git push alone does not apply the production schema or prove a live deployment.
