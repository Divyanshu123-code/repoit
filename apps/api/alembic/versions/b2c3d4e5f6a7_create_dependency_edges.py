"""create_dependency_edges

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-11-12 23:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema: create dependency_edges table for persisted import graph edges (P4-02)."""
    op.create_table(
        "dependency_edges",
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
        sa.Column("source_file", sa.String(length=1024), nullable=False),
        sa.Column("target_module", sa.String(length=1024), nullable=False),
        sa.Column("target_file", sa.String(length=1024), nullable=True),
        sa.Column("import_statement", sa.Text(), nullable=True),
        sa.Column("line_number", sa.Integer(), nullable=True),
        sa.Column(
            "is_internal",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "imported_symbols",
            sa.JSON().with_variant(JSONB, "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.String(length=32),
            nullable=False,
            server_default="graph_derived",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_dependency_edges_repository_id",
        "dependency_edges",
        ["repository_id"],
    )
    op.create_index(
        "ix_dependency_edges_scan_id",
        "dependency_edges",
        ["scan_id"],
    )
    op.create_index(
        "ix_dependency_edges_source_file",
        "dependency_edges",
        ["source_file"],
    )
    op.create_index(
        "ix_dependency_edges_target_module",
        "dependency_edges",
        ["target_module"],
    )
    op.create_index(
        "ix_dependency_edges_target_file",
        "dependency_edges",
        ["target_file"],
    )
    op.create_index(
        "ix_dependency_edges_is_internal",
        "dependency_edges",
        ["is_internal"],
    )
    op.create_index(
        "ix_dependency_edges_repo_source",
        "dependency_edges",
        ["repository_id", "source_file"],
    )
    op.create_index(
        "ix_dependency_edges_repo_target",
        "dependency_edges",
        ["repository_id", "target_file"],
    )


def downgrade() -> None:
    """Downgrade schema: drop dependency_edges table."""
    op.drop_index("ix_dependency_edges_repo_target", table_name="dependency_edges")
    op.drop_index("ix_dependency_edges_repo_source", table_name="dependency_edges")
    op.drop_index("ix_dependency_edges_is_internal", table_name="dependency_edges")
    op.drop_index("ix_dependency_edges_target_file", table_name="dependency_edges")
    op.drop_index("ix_dependency_edges_target_module", table_name="dependency_edges")
    op.drop_index("ix_dependency_edges_source_file", table_name="dependency_edges")
    op.drop_index("ix_dependency_edges_scan_id", table_name="dependency_edges")
    op.drop_index("ix_dependency_edges_repository_id", table_name="dependency_edges")
    op.drop_table("dependency_edges")
