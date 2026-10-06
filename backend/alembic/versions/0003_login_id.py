"""Add administrator Login ID support

Revision ID: 0003_login_id
Revises: 0002_destinlane_roles_v2
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0003_login_id"
down_revision: Union[str, None] = "0002_destinlane_roles_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.users ADD COLUMN IF NOT EXISTS login_id varchar(255)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_login_id ON public.users (login_id)")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS users_login_id_lower_idx "
        "ON public.users (lower(login_id)) WHERE login_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.users_login_id_lower_idx")
    op.execute("DROP INDEX IF EXISTS public.ix_users_login_id")
    op.execute("ALTER TABLE public.users DROP COLUMN IF EXISTS login_id")
