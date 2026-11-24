"""Store hashed rotating refresh tokens."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0005_refresh_tokens"
down_revision = "0004_conversations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",
        sa.Column("digest", sa.String(64), primary_key=True),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_refresh_tokens_family", "refresh_tokens", ["family_id"])


def downgrade() -> None:
    op.drop_table("refresh_tokens")
