"""Root verification tests for AI Debug Assistant (P5-01).

Acceptance Criteria:
    - Debug assistant correlates finding + code + graph context.
    - Strictly separates EVIDENCE vs HYPOTHESIS sections.
    - Enforces Hard Rule 5 source labels: static, graph_derived, llm_generated.
"""

from app.ai.debug_assistant import (
    CodeContext,
    DebugAnalysisRequest,
    DebugAnalysisResponse,
    EvidenceSection,
    FindingContext,
    GraphContext,
    HypothesisSection,
)


def test_debug_assistant_models_and_rule_5() -> None:
    """Verify Debug Assistant data models enforce separation and Hard Rule 5 labels."""
    finding = FindingContext(
        rule="B008",
        message="Do not perform function call in argument defaults",
        file_path="app/core/db.py",
        line_number=42,
    )
    assert finding.source == "static"

    code = CodeContext(
        file_path="app/core/db.py",
        start_line=40,
        end_line=45,
        content="def get_db(session=Depends(get_session)):",
    )
    assert code.source == "static"

    graph = GraphContext(
        file_path="app/core/db.py",
        upstream_imports=["app/core/config.py"],
        downstream_dependents=["app/api/routes.py"],
        blast_radius_count=1,
    )
    assert graph.source == "graph_derived"

    evidence = EvidenceSection(
        finding=finding,
        code_context=code,
        graph_context=graph,
        verified_facts=["Observed B008 warning", "1 downstream caller affected"],
    )
    assert evidence.source == "static"

    hypotheses = HypothesisSection(
        probable_root_causes=["FastAPI Depends called inside signature default"],
        recommended_fix="Use Annotated[Session, Depends(get_session)]",
        code_diff="-def get_db(session=Depends()):\n+def get_db(session: Annotated[Session, Depends()]):",
        regression_risks=[
            "Downstream callers in app/api/routes.py must not pass positional args"
        ],
        verification_plan=["Run ruff check app/core/db.py", "Run pytest tests/"],
    )
    assert hypotheses.source == "llm_generated"

    response = DebugAnalysisResponse(
        repository_id="repo-123",
        evidence=evidence,
        hypotheses=hypotheses,
        model_version="gpt-4o-mini",
    )
    assert response.source == "llm_generated"
    assert response.evidence.finding.rule == "B008"
    assert response.evidence.graph_context.blast_radius_count == 1
    assert "Annotated" in response.hypotheses.recommended_fix


def test_debug_request_schema() -> None:
    """Verify DebugAnalysisRequest handles optional fields gracefully."""
    req = DebugAnalysisRequest(
        file_path="app/main.py",
        line_number=10,
        rule="S101",
        message="Use of assert detected",
    )
    assert req.file_path == "app/main.py"
    assert req.rule == "S101"
    assert req.finding_id is None
