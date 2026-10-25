# Developer handover

Current status (25 October 2026): see the [development and readiness ledger](DEVELOPMENT_20261025.md). The dated sections below describe earlier snapshots.

Updated: 19 October 2026. Start with [action plan](../ACTION_PLAN.md) and [audit](AUDIT.md). No prior chat history is required to continue this work.

## Architecture and entry points

- `frontend/src/App.jsx`: routes. `context/AuthContext.jsx` authenticates; `AccessContext.jsx` controls navigation using server permissions. `api/axios.js` supplies tokens and a 20-second timeout. Backend checks remain authoritative.
- `backend/app/main.py`: FastAPI entry point. `api/v1/api.py` registers routers; endpoints, services, schemas and models own business rules.
- `backend/alembic/versions/`: versioned local bootstrap. `supabase/migrations/`: Supabase SQL history; inspect actual migration manifests before changing either path.
- `vercel.json`: frontend/backend/employee-app service routing. Production secrets are server-side deployment settings.
- `employee-app/`: separate mobile application; its full current behaviour is outside this first save correction.
- `frontend/src/utils/roleLabels.js` and `docs/LOGIN_HIERARCHY.md`: display names differ intentionally from stable backend enums. Do not rename database roles casually.

Keep existing DASE/DASS and legacy personnel codes immutable. Never reset counters or rewrite issued IDs during cleanup.

## Setup

Use the existing checkout; no worktree is needed. Check `git status --short` before editing and preserve existing work.

Backend: follow the first **Reproducible local database** section in `backend/README.md`, install `backend/requirements-dev.txt` in an isolated virtual environment, and use a new local PostgreSQL 17 database. Local browser roles `anon` and `authenticated` must exist for the security-policy migrations. Apply Alembic only to the intended new database. Never run the bootstrap or sample seeder against production.

Frontend: Node 22.12+ (CI Node 22; this local session Node 24), `npm ci` in `frontend`. For local development the default API is `http://localhost:8000/api/v1`; `VITE_API_BASE_URL` can override it. Start backend with `uvicorn app.main:app --host 127.0.0.1 --port 8000`, frontend with `npm run dev`. Use loopback endpoints for local checks, not public demo links.

See `.env.example` for names. Backend requires a strong `SECRET_KEY` and local `DATABASE_URL`. Real private uploads and account provisioning need Supabase settings including server-only `SUPABASE_SERVICE_ROLE_KEY`. Local password fallback is explicit development-only configuration, not a production fix. Never print environment values or commit `.env` files.

The current cloud workspace retains PostgreSQL tools under `/workspace/.onboarding/postgres/usr/lib/postgresql/17/bin` and a development cluster at `/workspace/.onboarding/pgdata`. Check readiness before starting it; its loopback-only startup is captured in the environment's existing onboarding instructions. These paths are convenience artifacts, not portable project dependencies.

## Verification

From `backend`, with the local virtual environment active:

```bash
python -m pytest tests -q
```

For complete PostgreSQL coverage, securely set `TEST_POSTGRES_ADMIN_URL` to a **local** administrator connection with CREATEDB. The test creates and removes uniquely named disposable databases; the URL must not point to production. Without this variable, three integration cases are skipped. Run only that group with:

```bash
python -m pytest tests/test_postgres_workflow.py -q
```

From `frontend`:

```bash
npm run lint
npm run test:staff-save
npm run test:travel-expenses
npm run test:md-accounting
npm run test:md-everyday
npm run build
```

The browser command requires Bash, curl and installed Chromium/Chrome. It discovers `chromium` or `google-chrome`, or accepts `BROWSER_EXECUTABLE_PATH`. It starts its own loopback Vite server on port 5179, runs browser tests against a simulated API, and stops that server on exit. Keep this port free. Tests reject non-loopback targets and require no real login credentials. They are not a replacement for real backend/provisioning checks.

`.github/workflows/erp-ci.yml` runs backend/PostgreSQL regression, frontend lint, browser regression and build. GitHub-hosted Ubuntu supplies Chrome; if a self-hosted runner is introduced, provision it explicitly. Several older workflows duplicate build checks; consolidation is a separate task. Branch protection/required reviews are not configured by these files.

## Current change: SAVE-001

Read `StaffMaster.jsx` in this order: `save`/`saveAccess`/`changeStatus` → `acceptSaved` → `show` and `load`. Mutation responses supply ID/version immediately. `acceptSaved` clears the password via `show`, then attempts detail/directory refreshes. Read failures warn without undoing confirmed state. Error and status messages are visible inside the open dialog.

No schema or backend changes are required. Revert the frontend commit/deployment to roll back this correction; no data restoration is needed. General mutation-timeout recovery is not solved.

## Release and recovery

The initial saving, Travel and MD accounting changes were deployed on 18 October; see the release record. Subsequent changes require their own deployment evidence. Before a future release, inspect the diff and checks, update the functional/user docs and audit, verify the deployment target and SHA, and use test records outside production. A deploy is separate from database migration. See `STAFF_MASTER_RELEASE.md` for historical migration context; its final limitation is historical, not a current live status check.

For schema changes, inspect the real environment and migration history, obtain a restorable backup, apply only unapplied forward migrations, and test rollback/compatibility. For application rollback, restore the prior deployment while retaining additive schema and issued IDs. Full database restore needs separate assessment of newer writes.

Verify health, authentication, authorised and denied actions, actual saves/reloads, and logs without exposing sensitive data. Do not create fabricated business identities in production to prove provisioning.

## Continue here

1. SAVE-002 and the affected employee workflow refresh paths are now corrected; see the professional workspace release. Preserve the new response/version and unknown-version recovery tests when extending the workflow.
2. Investigate uncertain mutation outcomes and Supabase Auth/PostgreSQL compensation. Do not add automatic retries without idempotency.
3. Extend staff lifecycle coverage to legacy-login activation, navigation/role acceptance, and real Supabase provisioning in a suitable test environment. Access/status post-write read failures already have browser coverage.
4. Expand the audit to other master save paths, then progress through the action-plan gates.

At every handoff record: defect/phase, changed entry points, commands/results, migration/deployment state, unresolved risks and the next concrete investigation. No credentials should be needed from chat; use secure environment bindings.

## Travel Expenses addition

Read [travel release handover](TRAVEL_EXPENSES_RELEASE.md) for source entry points, migration order, permission mapping, private receipts and accounting/recovery details. The shared browser runner is now `frontend/scripts/test-browser.sh`. Travel is an explicitly authorised addition; general expenses and the remaining save audit are still pending.

## MD bookkeeping addition

Read [MD accounting release handover](MD_ACCOUNTING_RELEASE.md) before editing. This module is identity-bound and must not inherit ordinary owner/super-admin bypasses. `MD_ACCOUNTING_USER_ID` unset denies access. The browser runner now also supports `npm run test:md-accounting`. Monetary truth comes from posted journal lines, not operational summary totals.

## Company Money simplification

See [everyday money handover](EVERYDAY_MONEY_RELEASE.md). Start at `MDWorkspace.jsx` → `md_transactions.py` routes/service → existing journal posting/report service. No database migration or new financial truth store. Keep the MD identity boundary, exact backend arithmetic and advanced journal controls. Business categories must not count collections/loans/transfers as revenue or expense.

## Professional ERP workspace

See [workspace release/handover](PROFESSIONAL_ERP_RELEASE.md) for the current navigation, scoped dashboard contracts, real billing endpoint, save recovery, lazy loading, removed demo paths and logo integration. Add `npm run test:dashboard` and `npm run test:module-workflows` to frontend verification. `/owner/executive-summary` now returns permission-scoped source sections, not the retired gross-invoice P&L estimate. The supplied official logo still needs a downloadable original file/URL; no original artwork bytes are committed.
