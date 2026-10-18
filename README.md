# DestinLane Allied Services ERP

Business ERP built with React/Vite, FastAPI and PostgreSQL. The existing production deployment uses Vercel and Supabase. ERPNext/Frappe HR are workflow references; their runtime is not a dependency of this application.

Start with the [documentation index](docs/README.md), [action plan and status](docs/ACTION_PLAN.md), [developer handover](docs/engineering/HANDOVER.md) and [contribution/review rules](CONTRIBUTING.md).

## Development

- Frontend: Node 22.12+ (CI uses Node 22), `cd frontend && npm ci && npm run dev`.
- Backend: Python 3.12 is the current regression CI baseline; see [backend setup](backend/README.md#reproducible-local-database) for a new local PostgreSQL 17 database, dependencies and migrations.
- Credentials belong in ignored local environment files or deployment settings. Never use production as a test database.
- See [verification commands and limitations](docs/engineering/HANDOVER.md#verification).

The root `pyproject.toml` Python requirement and historical backend instructions are not fully aligned; use the tested backend requirements/CI path until that discrepancy is resolved. See the audit for other known gaps.

The old APEX visual walkthrough is preserved as [historical material](docs/LEGACY_VISUAL_WALKTHROUGH.md); its production-ready claims and local image paths are not current evidence.
