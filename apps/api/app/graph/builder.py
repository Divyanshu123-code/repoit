"""NetworkX-based import dependency graph builder and topological analysis (P4-02).

Constructs a directed graph (networkx.DiGraph) representing module import relationships,
resolves intra-repository relative and absolute imports to physical file paths,
detects circular dependencies (cycles), and computes fan-in/fan-out metrics.

Enforces:
- Hard Rule 3: Repository content is untrusted input.
- Hard Rule 5: Source labelled strictly as 'graph_derived'.
- P4-02: Import graph builder (NetworkX) + persisted edges.
"""

import logging
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

import networkx as nx

from app.parsing.models import ImportStatement

logger = logging.getLogger("repopilot.graph.builder")

# Common Python standard library module prefixes for fast classification
STDLIB_PREFIXES: frozenset[str] = frozenset(
    {
        "abc",
        "argparse",
        "ast",
        "asyncio",
        "base64",
        "collections",
        "concurrent",
        "contextlib",
        "copy",
        "csv",
        "dataclasses",
        "datetime",
        "decimal",
        "difflib",
        "enum",
        "functools",
        "glob",
        "hashlib",
        "http",
        "importlib",
        "inspect",
        "io",
        "itertools",
        "json",
        "logging",
        "math",
        "multiprocessing",
        "operator",
        "os",
        "pathlib",
        "pickle",
        "platform",
        "pprint",
        "random",
        "re",
        "shutil",
        "signal",
        "socket",
        "sqlite3",
        "string",
        "subprocess",
        "sys",
        "tempfile",
        "threading",
        "time",
        "traceback",
        "types",
        "typing",
        "unittest",
        "urllib",
        "uuid",
        "warnings",
        "weakref",
        "xml",
        "zipfile",
    }
)


def resolve_import_to_file(
    source_file: str,
    imported_module: str,
    known_files: set[str],
) -> str | None:
    """Resolve an imported module string to a repository-relative file path.

    Handles:
    - Relative imports: `from .models import ...`, `from ..core import ...`
    - Absolute imports: `import app.repos.models` -> `app/repos/models.py` or `app/repos/models/__init__.py`
    - Nested packages: `src/`, `packages/`, or direct repo root prefixes.
    - External modules (e.g. `fastapi`, `numpy`, `os`) -> returns None.

    Args:
        source_file: Repository-relative path of the importing file (e.g. 'app/api/repos.py').
        imported_module: Raw module name from import statement (e.g. '.service', 'app.core.db').
        known_files: Set of normalized repository file paths (e.g. {'app/core/db.py', ...}).

    Returns:
        Resolved relative file path string if internal, or None if external.
    """
    if not imported_module:
        return None

    norm_source = source_file.replace("\\", "/").lstrip("/")
    source_parent = PurePosixPath(norm_source).parent

    # 1. Handle relative imports starting with '.'
    if imported_module.startswith("."):
        dots_count = len(imported_module) - len(imported_module.lstrip("."))
        remainder = imported_module.lstrip(".")

        target_dir = source_parent
        for _ in range(dots_count - 1):
            target_dir = target_dir.parent

        if remainder:
            candidate_base = (target_dir / remainder.replace(".", "/")).as_posix()
        else:
            candidate_base = target_dir.as_posix()

        # Check candidate as file or package __init__
        for cand in [f"{candidate_base}.py", f"{candidate_base}/__init__.py", candidate_base]:
            cleaned = cand.lstrip("./")
            if cleaned in known_files:
                return cleaned

        return None

    # 2. Fast check: is it standard library?
    base_prefix = imported_module.split(".")[0].lower()
    if base_prefix in STDLIB_PREFIXES:
        return None

    # 3. Handle absolute internal imports
    module_path = imported_module.replace(".", "/")

    # Candidate 1: Direct match from repository root
    direct_py = f"{module_path}.py"
    direct_init = f"{module_path}/__init__.py"
    if direct_py in known_files:
        return direct_py
    if direct_init in known_files:
        return direct_init

    # Candidate 2: Prefixed with common package directories ('src/', 'packages/...')
    for prefix in ["src", "packages", "app", "lib"]:
        prefixed_py = f"{prefix}/{module_path}.py"
        prefixed_init = f"{prefix}/{module_path}/__init__.py"
        if prefixed_py in known_files:
            return prefixed_py
        if prefixed_init in known_files:
            return prefixed_init

    # Candidate 3: Sibling or subpackage match relative to source file directory
    relative_py = (source_parent / f"{module_path}.py").as_posix()
    relative_init = (source_parent / f"{module_path}/__init__.py").as_posix()
    if relative_py in known_files:
        return relative_py
    if relative_init in known_files:
        return relative_init

    # Candidate 4: If imported_module was `from x.y import z` and `x/y.py` exists, z might be a symbol
    if "/" in module_path:
        parent_module = module_path.rsplit("/", 1)[0]
        if f"{parent_module}.py" in known_files:
            return f"{parent_module}.py"

    return None


@dataclass
class ResolvedEdge:
    """Internal representation of a resolved dependency edge."""

    source_file: str
    target_module: str
    target_file: str | None
    import_statement: str | None
    line_number: int | None
    is_internal: bool
    imported_symbols: list[str] = field(default_factory=list)
    source: str = "graph_derived"  # Hard Rule 5


@dataclass
class GraphTopologyMetrics:
    """Graph topological metrics computed via NetworkX."""

    total_nodes: int
    internal_edges_count: int
    external_edges_count: int
    cycles_count: int
    is_dag: bool
    density: float
    cycles: list[list[str]] = field(default_factory=list)
    in_degrees: dict[str, int] = field(default_factory=dict)
    out_degrees: dict[str, int] = field(default_factory=dict)
    top_imported_modules: list[dict[str, Any]] = field(default_factory=list)


class ImportGraphBuilder:
    """Builds and analyzes a NetworkX directed graph from repository imports."""

    def __init__(self, known_files: set[str] | list[str]) -> None:
        self.known_files: set[str] = {
            f.replace("\\", "/").lstrip("/") for f in known_files if f.endswith(".py")
        }
        self.graph = nx.DiGraph()
        self._initialize_nodes()

    def _initialize_nodes(self) -> None:
        """Add all known repository Python files as nodes in the graph."""
        for file_path in self.known_files:
            self.graph.add_node(
                file_path,
                id=file_path,
                file_path=file_path,
                is_internal=True,
            )

    def build_edges(
        self,
        modules_imports: dict[str, list[ImportStatement]],
    ) -> list[ResolvedEdge]:
        """Resolve all imports across modules and add directed edges into the NetworkX graph.

        Direction:
            `source_file -> target_file` (indicating `source_file` depends on `target_file`).
        """
        resolved_edges: list[ResolvedEdge] = []

        for src_file, imports in modules_imports.items():
            norm_src = src_file.replace("\\", "/").lstrip("/")

            # Ensure source node exists
            if norm_src not in self.graph:
                self.graph.add_node(norm_src, id=norm_src, file_path=norm_src, is_internal=True)
                self.known_files.add(norm_src)

            for imp in imports:
                target_file = resolve_import_to_file(norm_src, imp.module, self.known_files)
                is_internal = target_file is not None
                symbols = [item.name for item in imp.items]

                edge = ResolvedEdge(
                    source_file=norm_src,
                    target_module=imp.module,
                    target_file=target_file,
                    import_statement=imp.raw_statement or None,
                    line_number=imp.start_line if imp.start_line > 0 else None,
                    is_internal=is_internal,
                    imported_symbols=symbols,
                    source="graph_derived",  # Hard Rule 5
                )
                resolved_edges.append(edge)

                if is_internal and target_file:
                    # Add directed edge in internal dependency graph
                    self.graph.add_edge(
                        norm_src,
                        target_file,
                        target_module=imp.module,
                        line_number=edge.line_number,
                        symbols=symbols,
                        is_internal=True,
                    )
                else:
                    # External module (optional tracking in full graph)
                    ext_node = f"ext:{imp.module}"
                    self.graph.add_node(
                        ext_node, id=ext_node, file_path=imp.module, is_internal=False
                    )
                    self.graph.add_edge(
                        norm_src,
                        ext_node,
                        target_module=imp.module,
                        line_number=edge.line_number,
                        symbols=symbols,
                        is_internal=False,
                    )

        return resolved_edges

    def compute_metrics(self) -> GraphTopologyMetrics:
        """Compute topological metrics on the internal dependency subgraph using NetworkX."""
        # Focus topological metrics on internal repository files
        internal_nodes = [n for n, d in self.graph.nodes(data=True) if d.get("is_internal", True)]
        subgraph: nx.DiGraph = self.graph.subgraph(internal_nodes)

        total_nodes = subgraph.number_of_nodes()
        internal_edges = subgraph.number_of_edges()
        external_edges = self.graph.number_of_edges() - internal_edges

        # Check for circular dependencies (cycles)
        is_dag = nx.is_directed_acyclic_graph(subgraph)
        cycles: list[list[str]] = []
        if not is_dag:
            try:
                # Limit simple_cycles computation to bound runtime on large complex graphs
                for c in nx.simple_cycles(subgraph):
                    cycles.append([str(node) for node in c])
                    if len(cycles) >= 50:
                        break
            except Exception as e:  # noqa: BLE001
                logger.warning("Cycle computation truncated: %s", e)

        # Degree calculations
        in_degrees = {str(n): int(d) for n, d in subgraph.in_degree()}
        out_degrees = {str(n): int(d) for n, d in subgraph.out_degree()}
        density = float(nx.density(subgraph)) if total_nodes > 1 else 0.0

        # Identify top imported internal modules (highest in-degree / fan-in)
        sorted_by_fan_in = sorted(in_degrees.items(), key=lambda item: item[1], reverse=True)
        top_imported = [
            {
                "file_path": f_path,
                "in_degree": deg,
                "out_degree": out_degrees.get(f_path, 0),
            }
            for f_path, deg in sorted_by_fan_in[:10]
            if deg > 0
        ]

        return GraphTopologyMetrics(
            total_nodes=total_nodes,
            internal_edges_count=internal_edges,
            external_edges_count=external_edges,
            cycles_count=len(cycles),
            is_dag=is_dag,
            density=round(density, 4),
            cycles=cycles,
            in_degrees=in_degrees,
            out_degrees=out_degrees,
            top_imported_modules=top_imported,
        )
