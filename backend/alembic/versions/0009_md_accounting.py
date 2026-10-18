"""MD-only double-entry books and bank reconciliation."""
from pathlib import Path
from alembic import op
revision = '0009_md_accounting'
down_revision = '0008_travel_expenses'
branch_labels = None
depends_on = None


def upgrade():
    path = Path(__file__).resolve().parents[3] / 'supabase/migrations/20261018150000_md_accounting.sql'
    with op.get_bind().connection.driver_connection.cursor() as cursor:
        cursor.execute(path.read_text(),prepare=False)


def downgrade():
    raise RuntimeError('Retain books and posted vouchers. Use a reviewed forward correction.')
