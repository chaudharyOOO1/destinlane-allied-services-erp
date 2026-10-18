"""Versioned travel requests, receipts, decisions and reimbursements."""
from pathlib import Path
from alembic import op

revision = '0008_travel_expenses'
down_revision = '0007_compact_personnel_ids'
branch_labels = None
depends_on = None


def upgrade():
    migration = Path(__file__).resolve().parents[3] / 'supabase/migrations/20261018120000_travel_expenses.sql'
    with op.get_bind().connection.driver_connection.cursor() as cursor:
        cursor.execute(migration.read_text(), prepare=False)


def downgrade():
    raise RuntimeError('Retain travel claims, payments and audit history; use a reviewed forward migration.')
