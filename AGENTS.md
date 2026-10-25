# DestinLane ERP contributor guide

## Current architecture

- `backend/`: FastAPI, SQLAlchemy, PostgreSQL. API registration: `app/api/v1/api.py`.
- `frontend/`: React office ERP, Vite. Routes: `src/App.jsx`.
- `employee-app/`: separate React employee portal at `/employee`; phone/PIN sessions use the ERP backend.
- Hosting: Vercel and Supabase. Oracle is abandoned. Gmail integration is deferred.
- Roles displayed to users: IT Super Admin, Management, HR, Staff, Employee. Stored role values are compatibility identifiers; see `frontend/src/utils/roleLabels.js`.
- Internal staff (`internal_staff`, DASS IDs) and deployed employees (`employees`, DASE IDs) are different populations. Never infer one from the other.

## Workflow rules

- Only Management, IT Super Admin and HR create staff and their ERP login. Temporary passwords require a change on first sign-in.
- Employee activation requires the joining/document approval workflow. Recruitment must not bypass it.
- Internal staff remuneration is proposed per branch/month and requires Management approval every month. Active staff records do not generate salary. Staff remuneration is separate from employee attendance payroll.
- Employee wage rates are effective-dated and independent of client billing rates. Never silently calculate worked attendance at zero wages.
- Approved/disbursed payroll cannot be recalculated. Correct through an explicit reviewed adjustment workflow.
- A saved invoice, salary proposal or payment reference is not proof of a bank transfer. Do not fabricate collections or automatically duplicate operational entries in the MD books.
- MD accounting is restricted to the configured individual account, even for other privileged users.
- The discussed ₹100,000 remains intended personal capital until actual contribution. Do not create that financial entry from conversation history.

## Development and review

1. Read the relevant current functional and user guides in `docs/` before changing a workflow.
2. Keep migrations additive. Add matching Alembic and Supabase SQL files; test fresh bootstrap and repeated upgrade. Retain history and audit records.
3. `get_db()` closes sessions; it does not commit. Every successful mutation must commit before acknowledging success. Validate whole commands before writes.
4. Treat mutation responses as authoritative. A follow-up read failure must not report a successful save as failed or leave a duplicate submission ready.
5. Enforce role and action permissions on the server. Navigation visibility alone is insufficient. Private file URLs must be short-lived and ownership-checked.
6. Preserve draft edits on failed saves; reject stale versions/revisions. Serialize conflicting financial writes. Use Decimal for money.
7. Use generated local data for tests, never production fake clients, employees, attendance or money. Empty live business tables are expected for this new company.
8. Do not expose tokens, passwords, database URLs or personal documents in output, commits or browser fixtures.
9. Record what changed, why, validation, deployment evidence, known gaps and recovery steps in `docs/engineering/`.

## Verification

Backend (from `backend/`):

```sh
TEST_POSTGRES_ADMIN_URL=postgresql+psycopg://agent@127.0.0.1:5432/postgres .venv/bin/python -m pytest tests -q
```

Use an isolated local PostgreSQL role with CREATEDB. The integration fixture creates/drops disposable databases. Never target production.

Office frontend (from `frontend/`): `npm run lint`, `npm run build`, and the browser suites declared in `package.json`. Browser suites require Chromium and use mocked APIs.

Employee portal (from `employee-app/`): `npm ci`, `npm run lint`, `npm run build`. Build emits `dist/` without replacing source assets in `public/`.

Local restore drill: `scripts/verify_local_restore.py`. It proves generated local dump/restore only. Production offsite backup retention and recovery require separate evidence.

## Scope and readiness

See `docs/engineering/DEVELOPMENT_20261025.md` for the current completion ledger. Historical documents describe earlier snapshots; they are not proof of present readiness. Statutory payroll, GST treatment, receipt allocation and real-device attendance require the validation explicitly listed there.
