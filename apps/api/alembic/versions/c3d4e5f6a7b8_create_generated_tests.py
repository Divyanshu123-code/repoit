"""create_generated_tests

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-11-13 21:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema: create generated_tests table with status 'unvalidated' (P5-02)."""
    op.create_table(
        "generated_tests",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "repository_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_file", sa.String(1024), nullable=False),
        sa.Column("target_symbol", sa.String(256), nullable=True),
        sa.Column(
            "finding_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("static_findings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("test_framework", sa.String(32), nullable=False, server_default="pytest"),
        sa.Column("test_name", sa.String(256), nullable=False),
        sa.Column("test_code", sa.Text(), nullable=False),
        sa.Column("test_file_path", sa.String(1024), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="unvalidated"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("execution_output", sa.Text(), nullable=True),
        sa.Column("execution_duration_ms", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="llm_generated"),
        sa.Column("model_version", sa.String(64), nullable=False, server_default="gpt-4o-mini"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index(
        "ix_generated_tests_repository_id",
        "generated_tests",
        ["repository_id"],
        unique=False,
    )
    op.create_index(
        "ix_generated_tests_target_file",
        "generated_tests",
        ["target_file"],
        unique=False,
    )
    op.create_index(
        "ix_generated_tests_target_symbol",
        "generated_tests",
        ["target_symbol"],
        unique=False,
    )
    op.create_index(
        "ix_generated_tests_finding_id",
        "generated_tests",
        ["finding_id"],
        unique=False,
    )
    op.create_index(
        "ix_generated_tests_status",
        "generated_tests",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_generated_tests_test_name",
        "generated_tests",
        ["test_name"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema: drop generated_tests table."""
    op.drop_index("ix_generated_tests_test_name", table_name="generated_tests")
    op.drop_index("ix_generated_tests_status", table_name="generated_tests")
    op.drop_index("ix_generated_tests_finding_id", table_name="generated_tests")
    op.drop_index("ix_generated_tests_target_symbol", table_name="generated_tests")
    op.drop_index("ix_generated_tests_target_file", table_name="generated_tests")
    op.drop_index("ix_generated_tests_repository_id", table_name="generated_tests")
    op.drop_table("generated_tests")
