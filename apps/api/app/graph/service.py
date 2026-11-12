"""Dependency graph service for building, persisting, and querying import graphs (P4-02)."""

import logging
import uuid
from datetime import UTC, datetime

import networkx as nx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.graph.builder import ImportGraphBuilder
from app.graph.impact import analyze_change_impact
from app.graph.models import DependencyEdge
from app.graph.schemas import (
    GraphEdgeItem,
    GraphNode,
    GraphResponse,
    GraphSummary,
    ImpactResponse,
)
from app.parsing.models import ImportStatement

logger = logging.getLogger("repopilot.graph.service")


class DependencyGraphService:
    """Service orchestrating NetworkX import graph building and database persistence."""

    async def build_and_store_graph(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        modules_imports: dict[str, list[ImportStatement]],
        known_files: set[str] | list[str],
        scan_id: uuid.UUID | None = None,
    ) -> tuple[list[DependencyEdge], GraphSummary]:
        """Construct NetworkX import graph, resolve edges, and persist to dependency_edges table."""
        # 1. Clean previous edges for this repository
        await session.execute(
            delete(DependencyEdge).where(DependencyEdge.repository_id == repository_id)
        )

        # 2. Build graph and resolve dependencies
        builder = ImportGraphBuilder(known_files=known_files)
        resolved_edges = builder.build_edges(modules_imports)
        metrics = builder.compute_metrics()

        # 3. Persist edges into PostgreSQL
        now = datetime.now(UTC)
        records: list[DependencyEdge] = []
        for edge in resolved_edges:
            record = DependencyEdge(
                repository_id=repository_id,
                scan_id=scan_id,
                source_file=edge.source_file,
                target_module=edge.target_module,
                target_file=edge.target_file,
                import_statement=edge.import_statement,
                line_number=edge.line_number,
                is_internal=edge.is_internal,
                imported_symbols=edge.imported_symbols,
                source="graph_derived",  # Hard Rule 5
                created_at=now,
            )
            session.add(record)
            records.append(record)

        await session.commit()
        logger.info(
            "Persisted %d dependency edges for repository %s (scan_id=%s)",
            len(records),
            repository_id,
            scan_id,
        )

        summary = GraphSummary(
            total_nodes=metrics.total_nodes,
            internal_edges_count=metrics.internal_edges_count,
            external_edges_count=metrics.external_edges_count,
            cycles_count=metrics.cycles_count,
            is_dag=metrics.is_dag,
            density=metrics.density,
            top_imported_modules=metrics.top_imported_modules,
        )

        return records, summary

    async def get_repository_graph(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        internal_only: bool = True,
    ) -> GraphResponse:
        """Query persisted dependency edges, reconstruct NetworkX graph, and return graph topology."""
        stmt = select(DependencyEdge).where(DependencyEdge.repository_id == repository_id)
        if internal_only:
            stmt = stmt.where(DependencyEdge.is_internal == True)

        result = await session.execute(stmt)
        edge_records = result.scalars().all()

        # Reconstruct NetworkX directed graph
        nx_graph = nx.DiGraph()
        nodes_dict: dict[str, GraphNode] = {}
        edge_items: list[GraphEdgeItem] = []

        for r in edge_records:
            src = r.source_file
            tgt = r.target_file if (r.is_internal and r.target_file) else r.target_module

            if src not in nodes_dict:
                nodes_dict[src] = GraphNode(id=src, file_path=src, is_internal=True)
                nx_graph.add_node(src, is_internal=True)

            if tgt not in nodes_dict:
                nodes_dict[tgt] = GraphNode(
                    id=tgt,
                    file_path=tgt,
                    is_internal=r.is_internal,
                )
                nx_graph.add_node(tgt, is_internal=r.is_internal)

            nx_graph.add_edge(src, tgt)

            edge_items.append(
                GraphEdgeItem(
                    id=str(r.id),
                    source_file=r.source_file,
                    target_module=r.target_module,
                    target_file=r.target_file,
                    import_statement=r.import_statement,
                    line_number=r.line_number,
                    is_internal=r.is_internal,
                    imported_symbols=r.imported_symbols,
                    source="graph_derived",  # Hard Rule 5
                )
            )

        # Compute in/out degrees for nodes
        in_degrees = dict(nx_graph.in_degree())
        out_degrees = dict(nx_graph.out_degree())
        for node_id, node in nodes_dict.items():
            node.in_degree = int(in_degrees.get(node_id, 0))
            node.out_degree = int(out_degrees.get(node_id, 0))

        # Check DAG and cycles
        is_dag = nx.is_directed_acyclic_graph(nx_graph) if nx_graph.number_of_nodes() > 0 else True
        cycles_count = 0
        if not is_dag:
            try:
                cycles_count = len(list(nx.simple_cycles(nx_graph)))
            except Exception:  # noqa: BLE001
                cycles_count = 1

        density = float(nx.density(nx_graph)) if nx_graph.number_of_nodes() > 1 else 0.0

        # Identify top imported internal modules
        sorted_nodes = sorted(
            [n for n in nodes_dict.values() if n.is_internal],
            key=lambda item: item.in_degree,
            reverse=True,
        )
        top_imported = [
            {
                "file_path": n.file_path,
                "in_degree": n.in_degree,
                "out_degree": n.out_degree,
            }
            for n in sorted_nodes[:10]
            if n.in_degree > 0
        ]

        summary = GraphSummary(
            total_nodes=len(nodes_dict),
            internal_edges_count=len([e for e in edge_items if e.is_internal]),
            external_edges_count=len([e for e in edge_items if not e.is_internal]),
            cycles_count=cycles_count,
            is_dag=is_dag,
            density=round(density, 4),
            top_imported_modules=top_imported,
        )

        scan_id_val = (
            str(edge_records[0].scan_id) if edge_records and edge_records[0].scan_id else None
        )

        return GraphResponse(
            repository_id=str(repository_id),
            scan_id=scan_id_val,
            source="graph_derived",  # Hard Rule 5
            summary=summary,
            nodes=list(nodes_dict.values()),
            edges=edge_items,
        )

    async def compute_impact(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        changed_files: list[str],
        max_depth: int = 3,
        include_changed: bool = False,
    ) -> ImpactResponse:
        """Compute reverse reachability impact analysis for a set of changed files."""
        # Query internal edges
        stmt = select(DependencyEdge).where(
            DependencyEdge.repository_id == repository_id,
            DependencyEdge.is_internal.is_(True),
        )
        result = await session.execute(stmt)
        edge_records = result.scalars().all()

        nx_graph = nx.DiGraph()
        for r in edge_records:
            src = r.source_file
            tgt = r.target_file if r.target_file else r.target_module
            nx_graph.add_edge(src, tgt)

        return analyze_change_impact(
            graph=nx_graph,
            repository_id=str(repository_id),
            changed_files=changed_files,
            max_depth=max_depth,
            include_changed=include_changed,
        )


_graph_service: DependencyGraphService | None = None


def get_graph_service() -> DependencyGraphService:
    """Provide singleton instance of DependencyGraphService."""
    global _graph_service
    if _graph_service is None:
        _graph_service = DependencyGraphService()
    return _graph_service
