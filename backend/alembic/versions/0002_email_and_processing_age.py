"""Normalize emails and track document processing age."""

from alembic import op
import sqlalchemy as sa

revision = "0002_email_and_processing_age"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    duplicates = bind.execute(sa.text(
        "SELECT lower(btrim(email)) AS address, count(*) "
        "FROM users GROUP BY lower(btrim(email)) HAVING count(*) > 1 LIMIT 1"
    )).first()
    if duplicates:
        raise RuntimeError(
            "Cannot normalize users.email: case/whitespace duplicate accounts exist. "
            "Resolve conflicting user records manually before running this migration."
        )

    op.execute("UPDATE users SET email = lower(btrim(email))")
    op.create_index("uq_users_email_lower", "users", [sa.text("lower(email)")], unique=True)
    op.add_column(
        "documents",
        sa.Column(
            "status_changed_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("documents", "status_changed_at")
    op.drop_index("uq_users_email_lower", table_name="users")
