"""create_users_and_repositories

Revision ID: db456220b2e2
Revises: 676d5b6e6af4
Create Date: 2026-11-10 21:16:31.300082

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "db456220b2e2"
down_revision: str | Sequence[str] | None = "676d5b6e6af4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema: create users and repositories tables."""
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "repositories",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "owner_user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source", sa.String(length=50), server_default="github", nullable=False),
        sa.Column("url", sa.String(length=512), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("default_branch", sa.String(length=100), server_default="main", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="registered", nullable=False),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_repositories_owner_user_id", "repositories", ["owner_user_id"], unique=False
    )
    op.create_index("ix_repositories_url", "repositories", ["url"], unique=False)
    op.create_index("ix_repositories_full_name", "repositories", ["full_name"], unique=False)
    op.create_index("ix_repositories_status", "repositories", ["status"], unique=False)
    op.create_index(
        "ix_repositories_source_status", "repositories", ["source", "status"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema: drop repositories and users tables."""
    op.drop_index("ix_repositories_source_status", table_name="repositories")
    op.drop_index("ix_repositories_status", table_name="repositories")
    op.drop_index("ix_repositories_full_name", table_name="repositories")
    op.drop_index("ix_repositories_url", table_name="repositories")
    op.drop_index("ix_repositories_owner_user_id", table_name="repositories")
    op.drop_table("repositories")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
