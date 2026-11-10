"""Pydantic schemas for repository registration and responses."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RepoRegisterRequest(BaseModel):
    """Request payload for registering a repository via public URL."""

    url: str = Field(
        ...,
        description="Public repository URL (e.g. https://github.com/owner/repo)",
        examples=["https://github.com/psf/requests"],
    )


class RepoResponse(BaseModel):
    """Repository entity response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    url: str | None = None
    full_name: str
    default_branch: str
    status: str
    indexed_at: datetime | None = None
    created_at: datetime


class ScanResponse(BaseModel):
    """Repository scan status and results schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    repository_id: uuid.UUID
    status: str
    current_stage: str
    stage_progress: dict[str, Any] | None = None
    error_message: str | None = None
    file_count: int
    total_lines: int
    total_symbols: int
    metrics_summary: dict[str, Any] | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ErrorDetail(BaseModel):
    """Standardized error detail schema."""

    code: str
    message: str


class ErrorResponse(BaseModel):
    """Standardized error envelope matching DATA_MODEL_AND_API conventions."""

    error: ErrorDetail
