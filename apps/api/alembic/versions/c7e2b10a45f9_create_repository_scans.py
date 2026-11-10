"""create_repository_scans

Revision ID: c7e2b10a45f9
Revises: db456220b2e2
Create Date: 2026-11-11 01:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7e2b10a45f9"
down_revision: str | Sequence[str] | None = "db456220b2e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema: create repository_scans table."""
    op.create_table(
        "repository_scans",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "repository_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=50), server_default="pending", nullable=False),
        sa.Column("current_stage", sa.String(length=50), server_default="queued", nullable=False),
        sa.Column("stage_progress", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.String(length=2048), nullable=True),
        sa.Column("file_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_lines", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_symbols", sa.Integer(), server_default="0", nullable=False),
        sa.Column("metrics_summary", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_repository_scans_repository_id", "repository_scans", ["repository_id"], unique=False
    )
    op.create_index("ix_repository_scans_status", "repository_scans", ["status"], unique=False)
    op.create_index(
        "ix_repository_scans_repo_status",
        "repository_scans",
        ["repository_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema: drop repository_scans table."""
    op.drop_index("ix_repository_scans_repo_status", table_name="repository_scans")
    op.drop_index("ix_repository_scans_status", table_name="repository_scans")
    op.drop_index("ix_repository_scans_repository_id", table_name="repository_scans")
    op.drop_table("repository_scans")
