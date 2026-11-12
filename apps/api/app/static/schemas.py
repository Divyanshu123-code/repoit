"""Pydantic schemas for static analysis findings and API endpoints (P4-01)."""

from typing import Any, Literal

from pydantic import BaseModel, Field

FindingSeverity = Literal["error", "warning", "info"]
FindingCategory = Literal["security", "syntax", "complexity", "bugrisk", "style", "lint"]


class StaticFindingItem(BaseModel):
    """Normalized static analysis finding item.

    Enforces Hard Rule 5 (source: 'static') and P4-01 criteria (rule, severity, line).
    """

    id: str
    file_path: str
    rule: str
    category: str
    severity: FindingSeverity
    message: str
    line_start: int
    line_end: int
    column_start: int | None = None
    column_end: int | None = None
    rule_url: str | None = None
    fix_available: bool = False
    fix_message: str | None = None
    source: Literal["static"] = "static"
    created_at: str


class RuleCountItem(BaseModel):
    """Count of occurrences for a specific linter rule."""

    rule: str
    count: int
    category: str
    severity: FindingSeverity


class StaticFindingsSummary(BaseModel):
    """Summary metrics of static findings across a repository."""

    total_findings: int
    error_count: int
    warning_count: int
    info_count: int
    affected_files_count: int
    top_rules: list[dict[str, Any]] = Field(default_factory=list)


class StaticFindingsResponse(BaseModel):
    """API response for static findings query.

    Enforces Hard Rule 5: source labelled strictly as 'static'.
    """

    repository_id: str
    scan_id: str | None = None
    source: Literal["static"] = "static"
    summary: StaticFindingsSummary
    findings: list[StaticFindingItem]


class TriggerStaticScanRequest(BaseModel):
    """Request payload to trigger on-demand static analysis scan."""

    target_paths: list[str] | None = None
