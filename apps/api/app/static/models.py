"""SQLAlchemy models for normalized static analysis findings (P4-01)."""

import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class StaticFinding(Base):
    """Stores normalized static analysis findings from Ruff (and future linters).

    Enforces:
    - Hard Rule 3: Repository content is untrusted input.
    - Hard Rule 5: Source labelled strictly as 'static'.
    - P4-01 Acceptance Criteria: findings stored with rule, severity, line.
    """

    __tablename__ = "static_findings"

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
    rule: Mapped[str] = mapped_column(
        sa.String(64),
        nullable=False,
        index=True,
    )  # e.g. 'F401', 'E501', 'B008', 'S101'
    category: Mapped[str] = mapped_column(
        sa.String(64),
        nullable=False,
        default="lint",
    )  # 'security', 'syntax', 'complexity', 'bugrisk', 'style', 'lint'
    severity: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        index=True,
    )  # 'error', 'warning', 'info'
    message: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
    )
    line_start: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        index=True,
    )
    line_end: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
    )
    column_start: Mapped[int | None] = mapped_column(
        sa.Integer,
        nullable=True,
    )
    column_end: Mapped[int | None] = mapped_column(
        sa.Integer,
        nullable=True,
    )
    rule_url: Mapped[str | None] = mapped_column(
        sa.String(1024),
        nullable=True,
    )
    fix_available: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=False,
    )
    fix_message: Mapped[str | None] = mapped_column(
        sa.String(512),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        default="static",
    )  # Hard Rule 5: 'static'
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    def __init__(self, **kwargs: Any) -> None:
        if "source" not in kwargs:
            kwargs["source"] = "static"
        super().__init__(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        """Convert static finding entity to dictionary representation."""
        return {
            "id": str(self.id) if self.id else str(uuid.uuid4()),
            "repository_id": str(self.repository_id),
            "scan_id": str(self.scan_id) if self.scan_id else None,
            "file_path": self.file_path,
            "rule": self.rule,
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "column_start": self.column_start,
            "column_end": self.column_end,
            "rule_url": self.rule_url,
            "fix_available": self.fix_available,
            "fix_message": self.fix_message,
            "source": self.source,
            "created_at": (
                self.created_at.isoformat() if self.created_at else datetime.now(UTC).isoformat()
            ),
        }
