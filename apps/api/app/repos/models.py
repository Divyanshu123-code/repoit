"""SQLAlchemy models for repositories."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

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
