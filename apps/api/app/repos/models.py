"""SQLAlchemy models for repositories."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Repository(Base):
    """Repository entity registered for indexing and analysis."""

    __tablename__ = "repositories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="github",
    )  # e.g. "github", "upload"
    url: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )  # e.g. "owner/repo" or upload name
    default_branch: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="main",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="registered",
        index=True,
    )  # "registered", "scanning", "ready", "failed"
    indexed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    scans: Mapped[list["RepositoryScan"]] = relationship(
        "RepositoryScan",
        back_populates="repository",
        cascade="all, delete-orphan",
        order_by="desc(RepositoryScan.created_at)",
    )

    __table_args__ = (Index("ix_repositories_source_status", "source", "status"),)

    def __init__(self, **kwargs: object) -> None:
        if "created_at" not in kwargs or kwargs["created_at"] is None:
            kwargs["created_at"] = datetime.now(UTC)
        if "id" not in kwargs or kwargs["id"] is None:
            kwargs["id"] = uuid.uuid4()
        if "default_branch" not in kwargs or kwargs["default_branch"] is None:
            kwargs["default_branch"] = "main"
        if "status" not in kwargs or kwargs["status"] is None:
            kwargs["status"] = "registered"
        if "source" not in kwargs or kwargs["source"] is None:
            kwargs["source"] = "github"
        super().__init__(**kwargs)


class RepositoryScan(Base):
    """Execution record for an ingestion/scan job on a repository."""

    __tablename__ = "repository_scans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
    )  # "pending", "in_progress", "completed", "failed", "cancelled"
    current_stage: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="queued",
    )  # "queued", "fetching", "filtering", "parsing", "metrics", "completed", "failed"
    stage_progress: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
    )
    file_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    total_lines: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    total_symbols: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    metrics_summary: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    repository: Mapped["Repository"] = relationship(
        "Repository",
        back_populates="scans",
    )

    def __init__(self, **kwargs: object) -> None:
        if "created_at" not in kwargs or kwargs["created_at"] is None:
            kwargs["created_at"] = datetime.now(UTC)
        if "updated_at" not in kwargs or kwargs["updated_at"] is None:
            kwargs["updated_at"] = datetime.now(UTC)
        if "id" not in kwargs or kwargs["id"] is None:
            kwargs["id"] = uuid.uuid4()
        if "status" not in kwargs or kwargs["status"] is None:
            kwargs["status"] = "pending"
        if "current_stage" not in kwargs or kwargs["current_stage"] is None:
            kwargs["current_stage"] = "queued"
        if "file_count" not in kwargs or kwargs["file_count"] is None:
            kwargs["file_count"] = 0
        if "total_lines" not in kwargs or kwargs["total_lines"] is None:
            kwargs["total_lines"] = 0
        if "total_symbols" not in kwargs or kwargs["total_symbols"] is None:
            kwargs["total_symbols"] = 0
        super().__init__(**kwargs)
