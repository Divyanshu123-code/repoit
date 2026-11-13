"""Service for AI test generation and persistence (P5-02).

Synthesizes pytest unit and regression test cases from code chunks, AST symbols,
and static findings. Stores records in generated_tests with status 'unvalidated' (P5-02)
prior to execution in the Docker sandbox runner (P5-03).

Enforces:
    - Hard Rule 3: Untrusted code - generated tests are saved as unvalidated text, never executed locally.
    - Hard Rule 4: Secret and token redaction before any LLM prompt.
    - Hard Rule 5: Labelled strictly with source: 'llm_generated'.
    - Hard Rule 7: LLM calls route exclusively through LLMProvider.
"""

from __future__ import annotations

import logging
import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers import LLMProvider, get_llm_provider
from app.ai.redaction import redact_secrets
from app.indexing.models import CodeChunkRecord
from app.static.models import StaticFinding
from app.tests_gen.models import GeneratedTest
from app.tests_gen.schemas import (
    GeneratedTestListResponse,
    GeneratedTestResponse,
    GenerateTestRequest,
)

logger = logging.getLogger("repopilot.tests_gen.service")


class TestGenerationService:
    """Orchestrates test case synthesis, parsing, and database persistence."""

    __test__ = False

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self.llm_provider = llm_provider or get_llm_provider()

    async def generate_and_store_test(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        request: GenerateTestRequest,
    ) -> GeneratedTest:
        """Generate a pytest test case via LLM and persist with status 'unvalidated'."""
        # 1. Fetch Code Context
        code_context = await self._gather_code_context(session, repository_id, request)

        # 2. Fetch Finding Context if requested
        finding_info: dict[str, str] | None = None
        if request.finding_id:
            finding_info = await self._gather_finding_context(
                session, repository_id, request.finding_id
            )

        # 3. Redact Secrets (Hard Rule 4)
        clean_code = redact_secrets(code_context)
        clean_focus = redact_secrets(request.focus_description or "")

        # 4. Construct Prompt
        messages = self._build_prompt(
            target_file=request.target_file,
            target_symbol=request.target_symbol,
            test_type=request.test_type,
            clean_code=clean_code,
            clean_focus=clean_focus,
            finding_info=finding_info,
        )

        # 5. Call LLMProvider (Hard Rule 7)
        completion = await self.llm_provider.generate_completion(
            messages, temperature=0.1, max_tokens=1500
        )

        # 6. Parse Test Name, Code, and Target File Path
        test_name, test_code, test_file_path = self._extract_test_details(
            completion=completion,
            target_file=request.target_file,
            target_symbol=request.target_symbol,
        )

        # 7. Persist to generated_tests table with status 'unvalidated' (AC!)
        generated_test = GeneratedTest(
            repository_id=repository_id,
            target_file=request.target_file,
            target_symbol=request.target_symbol,
            finding_id=uuid.UUID(request.finding_id) if request.finding_id else None,
            test_framework="pytest",
            test_name=test_name,
            test_code=test_code,
            test_file_path=test_file_path,
            status="unvalidated",  # Hard requirement P5-02
            error_message=None,
            execution_output=None,
            execution_duration_ms=None,
            source="llm_generated",  # Hard Rule 5
            model_version=self.llm_provider.model_name,
        )

        session.add(generated_test)
        await session.commit()
        await session.refresh(generated_test)

        logger.info(
            "Synthesized and stored test %s for repository %s (status=%s)",
            generated_test.test_name,
            repository_id,
            generated_test.status,
        )

        return generated_test

    async def list_tests(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        status_filter: str | None = None,
        target_file: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> GeneratedTestListResponse:
        """Query generated tests with summary metrics."""
        stmt = (
            select(GeneratedTest)
            .where(GeneratedTest.repository_id == repository_id)
            .order_by(GeneratedTest.created_at.desc())
        )
        if status_filter:
            stmt = stmt.where(GeneratedTest.status == status_filter)
        if target_file:
            stmt = stmt.where(GeneratedTest.target_file == target_file)

        stmt = stmt.limit(limit).offset(offset)
        result = await session.execute(stmt)
        records = result.scalars().all()

        # Count metrics
        count_stmt = select(
            func.count().label("total"),
            func.count().filter(GeneratedTest.status == "unvalidated").label("unvalidated"),
            func.count().filter(GeneratedTest.status == "passed").label("passed"),
            func.count().filter(GeneratedTest.status == "failed").label("failed"),
        ).where(GeneratedTest.repository_id == repository_id)
        count_res = await session.execute(count_stmt)
        total, unvalidated, passed, failed = count_res.one()

        items = [self.to_response(r) for r in records]

        return GeneratedTestListResponse(
            repository_id=str(repository_id),
            total_count=int(total or 0),
            unvalidated_count=int(unvalidated or 0),
            passed_count=int(passed or 0),
            failed_count=int(failed or 0),
            source="llm_generated",  # Hard Rule 5
            tests=items,
        )

    async def get_test(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        test_id: uuid.UUID,
    ) -> GeneratedTest | None:
        """Retrieve single generated test record."""
        stmt = select(GeneratedTest).where(
            GeneratedTest.id == test_id,
            GeneratedTest.repository_id == repository_id,
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    def to_response(self, record: GeneratedTest) -> GeneratedTestResponse:
        """Map entity to Pydantic response."""
        return GeneratedTestResponse(
            id=str(record.id),
            repository_id=str(record.repository_id),
            target_file=record.target_file,
            target_symbol=record.target_symbol,
            finding_id=str(record.finding_id) if record.finding_id else None,
            test_framework=record.test_framework,
            test_name=record.test_name,
            test_code=record.test_code,
            test_file_path=record.test_file_path,
            status=record.status,
            error_message=record.error_message,
            execution_output=record.execution_output,
            execution_duration_ms=record.execution_duration_ms,
            source="llm_generated",  # Hard Rule 5
            model_version=record.model_version,
            created_at=record.created_at.isoformat(),
            updated_at=record.updated_at.isoformat(),
        )

    async def _gather_code_context(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        request: GenerateTestRequest,
    ) -> str:
        """Gather source code for target file/symbol."""
        if request.custom_code_snippet and request.custom_code_snippet.strip():
            return request.custom_code_snippet.strip()

        # Query code chunks
        stmt = select(CodeChunkRecord).where(
            CodeChunkRecord.repository_id == repository_id,
            CodeChunkRecord.file_path == request.target_file,
        )
        res = await session.execute(stmt)
        chunks = res.scalars().all()
        if chunks:
            # If target_symbol is specified, find chunk containing it
            if request.target_symbol:
                for c in chunks:
                    if request.target_symbol in c.content:
                        return c.content
            return "\n\n".join(c.content for c in chunks[:3])

        return f"# Code context for {request.target_file}\n# Target symbol: {request.target_symbol or 'module'}"

    async def _gather_finding_context(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        finding_id_str: str,
    ) -> dict[str, str] | None:
        """Fetch static finding details to tailor regression test."""
        try:
            fid = uuid.UUID(finding_id_str)
            stmt = select(StaticFinding).where(
                StaticFinding.id == fid,
                StaticFinding.repository_id == repository_id,
            )
            res = await session.execute(stmt)
            finding = res.scalar_one_or_none()
            if finding:
                return {
                    "rule": finding.rule,
                    "severity": finding.severity,
                    "message": finding.message,
                    "line": str(finding.line_start),
                    "fix_message": finding.fix_message or "",
                }
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not gather finding context for %s: %s", finding_id_str, exc)
        return None

    def _build_prompt(
        self,
        target_file: str,
        target_symbol: str | None,
        test_type: str,
        clean_code: str,
        clean_focus: str,
        finding_info: dict[str, str] | None,
    ) -> list[dict[str, str]]:
        """Assemble structured prompt requesting standalone pytest test code."""
        system_prompt = (
            "You are RepoPilot AI's Expert Test Generation Agent. "
            "Generate an isolated, robust, executable pytest test function for the specified Python module. "
            "Follow these strict conventions:\n"
            "1. Output ONLY a valid Python code block with markdown fences (```python ... ```).\n"
            "2. Use pytest standard conventions (assert statements, fixtures, pytest.raises).\n"
            "3. Cover happy path, edge cases, and boundary validations.\n"
            "4. Include a concise, descriptive test function name (e.g. test_<symbol>_<scenario>).\n"
            "5. The test must be completely standalone; do not include explanatory chatter outside the code block."
        )

        user_content = (
            f"Target File: {target_file}\n"
            f"Target Symbol: {target_symbol or 'Entire Module'}\n"
            f"Test Type: {test_type}\n"
        )
        if clean_focus:
            user_content += f"Focus / Objective: {clean_focus}\n"
        if finding_info:
            user_content += (
                f"Regression Target Finding: Rule {finding_info['rule']} at line {finding_info['line']}: "
                f"{finding_info['message']}\n"
            )

        user_content += f"\n=== SOURCE CODE UNDER TEST ===\n```python\n{clean_code}\n```\n"

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

    def _extract_test_details(
        self,
        completion: str,
        target_file: str,
        target_symbol: str | None,
    ) -> tuple[str, str, str]:
        """Extract test code, test function name, and proposed test file path."""
        code_match = re.search(r"```(?:python)?\s*\n([\s\S]*?)\n```", completion)
        if code_match:
            test_code = code_match.group(1).strip()
        else:
            test_code = completion.strip()

        # Extract function name
        fn_match = re.search(r"def\s+(test_[a-zA-Z0-9_]+)\s*\(", test_code)
        if fn_match:
            test_name = fn_match.group(1)
        else:
            sym_part = target_symbol.lower() if target_symbol else "module"
            clean_sym = re.sub(r"[^a-zA-Z0-9_]", "_", sym_part)
            test_name = f"test_{clean_sym}_behavior"

        # Derive proposed test file path
        # e.g. "app/repos/filter.py" -> "tests/generated/test_filter.py"
        base_name = target_file.split("/")[-1]
        base_name = base_name.removesuffix(".py")
        if not base_name.startswith("test_"):
            test_file_path = f"tests/generated/test_{base_name}.py"
        else:
            test_file_path = f"tests/generated/{base_name}.py"

        return test_name, test_code, test_file_path


_test_gen_service: TestGenerationService | None = None


def get_test_generation_service() -> TestGenerationService:
    """Provide singleton instance of TestGenerationService."""
    global _test_gen_service
    if _test_gen_service is None:
        _test_gen_service = TestGenerationService()
    return _test_gen_service
