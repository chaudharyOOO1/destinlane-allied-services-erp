"""Add administrator Login ID support

Revision ID: 0003_login_id
Revises: 0002_fortellus_roles_v2
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_login_id"
down_revision: Union[str, None] = "0002_fortellus_roles_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("login_id", sa.String(length=255), nullable=True))
    op.create_index(
        "ix_users_login_id",
        "users",
        ["login_id"],
        unique=False,
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS users_login_id_lower_idx "
        "ON public.users (lower(login_id)) WHERE login_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.users_login_id_lower_idx")
    op.drop_index("ix_users_login_id", table_name="users")
    op.drop_column("users", "login_id")
