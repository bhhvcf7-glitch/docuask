"""Create users, documents, and chunks."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("media_type", sa.String(120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("failure_reason", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE",
            name="fk_documents_user_id_users",
        ),
        sa.UniqueConstraint("user_id", "sha256", name="uq_documents_owner_hash"),
        sa.UniqueConstraint("id", "user_id", name="uq_documents_id_user_id"),
        sa.CheckConstraint("size_bytes > 0", name="ck_documents_positive_size"),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'ready', 'failed')",
            name="ck_documents_valid_status",
        ),
    )
    op.create_table(
        "chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id", "user_id"], ["documents.id", "documents.user_id"],
            ondelete="CASCADE", name="fk_chunks_document_owner",
        ),
        sa.UniqueConstraint("document_id", "ordinal", name="uq_chunks_document_ordinal"),
        sa.CheckConstraint("ordinal >= 0", name="ck_chunks_nonnegative_ordinal"),
        sa.CheckConstraint("page_number >= 1", name="ck_chunks_positive_page_number"),
    )
    op.create_index("ix_chunks_user_document", "chunks", ["user_id", "document_id"])


def downgrade() -> None:
    op.drop_index("ix_chunks_user_document", table_name="chunks")
    op.drop_table("chunks")
    op.drop_table("documents")
    op.drop_table("users")
