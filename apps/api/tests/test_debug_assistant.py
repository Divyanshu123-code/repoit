"""Unit and integration tests for AI Debug Assistant (P5-01).

Acceptance Criteria:
    - Finding + code + graph context -> evidence vs hypothesis sections.
    - Evidence section contains verified facts (finding, code context, graph callers).
    - Hypothesis section contains root causes, recommended fix, regression risks, verification plan.
    - Hard Rule 4: Secrets are redacted before any LLM call.
    - Hard Rule 5: Sources labelled strictly (static, graph_derived, llm_generated).
    - Hard Rule 7: All LLM interactions route strictly through LLMProvider.
"""

import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.debug_assistant import (
    DebugAnalysisRequest,
    DebugAnalysisResponse,
    DebugAssistantService,
    get_debug_assistant_service,
)
from app.ai.providers.fake_llm import FakeLLMProvider
from app.core.db import get_db_session
from app.graph.models import DependencyEdge
from app.indexing.models import CodeChunkRecord
from app.main import app
from app.repos.models import Repository
from app.static.models import StaticFinding


@pytest.mark.asyncio
async def test_debug_assistant_evidence_vs_hypothesis_separation() -> None:
    """Verify DebugAssistantService strictly separates verified evidence from AI hypotheses."""
    repo_id = uuid.uuid4()
    finding_id = uuid.uuid4()

    # 1. Mock DB Finding
    mock_finding = StaticFinding(
        id=finding_id,
        repository_id=repo_id,
        file_path="app/core/db.py",
        rule="B008",
        category="bugrisk",
        severity="warning",
        message="Do not perform function call `Depends` in argument defaults",
        line_start=42,
        line_end=42,
        column_start=25,
        column_end=35,
        fix_available=True,
        fix_message="Use Annotated or default to None",
        source="static",
    )

    # 2. Mock Code Chunk
    mock_chunk = CodeChunkRecord(
        id=uuid.uuid4(),
        repository_id=repo_id,
        file_path="app/core/db.py",
        start_line=30,
        end_line=55,
        content=(
            "def get_db_session(\n"
            "    session: AsyncSession = Depends(get_session)\n"
            ") -> AsyncSession:\n"
            "    return session\n"
        ),
        context_header="Database session dependency",
    )

    # 3. Mock Graph Edges (app/core/db.py is imported by services/user_service.py and api/routes.py)
    edge_downstream1 = DependencyEdge(
        repository_id=repo_id,
        source_file="app/services/user_service.py",
        target_file="app/core/db.py",
        is_internal=True,
        source="graph_derived",
    )
    edge_downstream2 = DependencyEdge(
        repository_id=repo_id,
        source_file="app/api/routes.py",
        target_file="app/core/db.py",
        is_internal=True,
        source="graph_derived",
    )
    # app/core/db.py imports app/core/config.py
    edge_upstream = DependencyEdge(
        repository_id=repo_id,
        source_file="app/core/db.py",
        target_file="app/core/config.py",
        is_internal=True,
        source="graph_derived",
    )

    # Setup AsyncSession Mock
    mock_session = MagicMock(spec=AsyncSession)

    async def mock_execute(stmt: Any) -> Any:
        stmt_str = str(stmt).lower()
        res_mock = MagicMock()
        if "from static_findings" in stmt_str:
            res_mock.scalar_one_or_none.return_value = mock_finding
        elif "from code_chunks" in stmt_str:
            res_mock.scalar_one_or_none.return_value = mock_chunk
        elif "dependency_edges.source_file =" in stmt_str:
            # upstream imports
            scalars_mock = MagicMock()
            scalars_mock.all.return_value = [edge_upstream]
            res_mock.scalars.return_value = scalars_mock
        elif "dependency_edges.target_file =" in stmt_str:
            # downstream dependents
            scalars_mock = MagicMock()
            scalars_mock.all.return_value = [edge_downstream1, edge_downstream2]
            res_mock.scalars.return_value = scalars_mock
        else:
            res_mock.scalar_one_or_none.return_value = None
            scalars_mock = MagicMock()
            scalars_mock.all.return_value = []
            res_mock.scalars.return_value = scalars_mock
        return res_mock

    mock_session.execute = mock_execute

    fake_llm = FakeLLMProvider(model_name="fake-gpt-4o-mini")
    service = DebugAssistantService(llm_provider=fake_llm)

    request = DebugAnalysisRequest(
        finding_id=str(finding_id),
        user_query="How do I resolve B008 while keeping dependency injection?",
    )

    response = await service.analyze_issue(
        session=mock_session,
        repository_id=repo_id,
        request=request,
    )

    # --- Verify EVIDENCE section (grounded, deterministic) ---
    assert response.source == "llm_generated"  # Hard Rule 5
    evidence = response.evidence
    assert evidence.source == "static"
    assert evidence.finding.rule == "B008"
    assert evidence.finding.source == "static"
    assert evidence.finding.line_number == 42
    assert evidence.code_context.source == "static"
    assert "get_db_session" in evidence.code_context.content

    # Graph Context
    graph_ctx = evidence.graph_context
    assert graph_ctx.source == "graph_derived"
    assert graph_ctx.upstream_imports == ["app/core/config.py"]
    assert sorted(graph_ctx.downstream_dependents) == [
        "app/api/routes.py",
        "app/services/user_service.py",
    ]
    assert graph_ctx.blast_radius_count == 2

    # Verified Facts
    assert any("B008" in fact for fact in evidence.verified_facts)
    assert any("blast radius: 2" in fact for fact in evidence.verified_facts)

    # --- Verify HYPOTHESIS section (AI synthesized) ---
    hypotheses = response.hypotheses
    assert hypotheses.source == "llm_generated"
    assert len(hypotheses.probable_root_causes) >= 1
    assert "Annotated" in hypotheses.recommended_fix or "None" in hypotheses.recommended_fix
    assert hypotheses.code_diff is not None
    assert len(hypotheses.regression_risks) >= 1
    assert len(hypotheses.verification_plan) >= 1


@pytest.mark.asyncio
async def test_debug_assistant_hard_rule_4_secret_redaction() -> None:
    """Verify that credentials and tokens in code snippets are redacted before reaching LLM."""
    repo_id = uuid.uuid4()
    mock_session = MagicMock(spec=AsyncSession)

    res_mock = MagicMock()
    res_mock.scalar_one_or_none.return_value = None
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []
    res_mock.scalars.return_value = scalars_mock
    mock_session.execute.return_value = res_mock

    fake_llm = FakeLLMProvider()
    service = DebugAssistantService(llm_provider=fake_llm)

    secret_token = "ghp_123456789012345678901234567890123456"
    request = DebugAnalysisRequest(
        file_path="app/config.py",
        line_number=10,
        rule="S105",
        message="Possible hardcoded password",
        code_snippet=f"GITHUB_TOKEN = '{secret_token}'\nAPI_KEY = 'secret123'",
        user_query=f"Is it safe to commit {secret_token}?",
    )

    await service.analyze_issue(
        session=mock_session,
        repository_id=repo_id,
        request=request,
    )

    # Inspect captured messages in FakeLLMProvider
    assert len(fake_llm.captured_messages) > 0
    sent_prompt = " ".join(m["content"] for m in fake_llm.captured_messages[-1])
    # The actual secret token must NOT be in the prompt!
    assert secret_token not in sent_prompt
    assert "[REDACTED_SECRET]" in sent_prompt or "[REDACTED_" in sent_prompt


@pytest.mark.asyncio
async def test_debug_api_endpoint() -> None:
    """Test POST /repositories/{id}/debug endpoint."""
    repo_id = uuid.uuid4()
    mock_repo = Repository(
        id=repo_id,
        full_name="org/proj",
        source="github",
        default_branch="main",
        status="ready",
    )

    mock_db = MagicMock(spec=AsyncSession)
    mock_db.get.return_value = mock_repo

    mock_service = MagicMock(spec=DebugAssistantService)
    mock_response = DebugAnalysisResponse(
        repository_id=str(repo_id),
        finding_id=None,
        evidence={
            "finding": {
                "rule": "F401",
                "category": "lint",
                "severity": "info",
                "message": "`os` imported but unused",
                "file_path": "app/main.py",
                "line_number": 1,
                "source": "static",
            },
            "code_context": {
                "file_path": "app/main.py",
                "start_line": 1,
                "end_line": 5,
                "content": "import os\nimport sys\n",
                "source": "static",
            },
            "graph_context": {
                "file_path": "app/main.py",
                "upstream_imports": [],
                "downstream_dependents": [],
                "blast_radius_count": 0,
                "source": "graph_derived",
            },
            "verified_facts": ["Unused import at line 1"],
            "source": "static",
        },
        hypotheses={
            "probable_root_causes": ["Leftover debugging import"],
            "recommended_fix": "Remove `import os`",
            "code_diff": "-import os",
            "regression_risks": ["None: isolated file"],
            "verification_plan": ["Run `ruff check app/main.py`"],
            "source": "llm_generated",
        },
        model_version="fake-gpt-4o-mini",
        source="llm_generated",
    )
    mock_service.analyze_issue.return_value = mock_response

    async def override_get_db_session() -> Any:
        yield mock_db

    def override_get_debug_service() -> DebugAssistantService:
        return mock_service

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_debug_assistant_service] = override_get_debug_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/repositories/{repo_id}/debug",
                json={
                    "file_path": "app/main.py",
                    "line_number": 1,
                    "rule": "F401",
                    "message": "Unused import",
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["source"] == "llm_generated"
            assert data["evidence"]["source"] == "static"
            assert data["evidence"]["finding"]["rule"] == "F401"
            assert data["evidence"]["graph_context"]["source"] == "graph_derived"
            assert data["hypotheses"]["source"] == "llm_generated"
            assert data["hypotheses"]["recommended_fix"] == "Remove `import os`"

            # Test 404 on missing repo
            mock_db.get.return_value = None
            bad_resp = await client.post(
                f"/repositories/{uuid.uuid4()}/debug",
                json={"file_path": "missing.py"},
            )
            assert bad_resp.status_code == 404
    finally:
        app.dependency_overrides.clear()
