# Security & Facility Management ERP - Backend API

A REST API built with **FastAPI**, **PostgreSQL**, **SQLAlchemy 2.0**, and **Alembic** for Security and Facility Management operations.

## Reproducible local database

Use Python 3.12+ and PostgreSQL 17 for the tested development workflow. From
`backend`, install dependencies with `pip install -r requirements-dev.txt`.

Create a **new, empty database** owned by your local backend role. As a local
database administrator, create the browser roles used by the security policies
once (Supabase already supplies these roles):

```sql
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
```

Supply `SECRET_KEY` through an ignored `.env` or the process environment, set
`DATABASE_URL` to that new database, then run from `backend`:

```bash
alembic upgrade head
alembic current
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The migration chain includes the missing enterprise baseline, followed by a
fixed manifest of the existing SQL migrations. Repeating `upgrade head` is a
no-op. New SQL migrations must be registered in a new Alembic revision; adding
a file does not alter an already-applied revision.

`create_tables.py` creates only ORM tables and is **not** a complete ERP bootstrap.
Do not stamp or replay the new baseline over an existing populated, unversioned
database. Existing Supabase environments must keep their migration history and
be assessed separately before applying changes. This setup does not migrate or
modify production data.

On PostgreSQL without Supabase Storage, database setup still succeeds; storage
DDL runs only when the actual `storage.buckets` and `storage.objects` tables
exist. Real private document uploads, selfies, signed viewing links and email
recovery require Supabase configuration. No substitute storage schema is created.

The bootstrap seeds no employees, bank records or credentials. Configure company
branches, active clients/sites, approved IFSC records, joining approvers and shift
rules through the ERP before using operational workflows. Local password fallback
is opt-in with `ALLOW_LOCAL_PASSWORD_FALLBACK=True` and is not a production default.

## Regression and integration validation

```bash
python -m pytest tests -q
```

For the PostgreSQL workflow test, set `TEST_POSTGRES_ADMIN_URL` securely in your
process environment to a **local** administrator connection with `CREATEDB` and
the two roles above, then run:

```bash
python -m pytest tests/test_postgres_workflow.py -q
```

The test creates a uniquely named disposable database, runs migrations twice,
checks ORM columns and browser-role restrictions, and exercises authenticated
HTTP requests for joining/document approval, deployment, approved manual
attendance, payroll, PDF payslip and invoice generation. It checks amounts and
repeatability and removes its own test database. Private object storage and the
attendance clock are stubbed; production Supabase and physical GPS/camera behavior
are not covered. Without `TEST_POSTGRES_ADMIN_URL`, that integration test is
explicitly skipped. ERP CI supplies PostgreSQL and runs it alongside regressions.

`GET /api/v1/erp/payroll` is the canonical salary-slip listing used by the payroll
screen. Legacy salary records remain available at `/api/v1/erp/payroll/salary-records`
and `/api/v1/erp/payroll/legacy-records`.

---

## 🏗️ Architecture Overview

The system models end-to-end security operations including User Management (RBAC), Client CRM, Site Shift Requirements, Guard Rostering, Attendance / Overtime Tracking, and Client Invoicing.

```
backend/
├── app/
│   ├── main.py                  # FastAPI application entrypoint & middleware
│   ├── core/                    # Core configuration, database engine, security
│   │   ├── config.py            # Pydantic Settings & environment variables
│   │   ├── database.py          # SQLAlchemy 2.0 engine, SessionLocal, get_db
│   │   └── security.py          # Password hashing (bcrypt) & JWT helpers
│   ├── models/                  # SQLAlchemy 2.0 ORM Models
│   │   ├── base.py              # Base model & timestamp mixins
│   │   ├── enums.py             # UserRole, GuardStatus, ShiftType, AttendanceStatus, InvoiceStatus
│   │   ├── user.py              # User entity (ADMIN, CLIENT, STAFF)
│   │   ├── client.py            # Client business details & GST
│   │   ├── site.py              # Client sites & shift requirements (JSON)
│   │   ├── guard.py             # GuardProfile (daily rate, badge number, status)
│   │   ├── roster.py            # ShiftRoster (Site, Guard, date, shift type)
│   │   ├── attendance.py        # Attendance (Check-in/out, status, overtime hours)
│   │   └── invoice.py           # Invoices (billing month, tax rate, total amount, status)
│   ├── schemas/                 # Pydantic v2 validation & response schemas
│   │   ├── user.py
│   │   ├── client.py
│   │   ├── site.py
│   │   ├── guard.py
│   │   ├── roster.py
│   │   ├── attendance.py
│   │   └── invoice.py
│   ├── crud/                    # Reusable CRUD & database operations
│   │   ├── base.py              # Generic CRUDBase class
│   │   ├── crud_user.py
│   │   ├── crud_client.py
│   │   ├── crud_site.py
│   │   ├── crud_guard.py
│   │   ├── crud_roster.py
│   │   ├── crud_attendance.py
│   │   └── crud_invoice.py
│   └── api/                     # API Routers
│       └── v1/
│           ├── api.py           # Aggregated v1 router
│           └── endpoints/       # Entity endpoints (CRUD & queries)
├── alembic/                     # Alembic migration environment
│   ├── env.py                   # Dynamic config & target metadata
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial_schema.py # Initial database migration
├── scripts/
│   └── seed_db.py               # Database seeder script
├── alembic.ini                  # Alembic CLI configuration
├── .env.example                 # Example environment variables
├── .env                         # Local environment settings
└── requirements.txt             # Python project dependencies
```

---

## 📋 Entity Specifications

| Entity | Description | Key Relationships |
| :--- | :--- | :--- |
| **User** | Authentication & roles (`ADMIN`, `CLIENT`, `STAFF`) | 1-to-1 with `GuardProfile`, 1-to-1 with `Client` |
| **Client** | Client enterprise profiles, contacts, billing & GST info | Has many `Site`, has many `Invoice` |
| **Site** | Guard deployment locations & shift requirements | Belongs to `Client`, has many `ShiftRoster` |
| **GuardProfile**| Security guard details, daily rate, badge number, status | Belongs to `User`, has many `ShiftRoster` |
| **ShiftRoster** | Scheduled guard shifts (`DAY` / `NIGHT`) by date & site | Belongs to `Site` & `GuardProfile`, 1-to-1 `Attendance` |
| **Attendance** | Check-in/out timestamps, status, overtime tracking | Belongs to `ShiftRoster` |
| **Invoice** | Monthly client billing, tax calculation, payment status | Belongs to `Client` |

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10+ (Python 3.13 supported)
- PostgreSQL database instance running locally or in Docker

### 2. Environment Setup

Create and activate a virtual environment:
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

Install dependencies:
```bash
pip install -r requirements.txt
```

### 3. Configure Database

Copy `.env.example` to `.env` (if not already done) and configure your PostgreSQL connection:
```ini
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=security_erp
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/security_erp
```

### 4. Run Alembic Database Migrations

Apply the initial schema migration:
```bash
alembic upgrade head
```

To create new migrations in the future after modifying SQLAlchemy models:
```bash
alembic revision --autogenerate -m "description_of_change"
alembic upgrade head
```

### 5. Seed Mock Data (Optional)

Populate sample users (Admin, Client, Guards), a client company, deployment site, shift rosters, attendance records, and an invoice:
```bash
python scripts/seed_db.py
```

### 6. Run the FastAPI Development Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 📖 API Documentation & Endpoints

Once the server is running, explore interactive Swagger docs at:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

### Master Endpoint Routes

| Resource | Methods | Base URL | Description |
| :--- | :--- | :--- | :--- |
| **Users** | `GET`, `POST`, `PUT`, `DELETE` | `/api/v1/users/` | Manage user credentials & roles |
| **Clients** | `GET`, `POST`, `PUT`, `DELETE` | `/api/v1/clients/` | Client corporate accounts |
| **Sites** | `GET`, `POST`, `PUT`, `DELETE` | `/api/v1/sites/` | Sites & guard deployment configs |
| **Guards** | `GET`, `POST`, `PUT`, `DELETE` | `/api/v1/guards/` | Guard profiles, badge numbers & rates |
| **Shift Rosters**| `GET`, `POST`, `PUT`, `DELETE` | `/api/v1/rosters/` | Shift assignments & schedules |
| **Attendance** | `GET`, `POST`, `PUT`, `DELETE` | `/api/v1/attendances/` | Check-in/out & overtime records |
| **Invoices** | `GET`, `POST`, `PUT`, `DELETE` | `/api/v1/invoices/` | Client billing & monthly invoices |
