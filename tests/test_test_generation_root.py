"""Root verification tests for AI Test Generation (P5-02).

Acceptance Criteria:
    - Test generation stored as generated_tests with status 'unvalidated'.
    - Hard Rule 5: Source labelled strictly as 'llm_generated'.
    - Schema and migration verification (c3d4e5f6a7b8_create_generated_tests).
"""

from pathlib import Path

from app.tests_gen.models import GeneratedTest
from app.tests_gen.schemas import (
    GeneratedTestListResponse,
    GeneratedTestResponse,
    GenerateTestRequest,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = REPO_ROOT / "apps" / "api" / "alembic" / "versions"


def test_generated_test_model_unvalidated_status_and_rule_5() -> None:
    """Verify GeneratedTest entity defaults to status='unvalidated' and source='llm_generated'."""
    test_obj = GeneratedTest(
        target_file="app/repos/filter.py",
        test_name="test_filter_edge_case",
        test_code="def test_filter(): assert True",
        test_file_path="tests/generated/test_filter.py",
    )
    assert test_obj.status == "unvalidated"
    assert test_obj.source == "llm_generated"
    assert test_obj.test_framework == "pytest"

    as_dict = test_obj.to_dict()
    assert as_dict["status"] == "unvalidated"
    assert as_dict["source"] == "llm_generated"


def test_generated_test_schemas_rule_5() -> None:
    """Verify Pydantic schemas enforce source='llm_generated'."""
    req = GenerateTestRequest(target_file="app/core/db.py")
    assert req.target_file == "app/core/db.py"
    assert req.test_type == "unit"

    resp = GeneratedTestResponse(
        id="test-123",
        repository_id="repo-123",
        target_file="app/core/db.py",
        test_name="test_db_connection",
        test_code="def test_db_connection(): pass",
        test_file_path="tests/generated/test_db.py",
        status="unvalidated",
        model_version="gpt-4o-mini",
        created_at="2026-11-13T00:00:00Z",
        updated_at="2026-11-13T00:00:00Z",
    )
    assert resp.source == "llm_generated"
    assert resp.status == "unvalidated"

    list_resp = GeneratedTestListResponse(
        repository_id="repo-123",
        total_count=1,
        unvalidated_count=1,
        passed_count=0,
        failed_count=0,
        tests=[resp],
    )
    assert list_resp.source == "llm_generated"
    assert list_resp.unvalidated_count == 1


def test_alembic_migration_c3d4e5f6a7b8_exists() -> None:
    """Verify Alembic migration file for generated_tests table exists."""
    migration_file = MIGRATIONS_DIR / "c3d4e5f6a7b8_create_generated_tests.py"
    assert migration_file.exists(), f"Migration file not found at {migration_file}"
    content = migration_file.read_text(encoding="utf-8")
    assert 'revision: str = "c3d4e5f6a7b8"' in content
    assert 'down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"' in content
    assert "generated_tests" in content
    assert "unvalidated" in content
