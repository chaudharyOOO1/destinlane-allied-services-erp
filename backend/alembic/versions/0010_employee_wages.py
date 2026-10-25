"""Effective-dated employee wages; private backend-only writes."""
from pathlib import Path
from alembic import op
revision = '0010_employee_wages'
down_revision = '0009_md_accounting'
branch_labels = None
depends_on = None


def upgrade():
    path = Path(__file__).resolve().parents[3] / 'supabase/migrations/20261025100000_employee_wages.sql'
    with op.get_bind().connection.driver_connection.cursor() as cursor:
        cursor.execute(path.read_text(), prepare=False)


def downgrade():
    raise RuntimeError('Retain wage history; use a reviewed forward migration.')
