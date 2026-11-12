"""Tests for change impact analysis via reverse reachability (P4-03).

Acceptance Criteria:
    - Controlled-change fixture returns expected set.
    - Reverse reachability correctly calculates shortest path distances.
    - Enforces depth limits (max_depth).
    - Resilient to circular/cyclic dependencies and disconnected components.
    - Hard Rule 5: source labelled strictly as 'graph_derived'.
"""

import uuid
from typing import Any

import networkx as nx
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import get_db_session
from app.graph.impact import (
    analyze_change_impact,
)
from app.graph.models import DependencyEdge
from app.graph.schemas import ImpactResponse
from app.graph.service import DependencyGraphService
from app.main import app
from app.repos.models import Repository


@pytest.fixture
def diamond_graph() -> nx.DiGraph:
    """Fixture with a controlled diamond dependency structure.

    Topology:
        main.py -> api/routes_a.py -> services/service_a.py -> core/base.py
        main.py -> api/routes_b.py -> services/service_b.py -> core/base.py
        utils/helper.py -> core/base.py
        isolated/script.py (disconnected)

    In this graph:
        - If 'core/base.py' changes:
          * Depth 1: services/service_a.py, services/service_b.py, utils/helper.py
          * Depth 2: api/routes_a.py, api/routes_b.py
          * Depth 3: main.py
          * Never affected: isolated/script.py
    """
    g = nx.DiGraph()
    # Edges represent (importer -> imported)
    g.add_edge("services/service_a.py", "core/base.py")
    g.add_edge("services/service_b.py", "core/base.py")
    g.add_edge("utils/helper.py", "core/base.py")
    g.add_edge("api/routes_a.py", "services/service_a.py")
    g.add_edge("api/routes_b.py", "services/service_b.py")
    g.add_edge("main.py", "api/routes_a.py")
    g.add_edge("main.py", "api/routes_b.py")
    g.add_node("isolated/script.py")
    return g


@pytest.fixture
def cyclic_graph() -> nx.DiGraph:
    """Fixture containing a circular dependency cycle.

    Topology:
        A -> B -> C -> A (cycle)
        consumer.py -> B
    """
    g = nx.DiGraph()
    g.add_edge("pkg/mod_a.py", "pkg/mod_b.py")
    g.add_edge("pkg/mod_b.py", "pkg/mod_c.py")
    g.add_edge("pkg/mod_c.py", "pkg/mod_a.py")
    g.add_edge("consumer.py", "pkg/mod_b.py")
    return g


def test_diamond_fixture_depth_1(diamond_graph: nx.DiGraph) -> None:
    """AC Test: Depth 1 cutoff on controlled diamond fixture returns exact direct consumers."""
    result = analyze_change_impact(
        graph=diamond_graph,
        repository_id="repo-123",
        changed_files=["core/base.py"],
        max_depth=1,
    )

    assert result.source == "graph_derived"
    assert result.max_depth == 1
    assert result.total_affected_count == 3
    assert result.direct_affected_count == 3
    assert result.transitive_affected_count == 0

    affected_paths = {f.file_path for f in result.affected_files}
    expected = {"services/service_a.py", "services/service_b.py", "utils/helper.py"}
    assert affected_paths == expected

    for f in result.affected_files:
        assert f.depth == 1
        assert f.impact_tier == "direct"
        assert f.seed_file == "core/base.py"
        assert f.direct_imported_module == "core/base.py"
        assert f.dependency_chain == ["core/base.py", f.file_path]
        assert f.source == "graph_derived"


def test_diamond_fixture_depth_2(diamond_graph: nx.DiGraph) -> None:
    """AC Test: Depth 2 cutoff returns direct and transitive tier-2 consumers."""
    result = analyze_change_impact(
        graph=diamond_graph,
        repository_id="repo-123",
        changed_files=["core/base.py"],
        max_depth=2,
    )

    assert result.total_affected_count == 5
    assert result.direct_affected_count == 3
    assert result.transitive_affected_count == 2

    affected_paths = {f.file_path for f in result.affected_files}
    expected = {
        "services/service_a.py",
        "services/service_b.py",
        "utils/helper.py",
        "api/routes_a.py",
        "api/routes_b.py",
    }
    assert affected_paths == expected

    # Verify transitive file properties
    routes_a = next(f for f in result.affected_files if f.file_path == "api/routes_a.py")
    assert routes_a.depth == 2
    assert routes_a.impact_tier == "transitive"
    assert routes_a.dependency_chain == ["core/base.py", "services/service_a.py", "api/routes_a.py"]
    assert routes_a.direct_imported_module == "services/service_a.py"


def test_diamond_fixture_depth_3_full(diamond_graph: nx.DiGraph) -> None:
    """AC Test: Depth 3 cutoff reaches main.py and respects disconnected components."""
    result = analyze_change_impact(
        graph=diamond_graph,
        repository_id="repo-123",
        changed_files=["core/base.py"],
        max_depth=3,
    )

    assert result.total_affected_count == 6
    affected_paths = {f.file_path for f in result.affected_files}
    assert "main.py" in affected_paths
    # Disconnected node must never be impacted
    assert "isolated/script.py" not in affected_paths

    main_node = next(f for f in result.affected_files if f.file_path == "main.py")
    assert main_node.depth == 3
    assert main_node.impact_tier == "transitive"
    assert main_node.dependency_chain[0] == "core/base.py"
    assert main_node.dependency_chain[-1] == "main.py"


def test_include_changed_option(diamond_graph: nx.DiGraph) -> None:
    """Verify include_changed=True includes seed file with depth 0 and 'changed' tier."""
    result = analyze_change_impact(
        graph=diamond_graph,
        repository_id="repo-123",
        changed_files=["core/base.py"],
        max_depth=1,
        include_changed=True,
    )

    assert result.total_affected_count == 4  # seed + 3 direct
    seed_item = next(f for f in result.affected_files if f.file_path == "core/base.py")
    assert seed_item.depth == 0
    assert seed_item.impact_tier == "changed"
    assert seed_item.dependency_chain == ["core/base.py"]


def test_cyclic_dependency_resilience(cyclic_graph: nx.DiGraph) -> None:
    """Verify reverse reachability terminates cleanly in cycles without infinite loops."""
    # Mod C is imported by mod B, which is imported by mod A and consumer
    result = analyze_change_impact(
        graph=cyclic_graph,
        repository_id="repo-cycle",
        changed_files=["pkg/mod_c.py"],
        max_depth=5,
    )

    # In cyclic graph:
    # mod_b imports mod_c -> depth 1
    # mod_a imports mod_b -> depth 2
    # consumer.py imports mod_b -> depth 2
    # mod_c imports mod_a -> cycle loop back to seed (visited, pruned)
    affected_paths = {f.file_path for f in result.affected_files}
    assert "pkg/mod_b.py" in affected_paths
    assert "pkg/mod_a.py" in affected_paths
    assert "consumer.py" in affected_paths

    mod_b = next(f for f in result.affected_files if f.file_path == "pkg/mod_b.py")
    assert mod_b.depth == 1

    consumer = next(f for f in result.affected_files if f.file_path == "consumer.py")
    assert consumer.depth == 2


def test_multiple_changed_files_union(diamond_graph: nx.DiGraph) -> None:
    """Verify multiple changed files produce a unified set taking minimum depth."""
    # Change both service_a and helper
    result = analyze_change_impact(
        graph=diamond_graph,
        repository_id="repo-123",
        changed_files=["services/service_a.py", "utils/helper.py"],
        max_depth=2,
    )

    affected_paths = {f.file_path for f in result.affected_files}
    # api/routes_a is depth 1 from service_a
    # main.py is depth 2 from service_a (via routes_a)
    assert "api/routes_a.py" in affected_paths
    assert "main.py" in affected_paths
    # service_b was not changed and does not depend on service_a/helper
    assert "services/service_b.py" not in affected_paths


def test_nonexistent_and_empty_files(diamond_graph: nx.DiGraph) -> None:
    """Verify changing non-existent or un-indexed files returns empty affected set gracefully."""
    result = analyze_change_impact(
        graph=diamond_graph,
        repository_id="repo-123",
        changed_files=["nonexistent/file.py", "README.md"],
        max_depth=3,
    )
    assert result.total_affected_count == 0
    assert result.affected_files == []
    assert result.source == "graph_derived"


# --- Service and API Integration Tests ---


@pytest.mark.asyncio
async def test_dependency_graph_service_compute_impact() -> None:
    """Test DependencyGraphService.compute_impact parses persisted DB edges into NetworkX impact."""
    from unittest.mock import MagicMock

    from sqlalchemy.ext.asyncio import AsyncSession

    service = DependencyGraphService()
    repo_id = uuid.uuid4()

    # Create mock edges:
    # api/routes.py -> services/user_service.py -> core/db.py
    edge1 = DependencyEdge(
        repository_id=repo_id,
        source_file="services/user_service.py",
        target_module="core.db",
        target_file="core/db.py",
        is_internal=True,
        source="graph_derived",
    )
    edge2 = DependencyEdge(
        repository_id=repo_id,
        source_file="api/routes.py",
        target_module="services.user_service",
        target_file="services/user_service.py",
        is_internal=True,
        source="graph_derived",
    )

    mock_db = MagicMock(spec=AsyncSession)
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [edge1, edge2]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_db.execute.return_value = mock_result

    impact = await service.compute_impact(
        session=mock_db,
        repository_id=repo_id,
        changed_files=["core/db.py"],
        max_depth=3,
        include_changed=False,
    )

    assert impact.source == "graph_derived"
    assert impact.total_affected_count == 2
    assert impact.direct_affected_count == 1
    assert impact.transitive_affected_count == 1
    paths = {f.file_path: f for f in impact.affected_files}
    assert "services/user_service.py" in paths
    assert paths["services/user_service.py"].depth == 1
    assert "api/routes.py" in paths
    assert paths["api/routes.py"].depth == 2


@pytest.mark.asyncio
async def test_api_impact_analysis_endpoints() -> None:
    """Test POST and GET /repositories/{id}/graph/impact endpoints."""
    from unittest.mock import MagicMock

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.graph.service import get_graph_service

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

    mock_service = MagicMock(spec=DependencyGraphService)
    mock_response = ImpactResponse(
        repository_id=str(repo_id),
        changed_files=["core/db.py"],
        max_depth=2,
        include_changed=False,
        total_affected_count=2,
        direct_affected_count=1,
        transitive_affected_count=1,
        total_repo_files=10,
        impact_ratio=0.2,
        affected_files=[
            {
                "file_path": "services/user_service.py",
                "depth": 1,
                "impact_tier": "direct",
                "seed_file": "core/db.py",
                "dependency_chain": ["core/db.py", "services/user_service.py"],
                "direct_imported_module": "core/db.py",
                "source": "graph_derived",
            },
            {
                "file_path": "api/routes.py",
                "depth": 2,
                "impact_tier": "transitive",
                "seed_file": "core/db.py",
                "dependency_chain": [
                    "core/db.py",
                    "services/user_service.py",
                    "api/routes.py",
                ],
                "direct_imported_module": "services/user_service.py",
                "source": "graph_derived",
            },
        ],
        source="graph_derived",
    )
    mock_service.compute_impact.return_value = mock_response

    async def override_get_db_session() -> Any:
        yield mock_db

    def override_get_graph_service() -> DependencyGraphService:
        return mock_service

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_graph_service] = override_get_graph_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Test POST /repositories/{id}/graph/impact
            post_resp = await client.post(
                f"/repositories/{repo_id}/graph/impact",
                json={
                    "changed_files": ["core/db.py"],
                    "max_depth": 2,
                    "include_changed": False,
                },
            )
            assert post_resp.status_code == 200
            data = post_resp.json()
            assert data["source"] == "graph_derived"
            assert data["total_affected_count"] == 2
            assert data["direct_affected_count"] == 1
            assert data["transitive_affected_count"] == 1
            assert len(data["affected_files"]) == 2

            # 2. Test GET /repositories/{id}/graph/impact
            get_resp = await client.get(
                f"/repositories/{repo_id}/graph/impact",
                params={"file": "core/db.py", "max_depth": 2},
            )
            assert get_resp.status_code == 200
            get_data = get_resp.json()
            assert get_data["source"] == "graph_derived"
            assert get_data["total_affected_count"] == 2

            # 3. Test 404 on missing repository
            mock_db.get.return_value = None
            missing_id = uuid.uuid4()
            bad_resp = await client.post(
                f"/repositories/{missing_id}/graph/impact",
                json={"changed_files": ["core/db.py"]},
            )
            assert bad_resp.status_code == 404
    finally:
        app.dependency_overrides.clear()
