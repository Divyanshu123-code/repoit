"""Root test verification for Phase 4 Impact Analysis (P4-03).

Acceptance Criteria:
    - Controlled-change fixture returns expected set.
    - Reverse reachability with depth cutoff.
    - Rule 5 source label check: 'graph_derived'.
"""

import networkx as nx
import pytest
from app.graph.impact import ImpactAnalyzer
from app.graph.schemas import AffectedFileItem, ImpactResponse


def test_controlled_fixture_root() -> None:
    """Verify controlled change impact fixture returns exact affected set."""
    g = nx.DiGraph()
    # Chain: consumer.py -> service.py -> model.py -> database.py
    g.add_edge("consumer.py", "service.py")
    g.add_edge("service.py", "model.py")
    g.add_edge("model.py", "database.py")
    g.add_node("unrelated.py")

    # If database.py changes:
    # depth 1: model.py
    # depth 2: service.py
    # depth 3: consumer.py
    analyzer = ImpactAnalyzer(g)
    result = analyzer.analyze(
        repository_id="test-repo",
        changed_files=["database.py"],
        max_depth=2,
        include_changed=False,
    )

    assert result.source == "graph_derived"
    assert result.total_affected_count == 2
    assert result.direct_affected_count == 1
    assert result.transitive_affected_count == 1

    paths = [f.file_path for f in result.affected_files]
    assert paths == ["model.py", "service.py"]

    # Test depth 3 reaches consumer.py
    res_depth_3 = analyzer.analyze(
        repository_id="test-repo",
        changed_files=["database.py"],
        max_depth=3,
    )
    assert res_depth_3.total_affected_count == 3
    paths_3 = [f.file_path for f in res_depth_3.affected_files]
    assert paths_3 == ["model.py", "service.py", "consumer.py"]


def test_impact_schema_hard_rule_5() -> None:
    """Ensure ImpactResponse and AffectedFileItem enforce source='graph_derived'."""
    item = AffectedFileItem(
        file_path="app/api.py",
        depth=1,
        impact_tier="direct",
        seed_file="app/db.py",
    )
    assert item.source == "graph_derived"

    resp = ImpactResponse(
        repository_id="repo-1",
        changed_files=["app/db.py"],
        max_depth=3,
        total_affected_count=1,
        direct_affected_count=1,
        transitive_affected_count=0,
        total_repo_files=10,
        impact_ratio=0.1,
        affected_files=[item],
    )
    assert resp.source == "graph_derived"


def test_validation_invalid_depth() -> None:
    """Test validation fails when max_depth < 1."""
    g = nx.DiGraph()
    analyzer = ImpactAnalyzer(g)
    with pytest.raises(ValueError, match="max_depth must be at least 1"):
        analyzer.analyze(
            repository_id="repo-1",
            changed_files=["db.py"],
            max_depth=0,
        )
