"""Pydantic schemas for dependency graph and topological queries (P4-02)."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    """A node in the repository import graph (typically a Python file)."""

    id: str  # Unique node key (normalized file path)
    file_path: str
    in_degree: int = 0  # Number of files depending on this file (fan-in)
    out_degree: int = 0  # Number of files this file depends on (fan-out)
    is_internal: bool = True


class GraphEdgeItem(BaseModel):
    """Directed dependency edge representing an import statement.

    Enforces Hard Rule 5: source labelled strictly as 'graph_derived'.
    """

    id: str
    source_file: str
    target_module: str
    target_file: str | None = None
    import_statement: str | None = None
    line_number: int | None = None
    is_internal: bool = True
    imported_symbols: list[str] = Field(default_factory=list)
    source: Literal["graph_derived"] = "graph_derived"


class GraphSummary(BaseModel):
    """Topological metrics and summary of the import graph."""

    total_nodes: int
    internal_edges_count: int
    external_edges_count: int
    cycles_count: int
    is_dag: bool
    density: float
    top_imported_modules: list[dict[str, Any]] = Field(default_factory=list)


class GraphResponse(BaseModel):
    """Full API response for repository import dependency graph.

    Enforces Hard Rule 5: source labelled strictly as 'graph_derived'.
    """

    repository_id: str
    scan_id: str | None = None
    source: Literal["graph_derived"] = "graph_derived"
    summary: GraphSummary
    nodes: list[GraphNode]
    edges: list[GraphEdgeItem]


class RebuildGraphRequest(BaseModel):
    """Request payload to trigger import graph recalculation."""

    include_external: bool = False
