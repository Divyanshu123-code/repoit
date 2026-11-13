"""Root End-to-End Pipeline Verification Suite (P5-05).

Verifies end-to-end coherence across all phases:
    Phase 1: Ingestion, AST parsing, radon metrics
    Phase 2: Code chunking, semantic retrieval, RAG citations
    Phase 3: Machine learning defect risk prediction with model version & disclaimers
    Phase 4: Import graph modeling and change impact reverse reachability
    Phase 5: AI debug assistant, test generation, and Docker sandbox execution
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import networkx as nx
import pytest
from app.ai.providers.fake_llm import FakeLLMProvider
from app.ai.rag_service import RAGService
from app.graph.impact import analyze_change_impact
from app.indexing.chunker import chunk_python_source
from app.indexing.models import SearchResultItem
from app.indexing.search_service import SemanticSearchService
from app.ml.inference_service import DefectInferenceService
from app.parsing.metrics import compute_repository_metrics
from app.parsing.parser import TreeSitterPythonParser
from app.tests_gen.models import GeneratedTest
from app.tests_gen.sandbox import DockerSandboxRunner


def test_phase1_ingestion_ast_and_metrics() -> None:
    """Verify Phase 1 AST extraction and metric calculation pipeline."""
    sample_code = (
        "def calculate_total(prices: list[float]) -> float:\n"
        '    """Calculate sum of prices."""\n'
        "    total = 0.0\n"
        "    for p in prices:\n"
        "        if p > 0:\n"
        "            total += p\n"
        "    return total\n"
    )

    parser = TreeSitterPythonParser()
    ast_result = parser.parse_source(sample_code, file_path="app/math.py")
    assert len(ast_result.symbols) == 1
    assert ast_result.symbols[0].name == "calculate_total"
    assert ast_result.symbols[0].symbol_type == "function"

    metrics = compute_repository_metrics(
        modules_code={"app/math.py": sample_code},
        modules_imports={"app/math.py": []},
    )
    assert metrics.total_loc >= 7
    assert metrics.avg_cyclomatic_complexity >= 2.0


@pytest.mark.asyncio
async def test_phase2_chunking_search_and_rag() -> None:
    """Verify Phase 2 chunking and RAG citation pipeline."""
    sample_code = (
        "def authenticate_user(token: str) -> bool:\n"
        '    """Authenticate token."""\n'
        "    return token == 'valid_token'\n"
    )
    chunks = chunk_python_source(sample_code, file_path="app/auth.py")
    assert len(chunks) == 1
    assert chunks[0].symbol_name == "authenticate_user"

    mock_search = MagicMock(spec=SemanticSearchService)
    mock_search.search = AsyncMock(
        return_value=[
            SearchResultItem(
                id=uuid.uuid4(),
                path="app/auth.py",
                start_line=1,
                end_line=3,
                content=sample_code,
                symbol_name="authenticate_user",
                score=0.88,
            )
        ]
    )

    fake_llm = FakeLLMProvider()
    rag = RAGService(search_service=mock_search, llm_provider=fake_llm)

    mock_session = MagicMock()
    ans = await rag.answer_question(
        db=mock_session,
        repository_id=uuid.uuid4(),
        question="How is authentication handled?",
    )
    assert ans.source == "llm_generated"
    assert not ans.abstained
    assert len(ans.citations) == 1
    assert ans.citations[0].source == "static"
    assert ans.citations[0].file_path == "app/auth.py"


def test_phase3_ml_defect_risk_inference() -> None:
    """Verify Phase 3 defect prediction enforces Rule 5 and Rule 6."""
    service = DefectInferenceService()
    sample_code = (
        "def complex_function(a, b, c):\n"
        "    if a: return b\n"
        "    elif b: return c\n"
        "    else: return a\n"
    )
    pred = service.predict_source_code(sample_code)
    assert 0.0 <= pred["risk_probability"] <= 1.0
    assert pred["risk_band"] in ("low", "medium", "high")
    assert pred["source"] == "ml_predicted"
    assert "risk estimates" in pred["disclaimer"].lower()
    assert pred["model_version"] is not None


def test_phase4_dependency_graph_and_impact() -> None:
    """Verify Phase 4 import graph and change impact engine."""
    g = nx.DiGraph()
    # A depends on B (B changed -> A affected)
    g.add_edge("app/service.py", "app/database.py")
    g.add_edge("app/api.py", "app/service.py")

    impact = analyze_change_impact(
        repository_id="repo-123",
        graph=g,
        changed_files=["app/database.py"],
        max_depth=3,
        include_changed=False,
    )

    assert impact.source == "graph_derived"
    assert impact.total_affected_count == 2
    paths = [item.file_path for item in impact.affected_files]
    assert "app/service.py" in paths
    assert "app/api.py" in paths


@pytest.mark.asyncio
async def test_phase5_test_generation_and_sandbox_execution() -> None:
    """Verify Phase 5 test generation and Docker sandbox execution."""
    test_record = GeneratedTest(
        target_file="app/math.py",
        test_name="test_math_calc",
        test_code="def test_math_calc(): assert 5 * 5 == 25\n",
        test_file_path="tests/test_math.py",
        status="unvalidated",
        source="llm_generated",
    )
    assert test_record.status == "unvalidated"
    assert test_record.source == "llm_generated"

    runner = DockerSandboxRunner()
    with patch.object(runner, "is_docker_available", return_value=False):
        result = await runner.run_test(
            test_code=test_record.test_code,
            test_file_path=test_record.test_file_path,
        )
        assert result.status == "passed"
        assert result.exit_code == 0
        assert result.runner_type == "isolated_process"
