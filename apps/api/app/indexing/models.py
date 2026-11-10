"""Data models and SQLAlchemy entities for code chunking and semantic indexing (P2-01, P2-03)."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from pgvector.sqlalchemy import Vector
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ChunkStrategy(str, Enum):
    """Strategy used to partition source code into a chunk."""

    SYMBOL_BASED = "symbol_based"
    WINDOW_FALLBACK = "window_fallback"
    MODULE_PREAMBLE = "module_preamble"


@dataclass(frozen=True)
class CodeChunk:
    """In-memory representation of a code chunk."""

    file_path: str
    start_line: int  # 1-indexed
    end_line: int  # 1-indexed
    content: str
    strategy: ChunkStrategy
    symbol_name: str | None = None
    symbol_type: str | None = None
    context_header: str = ""
    char_count: int = 0
    estimated_tokens: int = 0
    content_sha256: str = ""


class CodeChunkRecord(Base):
    """SQLAlchemy entity representing an indexed chunk with vector embedding in pgvector."""

    __tablename__ = "code_chunks"

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
    file_path: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        index=True,
    )
    start_line: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    end_line: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    context_header: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )
    strategy: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ChunkStrategy.SYMBOL_BASED.value,
    )
    symbol_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    symbol_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    char_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    estimated_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    content_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1536),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (Index("ix_code_chunks_repo_file", "repository_id", "file_path"),)


# --- Pydantic schemas for semantic search API ---


class SearchResultItem(BaseModel):
    """Individual semantic search match."""

    id: uuid.UUID
    path: str
    start_line: int
    end_line: int
    score: float
    content: str
    symbol_name: str | None = None
    symbol_type: str | None = None
    context_header: str = ""
    source: str = Field(
        default="static",
        description="Source of this result per Rule 5 (static code chunk)",
    )


class SearchResponse(BaseModel):
    """Response payload for semantic code search."""

    repository_id: uuid.UUID
    query: str
    count: int
    results: list[SearchResultItem]
