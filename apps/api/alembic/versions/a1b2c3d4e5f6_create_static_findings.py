"""create_static_findings

Revision ID: a1b2c3d4e5f6
Revises: f6b8c9d01234
Create Date: 2026-11-12 23:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "f6b8c9d01234"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema: create static_findings table for normalized Ruff findings (P4-01)."""
    op.create_table(
        "static_findings",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "repository_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "scan_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("repository_scans.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("rule", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False, server_default="lint"),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("line_start", sa.Integer(), nullable=False),
        sa.Column("line_end", sa.Integer(), nullable=False),
        sa.Column("column_start", sa.Integer(), nullable=True),
        sa.Column("column_end", sa.Integer(), nullable=True),
        sa.Column("rule_url", sa.String(length=1024), nullable=True),
        sa.Column("fix_available", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("fix_message", sa.String(length=512), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="static"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_static_findings_repository_id",
        "static_findings",
        ["repository_id"],
    )
    op.create_index(
        "ix_static_findings_scan_id",
        "static_findings",
        ["scan_id"],
    )
    op.create_index(
        "ix_static_findings_file_path",
        "static_findings",
        ["file_path"],
    )
    op.create_index(
        "ix_static_findings_rule",
        "static_findings",
        ["rule"],
    )
    op.create_index(
        "ix_static_findings_severity",
        "static_findings",
        ["severity"],
    )
    op.create_index(
        "ix_static_findings_line_start",
        "static_findings",
        ["line_start"],
    )
    op.create_index(
        "ix_static_findings_repo_severity",
        "static_findings",
        ["repository_id", "severity"],
    )
    op.create_index(
        "ix_static_findings_repo_file",
        "static_findings",
        ["repository_id", "file_path"],
    )


def downgrade() -> None:
    """Downgrade schema: drop static_findings table."""
    op.drop_index("ix_static_findings_repo_file", table_name="static_findings")
    op.drop_index("ix_static_findings_repo_severity", table_name="static_findings")
    op.drop_index("ix_static_findings_line_start", table_name="static_findings")
    op.drop_index("ix_static_findings_severity", table_name="static_findings")
    op.drop_index("ix_static_findings_rule", table_name="static_findings")
    op.drop_index("ix_static_findings_file_path", table_name="static_findings")
    op.drop_index("ix_static_findings_scan_id", table_name="static_findings")
    op.drop_index("ix_static_findings_repository_id", table_name="static_findings")
    op.drop_table("static_findings")
