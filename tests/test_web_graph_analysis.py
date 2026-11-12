"""Tests for Graph UI (select node -> affected set) and Findings Table with triage filter (P4-04).

Acceptance Criteria:
    - Route /repositories/:id/graph configured in App.tsx.
    - GraphAnalysisPage component renders graph topology, node selection, and impact analysis.
    - Reverse reachability affected set displayed upon selecting a node.
    - Findings table with severity tabs and triage status filtering.
    - Rule 5 compliance: labelled strictly with 'source: graph_derived' and 'source: static'.
    - Navigation link present on RepoOverviewPage.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = REPO_ROOT / "apps" / "web"


def test_graph_analysis_route_configured() -> None:
    """Ensure App.tsx registers the route for /repositories/:id/graph."""
    app_tsx = (WEB_DIR / "src" / "App.tsx").read_text(encoding="utf-8")
    assert "/repositories/:id/graph" in app_tsx
    assert "GraphAnalysisPage" in app_tsx


def test_repo_overview_has_graph_navigation_button() -> None:
    """Ensure RepoOverviewPage has a direct navigation link to Graph & Findings."""
    overview_tsx = (WEB_DIR / "src" / "pages" / "RepoOverviewPage.tsx").read_text(
        encoding="utf-8"
    )
    assert "/graph" in overview_tsx
    assert "Graph & Findings" in overview_tsx


def test_api_client_has_graph_and_findings_methods() -> None:
    """Ensure client.ts exports all required API calls for graph, impact, and static findings."""
    client_ts = (WEB_DIR / "src" / "api" / "client.ts").read_text(encoding="utf-8")
    assert "fetchRepositoryGraph" in client_ts
    assert "fetchChangeImpact" in client_ts
    assert "triggerRebuildGraph" in client_ts
    assert "fetchStaticFindings" in client_ts
    assert "triggerStaticScan" in client_ts
    assert 'source: "graph_derived"' in client_ts
    assert 'source: "static"' in client_ts


def test_graph_analysis_page_rule_5_and_features() -> None:
    """Ensure GraphAnalysisPage contains node selection, impact analysis, and triage table."""
    page_tsx = (WEB_DIR / "src" / "pages" / "GraphAnalysisPage.tsx").read_text(
        encoding="utf-8"
    )

    # 1. Hard Rule 5 labels
    assert "source: graph_derived" in page_tsx
    assert "source: static" in page_tsx

    # 2. Graph & Node Selection
    assert "selectedNode" in page_tsx
    assert "setSelectedNode" in page_tsx
    assert "fetchChangeImpact" in page_tsx
    assert "maxDepth" in page_tsx
    assert "Blast Radius" in page_tsx or "Impact Analysis" in page_tsx

    # 3. Affected Set representation
    assert "affected_files" in page_tsx
    assert "dependency_chain" in page_tsx
    assert "impact_tier" in page_tsx

    # 4. Static Findings & Triage
    assert "fetchStaticFindings" in page_tsx
    assert "severityFilter" in page_tsx
    assert "triageStatusFilter" in page_tsx
    assert "triageMap" in page_tsx
    assert "handleTriageChange" in page_tsx
    assert "Active" in page_tsx
    assert "Ignore" in page_tsx
    assert "Resolved" in page_tsx
