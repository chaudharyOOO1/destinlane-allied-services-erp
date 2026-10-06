"""Bootstrap the enterprise schema and its versioned SQL migrations.

Revision ID: 0005_enterprise_schema
Revises: 0004_user_permissions

This revision is for a database managed by Alembic from its initial schema.
Existing Supabase installations must continue using their migration history;
do not replay this revision over an unversioned populated database.
"""
from pathlib import Path
from alembic import op

revision = "0005_enterprise_schema"
down_revision = "0004_user_permissions"
branch_labels = None
depends_on = None

# Fixed manifest: future SQL files need a new Alembic revision.
MIGRATIONS = (
    '20260926140000_enterprise_baseline.sql',
    '20260926150000_add_client_field_officers.sql',
    '20260926160000_phase2_staff_recruitment.sql',
    '20260926173000_phase3_contract_rates_roster.sql',
    '20260926180000_phase4_attendance_geofence.sql',
    '20260926190000_phase5_payroll_finance.sql',
    '20260926193000_phase5_finance_compatibility.sql',
    '20260926210000_user_permissions_and_password_controls.sql',
    '20260926223000_employee_bank_master_and_photo.sql',
    '20260927200000_employee_client_mapping_and_auto_code.sql',
    '20261003190129_company_setup.sql',
    '20261003190400_company_legal_storage.sql',
    '20261004072652_internal_staff_master.sql',
    '20261004075227_account_access_controls.sql',
    '20261004080302_client_master_controls.sql',
    '20261004082817_site_contract_rate_master.sql',
    '20261004090846_employee_master_workflow.sql',
    '20261004091538_employee_compliance_hardening.sql',
    '20261004092134_employee_workflow_indexes.sql',
    '20261004100450_roster_deployment_controls.sql',
    '20261005164419_attendance_workflow.sql',
    '20261006120000_runtime_schema_alignment.sql',
)


def upgrade():
    root = Path(__file__).resolve().parents[3] / "supabase" / "migrations"
    connection = op.get_bind()
    roles = connection.exec_driver_sql(
        "select rolname from pg_roles where rolname in ('anon','authenticated')"
    ).scalars().all()
    if len(roles) != 2:
        raise RuntimeError("Database needs NOLOGIN roles anon and authenticated. "
                           "See backend/README.md local PostgreSQL setup.")
    for name in MIGRATIONS:
        # Execute the entire versioned repository SQL file, including PL/pgSQL,
        # without splitting function bodies or silently dropping security DDL.
        with connection.connection.driver_connection.cursor() as cursor:
            cursor.execute((root / name).read_text(), prepare=False)


def downgrade():
    raise RuntimeError("Enterprise rollback is destructive. Restore a database backup instead.")
