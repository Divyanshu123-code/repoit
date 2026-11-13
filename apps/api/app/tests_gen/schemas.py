"""Pydantic schemas for AI test generation endpoints (P5-02).

Enforces:
    - Hard Rule 5: source labelled strictly as 'llm_generated'.
    - Status initialized strictly as 'unvalidated' prior to sandbox execution (P5-03).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class GenerateTestRequest(BaseModel):
    """Input payload to request test generation."""

    target_file: str = Field(
        ...,
        min_length=1,
        description="Path of the repository file to generate tests for",
        examples=["app/repos/filter.py"],
    )
    target_symbol: str | None = Field(
        default=None,
        description="Optional function or class name within target_file to test",
        examples=["RepoFileFilter"],
    )
    finding_id: str | None = Field(
        default=None,
        description="Optional static finding UUID to generate targeted regression test for",
    )
    test_type: Literal["unit", "regression", "edge_case"] = Field(
        default="unit",
        description="Type of test case to generate",
    )
    focus_description: str | None = Field(
        default=None,
        description="Specific instructions or edge cases to cover",
        examples=["Verify rejection of path traversal symlinks pointing outside root"],
    )
    custom_code_snippet: str | None = Field(
        default=None,
        description="Optional explicit source code snippet of target function/class",
    )


class GeneratedTestResponse(BaseModel):
    """Details of an individual generated test case.

    Enforces Hard Rule 5: source labelled strictly as 'llm_generated'.
    """

    id: str
    repository_id: str
    target_file: str
    target_symbol: str | None = None
    finding_id: str | None = None
    test_framework: str = "pytest"
    test_name: str
    test_code: str
    test_file_path: str
    status: Literal["unvalidated", "passed", "failed", "error"] = "unvalidated"
    error_message: str | None = None
    execution_output: str | None = None
    execution_duration_ms: int | None = None
    source: Literal["llm_generated"] = "llm_generated"
    model_version: str
    created_at: str
    updated_at: str


class GeneratedTestListResponse(BaseModel):
    """Summary and collection of generated tests for a repository."""

    repository_id: str
    total_count: int
    unvalidated_count: int
    passed_count: int
    failed_count: int
    source: Literal["llm_generated"] = "llm_generated"
    tests: list[GeneratedTestResponse] = Field(default_factory=list)
