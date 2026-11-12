"""Unit and integration tests for NetworkX import graph builder and API (P4-02)."""

import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.graph.builder import (
    ImportGraphBuilder,
    resolve_import_to_file,
)
from app.graph.models import DependencyEdge
from app.graph.schemas import GraphResponse
from app.graph.service import DependencyGraphService, get_graph_service
from app.main import app
from app.parsing.models import ImportItem, ImportStatement
from app.repos.models import Repository


def test_resolve_import_to_file_internal_and_external() -> None:
    """Test resolution of relative, absolute, and external imports to physical repository files."""
    known_files = {
        "app/main.py",
        "app/core/db.py",
        "app/core/__init__.py",
        "app/repos/models.py",
        "app/repos/service.py",
        "app/api/repos.py",
        "app/api/utils.py",
    }

    # 1. Relative import in same directory
    res_same = resolve_import_to_file("app/api/repos.py", ".utils", known_files)
    assert res_same == "app/api/utils.py"

    # 2. Relative parent import
    res_parent = resolve_import_to_file("app/api/repos.py", "..repos.models", known_files)
    assert res_parent == "app/repos/models.py"

    # 3. Absolute internal import
    res_abs = resolve_import_to_file("app/main.py", "app.core.db", known_files)
    assert res_abs == "app/core/db.py"

    # 4. Package __init__ import
    res_init = resolve_import_to_file("app/main.py", "app.core", known_files)
    assert res_init == "app/core/__init__.py"

    # 5. External standard library import -> None
    assert resolve_import_to_file("app/main.py", "os", known_files) is None
    assert resolve_import_to_file("app/main.py", "sys", known_files) is None
    assert resolve_import_to_file("app/main.py", "asyncio", known_files) is None

    # 6. External third-party import -> None
    assert resolve_import_to_file("app/main.py", "fastapi", known_files) is None
    assert resolve_import_to_file("app/main.py", "networkx", known_files) is None
    assert resolve_import_to_file("app/main.py", "pytest", known_files) is None


def test_import_graph_builder_topology_and_cycles() -> None:
    """Test NetworkX directed graph construction, topological metrics, and cycle detection."""
    files = ["pkg/a.py", "pkg/b.py", "pkg/c.py"]
    builder = ImportGraphBuilder(known_files=files)

    # A depends on B, B depends on C (DAG: A -> B -> C)
    modules_imports = {
        "pkg/a.py": [
            ImportStatement(
                module=".b",
                items=[ImportItem("func_b")],
                raw_statement="from .b import func_b",
                start_line=2,
            )
        ],
        "pkg/b.py": [
            ImportStatement(
                module=".c",
                items=[ImportItem("func_c")],
                raw_statement="from .c import func_c",
                start_line=1,
            )
        ],
        "pkg/c.py": [],
    }

    edges = builder.build_edges(modules_imports)
    assert len(edges) == 2

    metrics = builder.compute_metrics()
    assert metrics.total_nodes == 3
    assert metrics.internal_edges_count == 2
    assert metrics.is_dag is True
    assert metrics.cycles_count == 0

    # In-degree (fan-in): C has 1 dependent (B), B has 1 dependent (A), A has 0
    assert metrics.in_degrees["pkg/c.py"] == 1
    assert metrics.in_degrees["pkg/b.py"] == 1
    assert metrics.in_degrees["pkg/a.py"] == 0

    # Out-degree (fan-out): A imports 1 (B), B imports 1 (C), C imports 0
    assert metrics.out_degrees["pkg/a.py"] == 1
    assert metrics.out_degrees["pkg/b.py"] == 1
    assert metrics.out_degrees["pkg/c.py"] == 0

    # Now introduce circular dependency: C depends back on A (A -> B -> C -> A)
    circular_imports = dict(modules_imports)
    circular_imports["pkg/c.py"] = [
        ImportStatement(
            module=".a",
            items=[ImportItem("func_a")],
            raw_statement="from .a import func_a",
            start_line=5,
        )
    ]

    circ_builder = ImportGraphBuilder(known_files=files)
    circ_builder.build_edges(circular_imports)
    circ_metrics = circ_builder.compute_metrics()

    assert circ_metrics.is_dag is False
    assert circ_metrics.cycles_count >= 1
    assert any("pkg/a.py" in cycle for cycle in circ_metrics.cycles)


def test_dependency_edge_model_and_rule_5() -> None:
    """Test DependencyEdge entity serialization and Hard Rule 5 source label."""
    repo_id = uuid.uuid4()
    edge = DependencyEdge(
        repository_id=repo_id,
        source_file="app/api/repos.py",
        target_module="app.repos.service",
        target_file="app/repos/service.py",
        import_statement="from app.repos.service import register_github_repository",
        line_number=27,
        is_internal=True,
        imported_symbols=["register_github_repository"],
        source="graph_derived",  # Hard Rule 5
    )

    data = edge.to_dict()
    assert data["source_file"] == "app/api/repos.py"
    assert data["target_file"] == "app/repos/service.py"
    assert data["is_internal"] is True
    assert data["imported_symbols"] == ["register_github_repository"]
    assert data["source"] == "graph_derived"  # Hard Rule 5
    assert "created_at" in data


@pytest.mark.asyncio
async def test_api_get_graph_repo_not_found() -> None:
    """GET /repositories/{id}/graph returns 404 for nonexistent repository."""
    nonexistent_id = uuid.uuid4()

    mock_db = MagicMock(spec=AsyncSession)
    mock_db.get.return_value = None

    async def override_get_db_session() -> Any:
        yield mock_db

    app.dependency_overrides[get_db_session] = override_get_db_session
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/repositories/{nonexistent_id}/graph")
            assert resp.status_code == 404
            assert "not found" in resp.json()["detail"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_get_graph_success() -> None:
    """GET /repositories/{id}/graph returns GraphResponse with source: graph_derived."""
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
    mock_response = GraphResponse(
        repository_id=str(repo_id),
        scan_id=None,
        source="graph_derived",  # Hard Rule 5
        summary={
            "total_nodes": 2,
            "internal_edges_count": 1,
            "external_edges_count": 0,
            "cycles_count": 0,
            "is_dag": True,
            "density": 0.5,
            "top_imported_modules": [{"file_path": "app/core.py", "in_degree": 1, "out_degree": 0}],
        },
        nodes=[
            {
                "id": "app/main.py",
                "file_path": "app/main.py",
                "in_degree": 0,
                "out_degree": 1,
                "is_internal": True,
            },
            {
                "id": "app/core.py",
                "file_path": "app/core.py",
                "in_degree": 1,
                "out_degree": 0,
                "is_internal": True,
            },
        ],
        edges=[
            {
                "id": str(uuid.uuid4()),
                "source_file": "app/main.py",
                "target_module": "app.core",
                "target_file": "app/core.py",
                "import_statement": "from app.core import init",
                "line_number": 5,
                "is_internal": True,
                "imported_symbols": ["init"],
                "source": "graph_derived",
            }
        ],
    )
    mock_service.get_repository_graph.return_value = mock_response

    async def override_get_db_session() -> Any:
        yield mock_db

    def override_get_graph_service() -> DependencyGraphService:
        return mock_service

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_graph_service] = override_get_graph_service
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/repositories/{repo_id}/graph")
            assert resp.status_code == 200
            data = resp.json()
            assert data["repository_id"] == str(repo_id)
            assert data["source"] == "graph_derived"  # Hard Rule 5
            assert data["summary"]["total_nodes"] == 2
            assert data["summary"]["is_dag"] is True
            assert len(data["nodes"]) == 2
            assert len(data["edges"]) == 1
            assert data["edges"][0]["source_file"] == "app/main.py"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_rebuild_graph() -> None:
    """POST /repositories/{id}/graph/rebuild triggers graph reconstruction."""
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
    mock_scan_res = MagicMock()
    mock_scan_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_scan_res

    mock_service = MagicMock(spec=DependencyGraphService)
    mock_service.build_and_store_graph.return_value = ([], MagicMock())
    mock_response = GraphResponse(
        repository_id=str(repo_id),
        scan_id=None,
        source="graph_derived",
        summary={
            "total_nodes": 0,
            "internal_edges_count": 0,
            "external_edges_count": 0,
            "cycles_count": 0,
            "is_dag": True,
            "density": 0.0,
            "top_imported_modules": [],
        },
        nodes=[],
        edges=[],
    )
    mock_service.get_repository_graph.return_value = mock_response

    async def override_get_db_session() -> Any:
        yield mock_db

    def override_get_graph_service() -> DependencyGraphService:
        return mock_service

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_graph_service] = override_get_graph_service
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/repositories/{repo_id}/graph/rebuild")
            assert resp.status_code == 200
            data = resp.json()
            assert data["source"] == "graph_derived"
    finally:
        app.dependency_overrides.clear()
