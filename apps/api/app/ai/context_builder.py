"""Context builder for conversational repository intelligence.

Aggregates repository scan metrics, static findings, dependency hubs,
and defect risk estimates to inject comprehensive context into conversational LLM prompts.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.graph.models import DependencyEdge
from app.ml.models import MLPrediction
from app.repos.models import Repository, RepositoryScan
from app.static.models import StaticFinding

logger = logging.getLogger("repopilot.ai.context")


class RepositoryContext:
    """Holds structured context metrics for prompt generation."""

    def __init__(
        self,
        repo: Repository,
        latest_scan: RepositoryScan | None = None,
        top_risk_modules: list[MLPrediction] | None = None,
        findings_summary: dict[str, int] | None = None,
        top_imported_modules: list[tuple[str, int]] | None = None,
    ) -> None:
        self.repo = repo
        self.latest_scan = latest_scan
        self.top_risk_modules = top_risk_modules or []
        self.findings_summary = findings_summary or {"error": 0, "warning": 0, "total": 0}
        self.top_imported_modules = top_imported_modules or []

    def format_summary_block(self) -> str:
        """Render a concise Markdown block of repo metadata, metrics, and health."""
        lines: list[str] = []
        lines.append(f"### Repository Profile: {self.repo.full_name}")
        if self.repo.url:
            lines.append(f"- URL: {self.repo.url}")
        lines.append(f"- Default Branch: {self.repo.default_branch}")
        lines.append(f"- Status: {self.repo.status}")

        if self.latest_scan:
            scan = self.latest_scan
            metrics = scan.metrics_summary or {}
            total_loc = metrics.get("total_loc", scan.total_lines)
            total_sloc = metrics.get("total_sloc", 0)
            avg_cc = metrics.get("avg_complexity", 0.0)
            avg_mi = metrics.get("avg_maintainability_index", 0.0)

            lines.append(
                f"- Scale: {scan.file_count} files, {total_loc} lines of code "
                f"({total_sloc} SLOC), {scan.total_symbols} functions/classes"
            )
            lines.append(
                f"- Quality Metrics: Avg Cyclomatic Complexity: {avg_cc}, "
                f"Maintainability Index: {avg_mi}/100"
            )

            # Categorized Module Manifest
            modules = metrics.get("modules", [])
            if modules:
                lines.append("\n#### Complete Repository Module Manifest:")
                cat_api: list[str] = []
                cat_services: list[str] = []
                cat_data: list[str] = []
                cat_core: list[str] = []
                cat_tests: list[str] = []

                for m in modules:
                    path = str(m.get("path", ""))
                    loc = m.get("loc", 0)
                    p_lower = path.lower()
                    entry = f"- `{path}` ({loc} LOC)"
                    if any(k in p_lower for k in ["router", "api", "endpoint", "view"]):
                        cat_api.append(entry)
                    elif any(k in p_lower for k in ["service", "engine", "worker", "logic", "pipeline"]):
                        cat_services.append(entry)
                    elif any(k in p_lower for k in ["model", "schema", "database", "db.", "alembic"]):
                        cat_data.append(entry)
                    elif any(k in p_lower for k in ["test", "fixture", "mock"]):
                        cat_tests.append(entry)
                    else:
                        cat_core.append(entry)

                if cat_api:
                    lines.append("\n**API & Routing Layer:**\n" + "\n".join(cat_api))
                if cat_services:
                    lines.append("\n**Business Services & Logic:**\n" + "\n".join(cat_services))
                if cat_data:
                    lines.append("\n**Data Models, Schemas & Persistence:**\n" + "\n".join(cat_data))
                if cat_core:
                    lines.append("\n**Core Application & Configuration:**\n" + "\n".join(cat_core))
                if cat_tests and len(cat_tests) <= 15:
                    lines.append("\n**Test Suites:**\n" + "\n".join(cat_tests))
                elif cat_tests:
                    lines.append(f"\n**Test Suites:** {len(cat_tests)} automated test files")

            # Top largest modules
            if modules:
                sorted_by_loc = sorted(
                    modules,
                    key=lambda m: int(m.get("loc", 0)),
                    reverse=True,
                )[:5]
                lines.append("\n#### Top Largest Modules by Code Volume:")
                for m in sorted_by_loc:
                    path = m.get("path", "unknown")
                    loc = m.get("loc", 0)
                    cc = m.get("complexity", 0)
                    mi = m.get("maintainability_index", 0)
                    lines.append(f"- `{path}`: {loc} LOC (Complexity: {cc}, Maintainability: {mi})")

        # Defect risk
        if self.top_risk_modules:
            lines.append("\n#### Defect Risk Estimates (ML Model Track B):")
            lines.append("(Note: Statistical risk estimates, not confirmed bugs - Hard Rule 6)")
            for pred in self.top_risk_modules[:5]:
                pct = round(pred.risk_probability * 100, 1)
                lines.append(f"- `{pred.file_path}`: {pct}% risk ({pred.risk_band} band)")

        # Static findings
        if self.findings_summary.get("total", 0) > 0:
            lines.append(
                f"\n#### Static Code Findings (Ruff): {self.findings_summary['total']} total "
                f"({self.findings_summary.get('error', 0)} errors, "
                f"{self.findings_summary.get('warning', 0)} warnings)"
            )

        # Import hubs
        if self.top_imported_modules:
            lines.append("\n#### Architectural Hubs (Most Imported Modules):")
            for mod_name, count in self.top_imported_modules[:5]:
                lines.append(f"- `{mod_name}`: imported by {count} modules")

        return "\n".join(lines)


async def build_repository_context(
    session: AsyncSession,
    repository_id: uuid.UUID,
) -> RepositoryContext:
    """Query database and construct a RepositoryContext instance."""
    # 1. Fetch Repository
    repo_res = await session.execute(select(Repository).where(Repository.id == repository_id))
    repo = repo_res.scalar_one_or_none()
    if repo is None:
        raise ValueError(f"Repository {repository_id} not found")

    # 2. Fetch Latest Scan
    scan_res = await session.execute(
        select(RepositoryScan)
        .where(RepositoryScan.repository_id == repository_id)
        .order_by(desc(RepositoryScan.created_at))
        .limit(1)
    )
    latest_scan = scan_res.scalar_one_or_none()

    # 3. Fetch Top Risk Modules
    risk_res = await session.execute(
        select(MLPrediction)
        .where(MLPrediction.repository_id == repository_id)
        .order_by(desc(MLPrediction.risk_probability))
        .limit(5)
    )
    top_risk = list(risk_res.scalars().all())

    # 4. Fetch Static Findings summary
    findings_summary: dict[str, int] = {"error": 0, "warning": 0, "total": 0}
    try:
        findings_res = await session.execute(
            select(StaticFinding.severity, func.count(StaticFinding.id))
            .where(StaticFinding.repository_id == repository_id)
            .group_by(StaticFinding.severity)
        )
        total = 0
        for sev, count in findings_res.all():
            findings_summary[sev.lower()] = count
            total += count
        findings_summary["total"] = total
    except Exception as exc:  # noqa: BLE001
        logger.debug("Static findings summary lookup skipped: %s", exc)

    # 5. Fetch Dependency Hubs (top imported modules)
    top_imported: list[tuple[str, int]] = []
    try:
        edges_res = await session.execute(
            select(DependencyEdge.target_module, func.count(DependencyEdge.id))
            .where(DependencyEdge.repository_id == repository_id)
            .where(DependencyEdge.is_internal.is_(True))
            .group_by(DependencyEdge.target_module)
            .order_by(desc(func.count(DependencyEdge.id)))
            .limit(5)
        )
        top_imported = [(row[0], row[1]) for row in edges_res.all()]
    except Exception as exc:  # noqa: BLE001
        logger.debug("Dependency edges lookup skipped: %s", exc)

    return RepositoryContext(
        repo=repo,
        latest_scan=latest_scan,
        top_risk_modules=top_risk,
        findings_summary=findings_summary,
        top_imported_modules=top_imported,
    )
