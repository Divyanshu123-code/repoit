"""Root tests for import graph migration, models, and scan integration (P4-02)."""

from pathlib import Path

from app.graph.models import DependencyEdge


class TestImportGraphSchemaAndMigration:
    """Verifies P4-02: Import graph builder (NetworkX) + persisted edges."""

    def test_migration_file_exists(self) -> None:
        """Verify that alembic migration for dependency_edges table exists."""
        versions_dir = Path("apps/api/alembic/versions")
        migrations = list(versions_dir.glob("*create_dependency_edges.py"))
        assert len(migrations) == 1, "create_dependency_edges migration must exist"

        content = migrations[0].read_text(encoding="utf-8")
        assert "dependency_edges" in content
        assert "source_file" in content
        assert "target_module" in content
        assert "target_file" in content
        assert "is_internal" in content
        assert "imported_symbols" in content
        assert "source" in content

    def test_dependency_edge_model_fields(self) -> None:
        """Verify DependencyEdge entity has required columns and Rule 5 source label."""
        assert hasattr(DependencyEdge, "id")
        assert hasattr(DependencyEdge, "repository_id")
        assert hasattr(DependencyEdge, "scan_id")
        assert hasattr(DependencyEdge, "source_file")
        assert hasattr(DependencyEdge, "target_module")
        assert hasattr(DependencyEdge, "target_file")
        assert hasattr(DependencyEdge, "import_statement")
        assert hasattr(DependencyEdge, "line_number")
        assert hasattr(DependencyEdge, "is_internal")
        assert hasattr(DependencyEdge, "imported_symbols")
        assert hasattr(DependencyEdge, "source")  # Hard Rule 5

    def test_rule_5_source_labelling_in_dependency_edge(self) -> None:
        """Hard Rule 5: Every API/UI result is labelled by source: graph_derived."""
        edge = DependencyEdge(
            source_file="a.py",
            target_module="b",
            target_file="b.py",
            is_internal=True,
            imported_symbols=[],
        )
        assert edge.source == "graph_derived"

    def test_scan_service_integrates_graph_builder(self) -> None:
        """Verify that scan_service.py invokes graph builder during scan pipeline."""
        scan_service_path = Path("apps/api/app/repos/scan_service.py")
        content = scan_service_path.read_text(encoding="utf-8")

        assert "build_and_store_graph" in content
        assert "get_graph_service" in content
