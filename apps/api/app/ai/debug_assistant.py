"""AI Debug Assistant service (P5-01).

Correlates:
    Static Finding (Ruff) + Code Context (AST/Chunks) + Graph Context (NetworkX)
Into strictly separated:
    - EVIDENCE section (ground truth: finding, code snippet, graph callers/importers)
    - HYPOTHESIS section (probable root causes, recommended fix, regression risks, verification plan)

Strictly enforces:
    - Hard Rule 4: Never log or send secrets/tokens. Redact before LLM calls.
    - Hard Rule 5: Every result labelled by source (static, graph_derived, llm_generated).
    - Hard Rule 7: LLM calls go ONLY through app.ai.providers interfaces.
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.base import LLMProvider
from app.ai.providers.factory import get_llm_provider
from app.ai.redaction import redact_secrets
from app.graph.models import DependencyEdge
from app.indexing.models import CodeChunkRecord
from app.static.models import StaticFinding

logger = logging.getLogger("repopilot.ai.debug")


# --- Schemas ---


class FindingContext(BaseModel):
    """Normalized static finding context.

    Enforces Hard Rule 5: source labelled strictly as 'static'.
    """

    finding_id: str | None = None
    rule: str
    category: str = "lint"
    severity: str = "warning"
    message: str
    file_path: str
    line_number: int
    column_number: int | None = None
    fix_suggested: str | None = None
    source: Literal["static"] = "static"


class CodeContext(BaseModel):
    """Source code context enclosing the finding.

    Enforces Hard Rule 5: source labelled strictly as 'static'.
    """

    file_path: str
    start_line: int
    end_line: int
    content: str
    symbol_name: str | None = None
    source: Literal["static"] = "static"


class GraphContext(BaseModel):
    """Import graph topology and caller context.

    Enforces Hard Rule 5: source labelled strictly as 'graph_derived'.
    """

    file_path: str
    upstream_imports: list[str] = Field(
        default_factory=list,
        description="Modules/files imported by this file",
    )
    downstream_dependents: list[str] = Field(
        default_factory=list,
        description="Modules/files that import this file (blast radius)",
    )
    blast_radius_count: int = 0
    source: Literal["graph_derived"] = "graph_derived"


class EvidenceSection(BaseModel):
    """Deterministic, verified ground truth directly observed from code and graph.

    Enforces Hard Rule 5: source labelled strictly as 'static'.
    """

    finding: FindingContext
    code_context: CodeContext
    graph_context: GraphContext
    verified_facts: list[str] = Field(
        default_factory=list,
        description="Direct observations grounded in static analysis and dependency graph",
    )
    source: Literal["static"] = "static"


class HypothesisSection(BaseModel):
    """AI-synthesized diagnostic hypotheses and resolution recommendations.

    Enforces Hard Rule 5: source labelled strictly as 'llm_generated'.
    """

    probable_root_causes: list[str] = Field(
        default_factory=list,
        description="Hypotheses explaining why this issue exists in the codebase",
    )
    recommended_fix: str = Field(description="Step-by-step resolution guidance")
    code_diff: str | None = Field(
        default=None,
        description="Suggested replacement code or patch",
    )
    regression_risks: list[str] = Field(
        default_factory=list,
        description="Downstream caller risks derived from graph context",
    )
    verification_plan: list[str] = Field(
        default_factory=list,
        description="Concrete tests and checks to verify resolution",
    )
    source: Literal["llm_generated"] = "llm_generated"


class DebugAnalysisResponse(BaseModel):
    """Complete debug diagnosis response separating evidence from hypotheses.

    Enforces Hard Rule 5: source labelled strictly as 'llm_generated'.
    """

    repository_id: str
    finding_id: str | None = None
    evidence: EvidenceSection
    hypotheses: HypothesisSection
    model_version: str
    source: Literal["llm_generated"] = "llm_generated"


class DebugAnalysisRequest(BaseModel):
    """Input parameters for AI debug assistance."""

    finding_id: str | None = Field(
        default=None,
        description="UUID of existing StaticFinding record",
    )
    file_path: str | None = Field(
        default=None,
        description="File path if running ad-hoc debug analysis",
    )
    line_number: int | None = Field(
        default=None,
        description="Line number where issue occurs",
    )
    rule: str | None = Field(
        default=None,
        description="Static rule code (e.g., 'B008', 'F401', 'S101')",
    )
    message: str | None = Field(
        default=None,
        description="Description of the bug or static finding",
    )
    code_snippet: str | None = Field(
        default=None,
        description="Optional explicit code context",
    )
    user_query: str | None = Field(
        default=None,
        description="Specific question or direction from developer",
    )


# --- Service ---


class DebugAssistantService:
    """Orchestrates multi-modal code debugging combining static findings, code, and graph context."""

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self.llm_provider = llm_provider or get_llm_provider()

    async def analyze_issue(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        request: DebugAnalysisRequest,
    ) -> DebugAnalysisResponse:
        """Execute debug investigation separating verified evidence from LLM hypotheses."""
        # 1. Gather Finding Context
        finding_ctx = await self._resolve_finding_context(session, repository_id, request)

        # 2. Gather Code Context
        code_ctx = await self._resolve_code_context(
            session, repository_id, finding_ctx, request.code_snippet
        )

        # 3. Gather Graph Context
        graph_ctx = await self._resolve_graph_context(session, repository_id, finding_ctx.file_path)

        # 4. Formulate Verified Evidence Facts
        verified_facts = [
            f"Rule {finding_ctx.rule} ({finding_ctx.severity}): {finding_ctx.message} at line {finding_ctx.line_number}",
            f"File '{finding_ctx.file_path}' has {len(graph_ctx.upstream_imports)} upstream imports",
            f"File '{finding_ctx.file_path}' is imported by {len(graph_ctx.downstream_dependents)} downstream modules (blast radius: {graph_ctx.blast_radius_count})",
        ]
        if finding_ctx.fix_suggested:
            verified_facts.append(f"Static tool suggested quick fix: {finding_ctx.fix_suggested}")

        evidence = EvidenceSection(
            finding=finding_ctx,
            code_context=code_ctx,
            graph_context=graph_ctx,
            verified_facts=verified_facts,
            source="static",  # Hard Rule 5
        )

        # 5. Redact Secrets before LLM Call (Hard Rule 4)
        clean_code = redact_secrets(code_ctx.content)
        clean_query = redact_secrets(request.user_query or "")

        # 6. Build Prompt for Evidence vs Hypothesis
        messages = self._build_prompt(evidence, clean_code, clean_query)

        # 7. Generate LLM Completion (Hard Rule 7)
        completion = await self.llm_provider.generate_completion(
            messages, temperature=0.1, max_tokens=1500
        )

        # 8. Parse into Structured Hypothesis Section
        hypotheses = self._parse_hypotheses(completion, graph_ctx)

        return DebugAnalysisResponse(
            repository_id=str(repository_id),
            finding_id=finding_ctx.finding_id,
            evidence=evidence,
            hypotheses=hypotheses,
            model_version=self.llm_provider.model_name,
            source="llm_generated",  # Hard Rule 5
        )

    async def _resolve_finding_context(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        request: DebugAnalysisRequest,
    ) -> FindingContext:
        """Retrieve finding from database or synthesize from ad-hoc input."""
        if request.finding_id:
            try:
                fid = uuid.UUID(request.finding_id)
                stmt = select(StaticFinding).where(
                    StaticFinding.id == fid,
                    StaticFinding.repository_id == repository_id,
                )
                res = await session.execute(stmt)
                db_finding = res.scalar_one_or_none()
                if db_finding:
                    return FindingContext(
                        finding_id=str(db_finding.id),
                        rule=db_finding.rule,
                        category=db_finding.category,
                        severity=db_finding.severity,
                        message=db_finding.message,
                        file_path=db_finding.file_path,
                        line_number=db_finding.line_start,
                        column_number=db_finding.column_start,
                        fix_suggested=db_finding.fix_message,
                        source="static",
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not load finding_id '%s': %s", request.finding_id, exc)

        # Fallback to ad-hoc input
        return FindingContext(
            finding_id=request.finding_id,
            rule=request.rule or "UNKNOWN",
            category="lint",
            severity="warning",
            message=request.message or "Code quality or bugrisk issue",
            file_path=request.file_path or "app/main.py",
            line_number=request.line_number or 1,
            column_number=None,
            fix_suggested=None,
            source="static",
        )

    async def _resolve_code_context(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        finding: FindingContext,
        custom_snippet: str | None,
    ) -> CodeContext:
        """Fetch surrounding code chunk from database or use provided snippet."""
        if custom_snippet and custom_snippet.strip():
            lines = custom_snippet.strip().splitlines()
            start = max(1, finding.line_number - 2)
            end = start + len(lines) - 1
            return CodeContext(
                file_path=finding.file_path,
                start_line=start,
                end_line=end,
                content=custom_snippet.strip(),
                source="static",
            )

        # Query code_chunks table
        stmt = (
            select(CodeChunkRecord)
            .where(
                CodeChunkRecord.repository_id == repository_id,
                CodeChunkRecord.file_path == finding.file_path,
                CodeChunkRecord.start_line <= finding.line_number,
                CodeChunkRecord.end_line >= finding.line_number,
            )
            .limit(1)
        )
        res = await session.execute(stmt)
        chunk = res.scalar_one_or_none()
        if chunk:
            return CodeContext(
                file_path=chunk.file_path,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                content=chunk.content,
                source="static",
            )

        # Fallback generic snippet
        fallback_content = f"# Context around line {finding.line_number} of {finding.file_path}\n# Finding: {finding.rule} - {finding.message}"
        return CodeContext(
            file_path=finding.file_path,
            start_line=max(1, finding.line_number - 5),
            end_line=finding.line_number + 5,
            content=fallback_content,
            source="static",
        )

    async def _resolve_graph_context(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        file_path: str,
    ) -> GraphContext:
        """Query import graph edges to determine upstream dependencies and downstream callers."""
        # 1. Upstream imports (what file_path imports)
        up_stmt = select(DependencyEdge).where(
            DependencyEdge.repository_id == repository_id,
            DependencyEdge.source_file == file_path,
            DependencyEdge.is_internal.is_(True),
        )
        up_res = await session.execute(up_stmt)
        up_edges = up_res.scalars().all()
        upstream = sorted(
            {e.target_file or e.target_module for e in up_edges if e.target_file or e.target_module}
        )

        # 2. Downstream callers/consumers (who imports file_path)
        down_stmt = select(DependencyEdge).where(
            DependencyEdge.repository_id == repository_id,
            DependencyEdge.target_file == file_path,
            DependencyEdge.is_internal.is_(True),
        )
        down_res = await session.execute(down_stmt)
        down_edges = down_res.scalars().all()
        downstream = sorted({e.source_file for e in down_edges if e.source_file})

        return GraphContext(
            file_path=file_path,
            upstream_imports=upstream,
            downstream_dependents=downstream,
            blast_radius_count=len(downstream),
            source="graph_derived",  # Hard Rule 5
        )

    def _build_prompt(
        self,
        evidence: EvidenceSection,
        clean_code: str,
        user_query: str,
    ) -> list[dict[str, str]]:
        """Construct structured prompt enforcing evidence grounding and hypothesis generation."""
        system_prompt = (
            "You are RepoPilot AI's Senior Debugging Assistant. "
            "Analyze the reported static finding and code context using the repository's dependency graph. "
            "You must strictly separate verified facts (EVIDENCE) from your diagnostic reasoning (HYPOTHESES). "
            "Format your response with the following explicit section headers:\n\n"
            "PROBABLE ROOT CAUSES:\n"
            "- <Hypothesis 1>\n"
            "- <Hypothesis 2>\n\n"
            "RECOMMENDED FIX:\n"
            "<Clear step-by-step resolution>\n\n"
            "CODE DIFF:\n"
            "```python\n"
            "<Proposed code patch or fix snippet>\n"
            "```\n\n"
            "REGRESSION RISKS:\n"
            "- <Risk to downstream callers or consumers based on the dependency graph>\n\n"
            "VERIFICATION PLAN:\n"
            "- <Concrete test or validation command to verify the fix>\n"
        )

        upstream_str = ", ".join(evidence.graph_context.upstream_imports) or "None"
        downstream_str = (
            ", ".join(evidence.graph_context.downstream_dependents)
            or "None (isolated blast radius)"
        )

        user_content = (
            f"=== VERIFIED EVIDENCE ===\n"
            f"File: {evidence.finding.file_path}:{evidence.finding.line_number}\n"
            f"Rule: {evidence.finding.rule} ({evidence.finding.severity})\n"
            f"Message: {evidence.finding.message}\n"
            f"Upstream Dependencies: {upstream_str}\n"
            f"Downstream Callers (Blast Radius: {evidence.graph_context.blast_radius_count}): {downstream_str}\n\n"
            f"=== CODE CONTEXT (Lines {evidence.code_context.start_line}-{evidence.code_context.end_line}) ===\n"
            f"```python\n{clean_code}\n```\n\n"
        )
        if user_query:
            user_content += f"Developer Inquiry: {user_query}\n\n"

        user_content += "Please provide the complete root cause analysis, recommended fix, code diff, regression risks, and verification plan."

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

    def _parse_hypotheses(
        self,
        completion: str,
        graph_ctx: GraphContext,
    ) -> HypothesisSection:
        """Parse LLM completion into structured HypothesisSection."""
        root_causes: list[str] = []
        recommended_fix = ""
        code_diff: str | None = None
        regression_risks: list[str] = []
        verification_plan: list[str] = []

        # 1. Extract Code Diff if present
        diff_match = re.search(r"```(?:python|diff)?\s*\n([\s\S]*?)\n```", completion)
        if diff_match:
            code_diff = diff_match.group(1).strip()

        # 2. Extract sections using regex
        rc_match = re.search(
            r"PROBABLE ROOT CAUSES:?\s*\n(.*?)(?=\n[A-Z\s]{4,}:|\Z)",
            completion,
            re.DOTALL | re.IGNORECASE,
        )
        if rc_match:
            raw_rc = rc_match.group(1).strip()
            root_causes = [
                line.lstrip("-*• 0123456789.)").strip()
                for line in raw_rc.splitlines()
                if line.strip() and not line.strip().startswith("```")
            ]

        fix_match = re.search(
            r"RECOMMENDED FIX:?\s*\n(.*?)(?=\n[A-Z\s]{4,}:|\Z)",
            completion,
            re.DOTALL | re.IGNORECASE,
        )
        if fix_match:
            recommended_fix = fix_match.group(1).strip()
            # Remove any raw code fence if captured in fix description
            recommended_fix = re.sub(r"```[\s\S]*?```", "", recommended_fix).strip()

        risks_match = re.search(
            r"REGRESSION RISKS:?\s*\n(.*?)(?=\n[A-Z\s]{4,}:|\Z)",
            completion,
            re.DOTALL | re.IGNORECASE,
        )
        if risks_match:
            raw_risks = risks_match.group(1).strip()
            regression_risks = [
                line.lstrip("-*• 0123456789.)").strip()
                for line in raw_risks.splitlines()
                if line.strip() and not line.strip().startswith("```")
            ]

        plan_match = re.search(
            r"VERIFICATION PLAN:?\s*\n(.*?)(?=\n[A-Z\s]{4,}:|\Z)",
            completion,
            re.DOTALL | re.IGNORECASE,
        )
        if plan_match:
            raw_plan = plan_match.group(1).strip()
            verification_plan = [
                line.lstrip("-*• 0123456789.)").strip()
                for line in raw_plan.splitlines()
                if line.strip() and not line.strip().startswith("```")
            ]

        # Defaults if LLM returned unstructured text
        if not root_causes:
            root_causes = [
                "Issue caused by non-idiomatic or risky code construct at the indicated line."
            ]
        if not recommended_fix:
            recommended_fix = completion.strip()
        if not regression_risks:
            if graph_ctx.downstream_dependents:
                regression_risks = [
                    f"Modifying signature or return types could affect downstream callers: {', '.join(graph_ctx.downstream_dependents[:3])}"
                ]
            else:
                regression_risks = [
                    "Low regression risk: module has no internal downstream dependents."
                ]
        if not verification_plan:
            verification_plan = [
                "Run static linter to confirm finding resolution: `ruff check <file>`",
                "Execute test suite to verify no regressions: `pytest -q`",
            ]

        return HypothesisSection(
            probable_root_causes=root_causes,
            recommended_fix=recommended_fix,
            code_diff=code_diff,
            regression_risks=regression_risks,
            verification_plan=verification_plan,
            source="llm_generated",  # Hard Rule 5
        )


_debug_service: DebugAssistantService | None = None


def get_debug_assistant_service() -> DebugAssistantService:
    """Provide singleton instance of DebugAssistantService."""
    global _debug_service
    if _debug_service is None:
        _debug_service = DebugAssistantService()
    return _debug_service
