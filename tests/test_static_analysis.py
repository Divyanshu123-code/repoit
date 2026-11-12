"""Root tests for static analysis, normalized finding schema, and migration (P4-01)."""

from pathlib import Path

from app.static.models import StaticFinding
from app.static.runner import classify_rule, normalize_ruff_json


class TestStaticFindingsSchemaAndMigration:
    """Verifies P4-01 acceptance criteria: findings stored with rule, severity, line."""

    def test_migration_file_exists(self) -> None:
        """Verify that alembic migration for static_findings table exists."""
        versions_dir = Path("apps/api/alembic/versions")
        migrations = list(versions_dir.glob("*create_static_findings.py"))
        assert len(migrations) == 1, "create_static_findings migration must exist"

        content = migrations[0].read_text(encoding="utf-8")
        assert (
            'op.create_table(\n        "static_findings"' in content
            or "op.create_table(\n        'static_findings'" in content
            or '"static_findings"' in content
        )
        assert "rule" in content
        assert "severity" in content
        assert "line_start" in content
        assert "source" in content

    def test_static_finding_model_fields(self) -> None:
        """Verify StaticFinding entity has required AC columns and Rule 5 source label."""
        assert hasattr(StaticFinding, "id")
        assert hasattr(StaticFinding, "repository_id")
        assert hasattr(StaticFinding, "scan_id")
        assert hasattr(StaticFinding, "file_path")
        assert hasattr(StaticFinding, "rule")  # AC: rule
        assert hasattr(StaticFinding, "severity")  # AC: severity
        assert hasattr(StaticFinding, "line_start")  # AC: line
        assert hasattr(StaticFinding, "line_end")
        assert hasattr(StaticFinding, "message")
        assert hasattr(StaticFinding, "source")  # Hard Rule 5

    def test_rule_5_source_labelling_in_static_findings(self) -> None:
        """Hard Rule 5: Every API/UI result is labelled by source: static."""
        raw = [
            {
                "code": "F401",
                "filename": "/repo/foo.py",
                "location": {"row": 1, "column": 1},
                "end_location": {"row": 1, "column": 10},
                "message": "Unused import",
            }
        ]
        findings = normalize_ruff_json(raw, base_dir="/repo")
        assert len(findings) == 1
        assert findings[0].source == "static"

    def test_rule_classification_matrix(self) -> None:
        """Verify severity and category classifications across rule prefixes."""
        # Security: S101 -> error
        assert classify_rule("S101") == ("security", "error")
        # Syntax: F821 -> error
        assert classify_rule("F821") == ("syntax", "error")
        # Bugrisk: B008 -> warning
        assert classify_rule("B008") == ("bugrisk", "warning")
        # Style: E501 -> warning
        assert classify_rule("E501") == ("style", "warning")
        # Lint: F401 -> info
        assert classify_rule("F401") == ("lint", "info")

    def test_scan_service_integrates_static_analysis(self) -> None:
        """Verify that scan_service.py invokes static analysis during scan pipeline."""
        scan_service_path = Path("apps/api/app/repos/scan_service.py")
        content = scan_service_path.read_text(encoding="utf-8")

        assert "run_and_store_findings" in content
        assert "get_static_service" in content
