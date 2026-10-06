"""Link staff records to ERP login accounts.

Revision ID: 0006_staff_login_link
Revises: 0005_enterprise_schema
"""
from pathlib import Path
from alembic import op

revision = '0006_staff_login_link'
down_revision = '0005_enterprise_schema'
branch_labels = None
depends_on = None


def upgrade():
    sql = Path(__file__).resolve().parents[3] / 'supabase/migrations/20261006130000_staff_login_link.sql'
    with op.get_bind().connection.driver_connection.cursor() as cursor:
        cursor.execute(sql.read_text(), prepare=False)


def downgrade():
    op.drop_column('internal_staff', 'user_id')
