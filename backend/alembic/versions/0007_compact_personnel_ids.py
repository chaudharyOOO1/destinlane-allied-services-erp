"""Use compact IDs for new employee and staff records.

Revision ID: 0007_compact_personnel_ids
Revises: 0006_staff_login_link
"""
from pathlib import Path
from alembic import op

revision = '0007_compact_personnel_ids'
down_revision = '0006_staff_login_link'
branch_labels = None
depends_on = None


def upgrade():
    sql = Path(__file__).resolve().parents[3] / 'supabase/migrations/20261006140000_compact_personnel_ids.sql'
    with op.get_bind().connection.driver_connection.cursor() as cursor:
        cursor.execute(sql.read_text(), prepare=False)


def downgrade():
    raise RuntimeError('Compact IDs already issued must be retained; use a forward migration.')
