"""create_ml_predictions

Revision ID: f6b8c9d01234
Revises: e5a7b8c9d012
Create Date: 2026-11-12 23:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6b8c9d01234"
down_revision: str | Sequence[str] | None = "e5a7b8c9d012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema: create ml_predictions table for ML defect prediction storage (P3-07)."""
    op.create_table(
        "ml_predictions",
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
        sa.Column("function_name", sa.String(length=255), nullable=True),
        sa.Column("line_start", sa.Integer(), nullable=True),
        sa.Column("line_end", sa.Integer(), nullable=True),
        sa.Column("risk_probability", sa.Float(), nullable=False),
        sa.Column("risk_band", sa.String(length=32), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column(
            "top_features",
            sa.JSON().with_variant(JSONB, "postgresql"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="ml_predicted"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_ml_predictions_repository_id",
        "ml_predictions",
        ["repository_id"],
    )
    op.create_index(
        "ix_ml_predictions_scan_id",
        "ml_predictions",
        ["scan_id"],
    )
    op.create_index(
        "ix_ml_predictions_file_path",
        "ml_predictions",
        ["file_path"],
    )
    op.create_index(
        "ix_ml_predictions_risk_band",
        "ml_predictions",
        ["risk_band"],
    )
    op.create_index(
        "ix_ml_predictions_repo_risk",
        "ml_predictions",
        ["repository_id", "risk_band"],
    )


def downgrade() -> None:
    """Downgrade schema: drop ml_predictions table."""
    op.drop_index("ix_ml_predictions_repo_risk", table_name="ml_predictions")
    op.drop_index("ix_ml_predictions_risk_band", table_name="ml_predictions")
    op.drop_index("ix_ml_predictions_file_path", table_name="ml_predictions")
    op.drop_index("ix_ml_predictions_scan_id", table_name="ml_predictions")
    op.drop_index("ix_ml_predictions_repository_id", table_name="ml_predictions")
    op.drop_table("ml_predictions")
