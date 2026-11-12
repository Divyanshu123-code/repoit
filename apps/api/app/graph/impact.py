"""Change impact analysis engine using reverse reachability on import dependency graph (P4-03).

In RepoPilot's dependency graph:
    Directed edge A -> B means module A imports and depends on module B.
When B is modified:
    - Modules importing B directly are affected at depth 1 (direct impact).
    - Modules importing those modules are affected at depth 2 (transitive impact).
    - This reverse reachability is bounded by a configurable depth limit.

Complies strictly with Hard Rule 5:
    Every result is labelled with source: "graph_derived".
"""

from __future__ import annotations

import logging
from typing import Literal

import networkx as nx

from app.graph.schemas import AffectedFileItem, ImpactResponse

logger = logging.getLogger("repopilot.graph.impact")

# Aliases for backward/convenient imports
AffectedFile = AffectedFileItem
ImpactAnalysisResult = ImpactResponse


class ImpactAnalyzer:
    """Computes reverse reachability and blast radius on directed dependency graphs."""

    def __init__(self, graph: nx.DiGraph) -> None:
        """Initialize with a directed dependency graph (source_file -> target_file)."""
        self.graph = graph
        # Invert edges: if A -> B in self.graph, then B -> A in rev_graph
        # Traversing rev_graph forwards from B explores all consumers of B!
        self.rev_graph: nx.DiGraph = graph.reverse(copy=False)

    def analyze(
        self,
        repository_id: str,
        changed_files: list[str],
        max_depth: int = 3,
        include_changed: bool = False,
    ) -> ImpactAnalysisResult:
        """Compute reverse reachability up to max_depth from changed files."""
        if max_depth < 1:
            raise ValueError(f"max_depth must be at least 1, got {max_depth}")

        # Normalize paths
        normalized_seeds = [
            f.strip().replace("\\", "/").lstrip("/") for f in changed_files if f.strip()
        ]
        total_repo_files = len(self.graph.nodes)

        # Dictionary mapping affected_file_path -> best (minimum depth) details
        # format: path -> (depth, seed_file, dependency_chain)
        affected_map: dict[str, tuple[int, str, list[str]]] = {}

        for seed in normalized_seeds:
            # If seed file is in the graph
            if seed in self.rev_graph:
                # Find shortest path lengths and paths from seed in reversed graph
                try:
                    path_lengths: dict[str, int] = nx.single_source_shortest_path_length(
                        self.rev_graph, seed, cutoff=max_depth
                    )
                    paths: dict[str, list[str]] = nx.single_source_shortest_path(
                        self.rev_graph, seed, cutoff=max_depth
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Error calculating reverse reachability for seed %s: %s", seed, exc
                    )
                    continue

                for target_node, depth in path_lengths.items():
                    if depth == 0 and not include_changed:
                        continue

                    # If not seen yet, or found a strictly shorter path from another seed
                    if target_node not in affected_map or depth < affected_map[target_node][0]:
                        affected_map[target_node] = (
                            depth,
                            seed,
                            paths.get(target_node, [seed, target_node]),
                        )
            elif include_changed:
                # Seed itself is not in the graph (e.g. newly created file or non-importing file)
                if seed not in affected_map:
                    affected_map[seed] = (0, seed, [seed])

        # Degree lookups for topological context
        in_degrees: dict[str, int] = (
            dict(self.graph.in_degree()) if self.graph.number_of_nodes() > 0 else {}
        )
        out_degrees: dict[str, int] = (
            dict(self.graph.out_degree()) if self.graph.number_of_nodes() > 0 else {}
        )

        affected_list: list[AffectedFile] = []
        direct_count = 0
        transitive_count = 0

        for file_path, (depth, seed, chain) in affected_map.items():
            if depth == 0:
                tier: Literal["changed", "direct", "transitive"] = "changed"
            elif depth == 1:
                tier = "direct"
                direct_count += 1
            else:
                tier = "transitive"
                transitive_count += 1

            # Identify immediate module in chain that this file depends upon
            # chain is [seed, step1, step2, ..., file_path]
            direct_dep = chain[-2] if len(chain) >= 2 else None

            affected_list.append(
                AffectedFile(
                    file_path=file_path,
                    depth=depth,
                    impact_tier=tier,
                    seed_file=seed,
                    dependency_chain=chain,
                    direct_imported_module=direct_dep,
                    in_degree=int(in_degrees.get(file_path, 0)),
                    out_degree=int(out_degrees.get(file_path, 0)),
                    source="graph_derived",  # Hard Rule 5
                )
            )

        # Sort affected files: depth ascending, then file_path ascending
        affected_list.sort(key=lambda item: (item.depth, item.file_path))

        total_affected = len(affected_list)
        # Avoid division by zero
        impact_ratio = (
            round(total_affected / max(total_repo_files, 1), 4) if total_repo_files > 0 else 0.0
        )
        impact_ratio = min(max(impact_ratio, 0.0), 1.0)

        return ImpactAnalysisResult(
            repository_id=repository_id,
            changed_files=normalized_seeds,
            max_depth=max_depth,
            include_changed=include_changed,
            total_affected_count=total_affected,
            direct_affected_count=direct_count,
            transitive_affected_count=transitive_count,
            total_repo_files=total_repo_files,
            impact_ratio=impact_ratio,
            affected_files=affected_list,
            source="graph_derived",  # Hard Rule 5
        )


def analyze_change_impact(
    graph: nx.DiGraph,
    repository_id: str,
    changed_files: list[str],
    max_depth: int = 3,
    include_changed: bool = False,
) -> ImpactAnalysisResult:
    """Convenience functional interface to ImpactAnalyzer."""
    analyzer = ImpactAnalyzer(graph)
    return analyzer.analyze(
        repository_id=repository_id,
        changed_files=changed_files,
        max_depth=max_depth,
        include_changed=include_changed,
    )
