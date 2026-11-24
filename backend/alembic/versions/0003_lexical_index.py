"""Index normalized chunk text for bilingual lexical search."""

import sqlalchemy as sa

from alembic import op

revision = "0003_lexical_index"
down_revision = "0002_email_and_processing_age"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_chunks_lexical", "chunks",
        [sa.text("to_tsvector('simple'::regconfig, normalized_text)")],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_chunks_lexical", table_name="chunks")
