"""Static analysis service orchestrating Ruff execution, persistence, and queries (P4-01)."""

import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import sqlalchemy as sa
from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.static.models import StaticFinding
from app.static.runner import NormalizedFinding, run_ruff_check
from app.static.schemas import (
    FindingSeverity,
    StaticFindingItem,
    StaticFindingsResponse,
    StaticFindingsSummary,
)

logger = logging.getLogger("repopilot.static.service")


class StaticAnalysisService:
    """Service for running static analysis scans and querying stored findings."""

    async def run_and_store_findings(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        repo_path: Path | str,
        scan_id: uuid.UUID | None = None,
        select_rules: list[str] | None = None,
    ) -> list[StaticFinding]:
        """Execute Ruff on the repository path and persist normalized findings to database."""
        # Clean existing findings for this repository
        await session.execute(
            delete(StaticFinding).where(StaticFinding.repository_id == repository_id)
        )

        normalized_findings: list[NormalizedFinding] = run_ruff_check(
            target_path=repo_path,
            select_rules=select_rules,
        )

        now = datetime.now(UTC)
        records: list[StaticFinding] = []
        for f in normalized_findings:
            record = StaticFinding(
                repository_id=repository_id,
                scan_id=scan_id,
                file_path=f.file_path,
                rule=f.rule,
                category=f.category,
                severity=f.severity,
                message=f.message,
                line_start=f.line_start,
                line_end=f.line_end,
                column_start=f.column_start,
                column_end=f.column_end,
                rule_url=f.rule_url,
                fix_available=f.fix_available,
                fix_message=f.fix_message,
                source="static",  # Hard Rule 5
                created_at=now,
            )
            session.add(record)
            records.append(record)

        await session.commit()
        logger.info(
            "Persisted %d static analysis findings for repository %s (scan_id=%s)",
            len(records),
            repository_id,
            scan_id,
        )
        return records

    async def store_normalized_findings(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        findings: list[NormalizedFinding],
        scan_id: uuid.UUID | None = None,
    ) -> list[StaticFinding]:
        """Directly persist a list of normalized findings (useful for memory or scan pipelines)."""
        await session.execute(
            delete(StaticFinding).where(StaticFinding.repository_id == repository_id)
        )

        now = datetime.now(UTC)
        records: list[StaticFinding] = []
        for f in findings:
            record = StaticFinding(
                repository_id=repository_id,
                scan_id=scan_id,
                file_path=f.file_path,
                rule=f.rule,
                category=f.category,
                severity=f.severity,
                message=f.message,
                line_start=f.line_start,
                line_end=f.line_end,
                column_start=f.column_start,
                column_end=f.column_end,
                rule_url=f.rule_url,
                fix_available=f.fix_available,
                fix_message=f.fix_message,
                source="static",  # Hard Rule 5
                created_at=now,
            )
            session.add(record)
            records.append(record)

        await session.commit()
        return records

    async def get_repository_findings(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        severity: str | None = None,
        rule: str | None = None,
        file_path: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> StaticFindingsResponse:
        """Query stored static analysis findings with summary statistics."""
        # 1. Summary aggregations
        stats_query = select(
            func.count(StaticFinding.id).label("total"),
            func.sum(sa.case((StaticFinding.severity == "error", 1), else_=0)).label("errors"),
            func.sum(sa.case((StaticFinding.severity == "warning", 1), else_=0)).label("warnings"),
            func.sum(sa.case((StaticFinding.severity == "info", 1), else_=0)).label("infos"),
            func.count(sa.distinct(StaticFinding.file_path)).label("files_count"),
        ).where(StaticFinding.repository_id == repository_id)

        stats_res = await session.execute(stats_query)
        row = stats_res.first()

        total = int(row.total or 0) if row else 0
        errors = int(row.errors or 0) if row else 0
        warnings = int(row.warnings or 0) if row else 0
        infos = int(row.infos or 0) if row else 0
        files_count = int(row.files_count or 0) if row else 0

        # Top 5 rules by count
        top_rules_query = (
            select(
                StaticFinding.rule,
                StaticFinding.category,
                StaticFinding.severity,
                func.count(StaticFinding.id).label("rule_count"),
            )
            .where(StaticFinding.repository_id == repository_id)
            .group_by(StaticFinding.rule, StaticFinding.category, StaticFinding.severity)
            .order_by(desc("rule_count"))
            .limit(5)
        )
        rules_res = await session.execute(top_rules_query)
        top_rules = [
            {
                "rule": str(r_row[0]),
                "category": str(r_row[1]),
                "severity": str(r_row[2]),
                "count": int(r_row[3]),
            }
            for r_row in rules_res.all()
        ]

        summary = StaticFindingsSummary(
            total_findings=total,
            error_count=errors,
            warning_count=warnings,
            info_count=infos,
            affected_files_count=files_count,
            top_rules=top_rules,
        )

        # 2. Filtered findings query
        stmt = select(StaticFinding).where(StaticFinding.repository_id == repository_id)
        if severity in ["error", "warning", "info"]:
            stmt = stmt.where(StaticFinding.severity == severity)
        if rule:
            stmt = stmt.where(StaticFinding.rule == rule)
        if file_path:
            stmt = stmt.where(StaticFinding.file_path.ilike(f"%{file_path}%"))

        # Order by severity priority (error -> warning -> info) then file and line
        severity_priority = sa.case(
            (StaticFinding.severity == "error", 1),
            (StaticFinding.severity == "warning", 2),
            else_=3,
        )
        stmt = stmt.order_by(severity_priority, StaticFinding.file_path, StaticFinding.line_start)
        stmt = stmt.offset(offset).limit(limit)

        findings_res = await session.execute(stmt)
        records = findings_res.scalars().all()

        finding_items = [
            StaticFindingItem(
                id=str(r.id),
                file_path=r.file_path,
                rule=r.rule,
                category=r.category,
                severity=cast(FindingSeverity, r.severity),
                message=r.message,
                line_start=r.line_start,
                line_end=r.line_end,
                column_start=r.column_start,
                column_end=r.column_end,
                rule_url=r.rule_url,
                fix_available=r.fix_available,
                fix_message=r.fix_message,
                source="static",  # Hard Rule 5
                created_at=r.created_at.isoformat(),
            )
            for r in records
        ]

        return StaticFindingsResponse(
            repository_id=str(repository_id),
            scan_id=str(records[0].scan_id) if records and records[0].scan_id else None,
            source="static",  # Hard Rule 5
            summary=summary,
            findings=finding_items,
        )


_static_service: StaticAnalysisService | None = None


def get_static_service() -> StaticAnalysisService:
    """Provide singleton instance of StaticAnalysisService."""
    global _static_service
    if _static_service is None:
        _static_service = StaticAnalysisService()
    return _static_service
