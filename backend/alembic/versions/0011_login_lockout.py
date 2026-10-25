"""Shared database-backed office account lockout."""
from pathlib import Path
from alembic import op
revision = '0011_login_lockout'
down_revision = '0010_employee_wages'
branch_labels = None
depends_on = None


def upgrade():
    path = Path(__file__).resolve().parents[3] / 'supabase/migrations/20261025110000_login_lockout.sql'
    with op.get_bind().connection.driver_connection.cursor() as cursor:
        cursor.execute(path.read_text(), prepare=False)


def downgrade():
    raise RuntimeError('Retain security state; use a reviewed forward migration.')
