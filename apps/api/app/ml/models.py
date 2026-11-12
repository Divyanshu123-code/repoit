"""SQLAlchemy models for ML defect prediction storage (P3-07)."""

import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class MLPrediction(Base):
    """Stores ML defect prediction results for repository files and functions.

    Enforces:
    - Hard Rule 5: Source labelled strictly as 'ml_predicted'.
    - Hard Rule 6: Predictions are risk estimates, never 'confirmed bugs', with model_version.
    """

    __tablename__ = "ml_predictions"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scan_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("repository_scans.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    file_path: Mapped[str] = mapped_column(
        sa.String(1024),
        nullable=False,
        index=True,
    )
    function_name: Mapped[str | None] = mapped_column(
        sa.String(255),
        nullable=True,
    )
    line_start: Mapped[int | None] = mapped_column(
        sa.Integer,
        nullable=True,
    )
    line_end: Mapped[int | None] = mapped_column(
        sa.Integer,
        nullable=True,
    )
    risk_probability: Mapped[float] = mapped_column(
        sa.Float,
        nullable=False,
    )
    risk_band: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        index=True,
    )  # 'low' | 'medium' | 'high'
    model_version: Mapped[str] = mapped_column(
        sa.String(64),
        nullable=False,
    )  # e.g. '2.0.0'
    top_features: Mapped[list[dict[str, Any]]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    source: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        default="ml_predicted",
    )  # Hard Rule 5: 'ml_predicted'
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    # Relationships
    repository = relationship("Repository", backref="ml_predictions")
    scan = relationship("RepositoryScan", backref="ml_predictions")

    def to_dict(self) -> dict[str, Any]:
        """Convert MLPrediction model instance to dictionary representation."""
        return {
            "id": str(self.id) if self.id else str(uuid.uuid4()),
            "repository_id": str(self.repository_id),
            "scan_id": str(self.scan_id) if self.scan_id else None,
            "file_path": self.file_path,
            "function_name": self.function_name,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "risk_probability": round(self.risk_probability, 4),
            "risk_band": self.risk_band,
            "model_version": self.model_version,
            "top_features": self.top_features,
            "source": self.source,
            "created_at": self.created_at.isoformat()
            if self.created_at
            else datetime.now(UTC).isoformat(),
        }
