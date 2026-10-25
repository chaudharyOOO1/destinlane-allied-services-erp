"""Management approves internal staff remuneration each month."""
from pathlib import Path
from alembic import op
revision = '0012_staff_monthly_pay'
down_revision = '0011_login_lockout'
branch_labels = None
depends_on = None


def upgrade():
    path = Path(__file__).resolve().parents[3] / 'supabase/migrations/20261025120000_staff_monthly_pay.sql'
    with op.get_bind().connection.driver_connection.cursor() as cursor:
        cursor.execute(path.read_text(), prepare=False)


def downgrade():
    raise RuntimeError('Retain remuneration approvals and audit history.')
