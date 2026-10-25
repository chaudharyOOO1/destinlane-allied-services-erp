"""Transactional response replay for authenticated, scoped write requests."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0010_api_idempotency"
down_revision = "0009_md_accounting"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "api_idempotency_requests",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("operation", sa.String(120), nullable=False),
        sa.Column("request_key", sa.String(128), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("response", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("actor_id","operation","request_key",name="uq_api_idempotency_actor_operation_key")
    )
    op.execute("ALTER TABLE api_idempotency_requests ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON TABLE api_idempotency_requests FROM PUBLIC, anon, authenticated")
    op.execute("REVOKE ALL ON SEQUENCE api_idempotency_requests_id_seq FROM PUBLIC, anon, authenticated")

def downgrade():
    raise RuntimeError(
        "Idempotency records are transaction audit/recovery evidence. "
        "Rollback the application without dropping the ledger; use a "
        "separately reviewed forward migration if a schema correction is needed."
    )
