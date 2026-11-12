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


class ImpactRequest(BaseModel):
    """Request payload for change impact analysis (P4-03)."""

    changed_files: list[str] = Field(
        ...,
        min_length=1,
        description="List of modified or proposed file paths to analyze",
        examples=[["app/core/db.py"]],
    )
    max_depth: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Maximum depth of reverse reachability traversal",
    )
    include_changed: bool = Field(
        default=False,
        description="Whether to include the seed changed files themselves in the affected list (at depth 0)",
    )


class AffectedFileItem(BaseModel):
    """Details of a single file affected by change propagation.

    Enforces Hard Rule 5: source labelled strictly as 'graph_derived'.
    """

    file_path: str
    depth: int = Field(ge=0, description="Shortest distance from any changed file")
    impact_tier: Literal["changed", "direct", "transitive"]
    seed_file: str = Field(description="The changed file that triggered this impact")
    dependency_chain: list[str] = Field(
        default_factory=list,
        description="Shortest path from changed seed file to this affected file [seed, ..., affected]",
    )
    direct_imported_module: str | None = Field(
        default=None,
        description="The immediate dependency in the chain imported by this file",
    )
    in_degree: int = 0
    out_degree: int = 0
    source: Literal["graph_derived"] = "graph_derived"


class ImpactResponse(BaseModel):
    """Full API response for change impact blast radius analysis.

    Enforces Hard Rule 5: source labelled strictly as 'graph_derived'.
    """

    repository_id: str
    changed_files: list[str]
    max_depth: int
    include_changed: bool = False
    total_affected_count: int
    direct_affected_count: int
    transitive_affected_count: int
    total_repo_files: int
    impact_ratio: float = Field(
        ge=0.0,
        le=1.0,
        description="Fraction of repo files impacted by this change set (0.0 to 1.0)",
    )
    affected_files: list[AffectedFileItem] = Field(default_factory=list)
    source: Literal["graph_derived"] = "graph_derived"
