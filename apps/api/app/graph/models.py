"""SQLAlchemy models for dependency graph and persisted edges (P4-02)."""

import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class DependencyEdge(Base):
    """Stores directed import dependency edges between repository files and modules.

    Enforces:
    - Hard Rule 5: Source labelled strictly as 'graph_derived'.
    - P4-02 Criteria: Import graph builder (NetworkX) + persisted edges.
    """

    __tablename__ = "dependency_edges"

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
    source_file: Mapped[str] = mapped_column(
        sa.String(1024),
        nullable=False,
        index=True,
    )  # e.g., 'app/api/repos.py'
    target_module: Mapped[str] = mapped_column(
        sa.String(1024),
        nullable=False,
        index=True,
    )  # e.g., 'app.repos.service' or 'os'
    target_file: Mapped[str | None] = mapped_column(
        sa.String(1024),
        nullable=True,
        index=True,
    )  # Resolved internal path, e.g., 'app/repos/service.py' (or None if external)
    import_statement: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
    )
    line_number: Mapped[int | None] = mapped_column(
        sa.Integer,
        nullable=True,
    )
    is_internal: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=True,
        index=True,
    )
    imported_symbols: Mapped[list[str]] = mapped_column(
        sa.JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    source: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        default="graph_derived",
    )  # Hard Rule 5: 'graph_derived'
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    def __init__(self, **kwargs: Any) -> None:
        if "source" not in kwargs:
            kwargs["source"] = "graph_derived"
        super().__init__(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        """Convert dependency edge entity to dictionary representation."""
        return {
            "id": str(self.id) if self.id else str(uuid.uuid4()),
            "repository_id": str(self.repository_id),
            "scan_id": str(self.scan_id) if self.scan_id else None,
            "source_file": self.source_file,
            "target_module": self.target_module,
            "target_file": self.target_file,
            "import_statement": self.import_statement,
            "line_number": self.line_number,
            "is_internal": self.is_internal,
            "imported_symbols": self.imported_symbols,
            "source": self.source,
            "created_at": (
                self.created_at.isoformat() if self.created_at else datetime.now(UTC).isoformat()
            ),
        }
