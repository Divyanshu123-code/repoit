"""Unit and integration tests for Ruff runner, normalizer, and static findings API (P4-01)."""

import tempfile
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.main import app
from app.repos.models import Repository
from app.static.models import StaticFinding
from app.static.runner import (
    classify_rule,
    normalize_ruff_json,
    resolve_ruff_binary,
    run_ruff_check,
)
from app.static.schemas import StaticFindingsResponse
from app.static.service import StaticAnalysisService, get_static_service


def test_classify_rule_categories_and_severities() -> None:
    """Test rule code classification maps accurately to categories and severities."""
    # Security rules (flake8-bandit)
    sec_cat, sec_sev = classify_rule("S101")
    assert sec_cat == "security"
    assert sec_sev == "error"

    sec2_cat, sec2_sev = classify_rule("S105")
    assert sec2_cat == "security"
    assert sec2_sev == "error"

    # Syntax / fatal runtime errors
    syn_cat, syn_sev = classify_rule("F821")
    assert syn_cat == "syntax"
    assert syn_sev == "error"

    # Bugbear risks
    bug_cat, bug_sev = classify_rule("B008")
    assert bug_cat == "bugrisk"
    assert bug_sev == "warning"

    # Style / line length
    style_cat, style_sev = classify_rule("E501")
    assert style_cat == "style"
    assert style_sev == "warning"

    # Unused import info
    lint_cat, lint_sev = classify_rule("F401")
    assert lint_cat == "lint"
    assert lint_sev == "info"

    # Isort info
    isort_cat, isort_sev = classify_rule("I001")
    assert isort_cat == "style"
    assert isort_sev == "info"


def test_normalize_ruff_json_ac_and_rule_5() -> None:
    """P4-01 AC: findings stored with rule, severity, line, and Hard Rule 5 source: static."""
    sample_json = [
        {
            "code": "F401",
            "filename": "/tmp/test_project/app/module.py",
            "location": {"row": 12, "column": 8},
            "end_location": {"row": 12, "column": 14},
            "message": "`os` imported but unused",
            "url": "https://docs.astral.sh/ruff/rules/unused-import",
            "fix": {"message": "Remove unused import: `os`"},
        },
        {
            "code": "S101",
            "filename": "/tmp/test_project/app/auth.py",
            "location": {"row": 45, "column": 5},
            "end_location": {"row": 45, "column": 25},
            "message": "Use of `assert` detected",
            "url": "https://docs.astral.sh/ruff/rules/assert",
            "fix": None,
        },
    ]

    base_dir = "/tmp/test_project"
    findings = normalize_ruff_json(sample_json, base_dir=base_dir)

    assert len(findings) == 2

    # Finding 1 verification
    f1 = findings[0]
    assert f1.rule == "F401"
    assert f1.severity == "info"
    assert f1.line_start == 12
    assert f1.line_end == 12
    assert f1.column_start == 8
    assert f1.column_end == 14
    assert f1.file_path == "app/module.py"  # Normalized relative path
    assert f1.fix_available is True
    assert f1.fix_message == "Remove unused import: `os`"
    assert f1.source == "static"  # Hard Rule 5

    # Finding 2 verification
    f2 = findings[1]
    assert f2.rule == "S101"
    assert f2.category == "security"
    assert f2.severity == "error"
    assert f2.line_start == 45
    assert f2.file_path == "app/auth.py"
    assert f2.source == "static"  # Hard Rule 5


def test_resolve_ruff_binary() -> None:
    """Test Ruff binary path resolution finds an executable."""
    bin_path = resolve_ruff_binary()
    assert bin_path is not None
    assert "ruff" in bin_path


def test_run_ruff_check_on_fixture_directory() -> None:
    """Test running Ruff check on a temporary directory with known issues."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        py_file = tmp_path / "bad_code.py"
        py_file.write_text(
            "import sys\nimport os\n\ndef test_fn():\n    unused_var = 100\n    assert True\n",
            encoding="utf-8",
        )

        findings = run_ruff_check(tmp_path)
        assert len(findings) >= 2

        rules = {f.rule for f in findings}
        # Should detect unused import (F401) and/or unused variable (F841) or assert (S101)
        assert any(r in rules for r in ["F401", "F841", "S101"])

        for f in findings:
            assert f.file_path == "bad_code.py"
            assert f.line_start > 0
            assert f.source == "static"  # Hard Rule 5
            assert f.severity in ["error", "warning", "info"]


def test_static_finding_model_to_dict() -> None:
    """Test StaticFinding SQLAlchemy model serialization."""
    repo_id = uuid.uuid4()
    finding = StaticFinding(
        repository_id=repo_id,
        file_path="app/server.py",
        rule="B008",
        category="bugrisk",
        severity="warning",
        message="Do not perform function call in argument defaults",
        line_start=34,
        line_end=34,
        column_start=15,
        column_end=30,
        fix_available=False,
        source="static",
    )

    data = finding.to_dict()
    assert data["file_path"] == "app/server.py"
    assert data["rule"] == "B008"
    assert data["severity"] == "warning"
    assert data["line_start"] == 34
    assert data["source"] == "static"  # Hard Rule 5
    assert "created_at" in data


@pytest.mark.asyncio
async def test_api_get_findings_repo_not_found() -> None:
    """GET /repositories/{id}/findings returns 404 for nonexistent repository."""
    nonexistent_id = uuid.uuid4()

    mock_db = MagicMock(spec=AsyncSession)
    mock_db.get.return_value = None

    async def override_get_db_session() -> Any:
        yield mock_db

    app.dependency_overrides[get_db_session] = override_get_db_session
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/repositories/{nonexistent_id}/findings")
            assert resp.status_code == 404
            assert "not found" in resp.json()["detail"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_get_findings_success() -> None:
    """GET /repositories/{id}/findings returns valid StaticFindingsResponse with summary and items."""
    repo_id = uuid.uuid4()
    mock_repo = Repository(
        id=repo_id,
        full_name="org/project",
        source="github",
        default_branch="main",
        status="ready",
    )

    mock_db = MagicMock(spec=AsyncSession)
    mock_db.get.return_value = mock_repo

    mock_service = MagicMock(spec=StaticAnalysisService)
    mock_response = StaticFindingsResponse(
        repository_id=str(repo_id),
        scan_id=None,
        source="static",
        summary={
            "total_findings": 3,
            "error_count": 1,
            "warning_count": 1,
            "info_count": 1,
            "affected_files_count": 2,
            "top_rules": [{"rule": "F401", "category": "lint", "severity": "info", "count": 1}],
        },
        findings=[
            {
                "id": str(uuid.uuid4()),
                "file_path": "app/main.py",
                "rule": "S101",
                "category": "security",
                "severity": "error",
                "message": "Use of assert detected",
                "line_start": 25,
                "line_end": 25,
                "column_start": 5,
                "column_end": 20,
                "rule_url": "https://docs.astral.sh/ruff/rules/assert",
                "fix_available": False,
                "fix_message": None,
                "source": "static",
                "created_at": "2026-11-12T12:00:00Z",
            }
        ],
    )
    mock_service.get_repository_findings.return_value = mock_response

    async def override_get_db_session() -> Any:
        yield mock_db

    def override_get_static_service() -> StaticAnalysisService:
        return mock_service

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_static_service] = override_get_static_service
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/repositories/{repo_id}/findings")
            assert resp.status_code == 200
            data = resp.json()
            assert data["repository_id"] == str(repo_id)
            assert data["source"] == "static"  # Hard Rule 5
            assert data["summary"]["total_findings"] == 3
            assert data["summary"]["error_count"] == 1
            assert len(data["findings"]) == 1
            assert data["findings"][0]["rule"] == "S101"
            assert data["findings"][0]["severity"] == "error"
            assert data["findings"][0]["line_start"] == 25
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_trigger_static_scan() -> None:
    """POST /repositories/{id}/findings/scan triggers Ruff scan and returns findings."""
    repo_id = uuid.uuid4()
    mock_repo = Repository(
        id=repo_id,
        full_name="org/project",
        source="github",
        default_branch="main",
        status="ready",
    )

    mock_db = MagicMock(spec=AsyncSession)
    mock_db.get.return_value = mock_repo
    mock_scan_res = MagicMock()
    mock_scan_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_scan_res

    mock_service = MagicMock(spec=StaticAnalysisService)
    mock_service.store_normalized_findings.return_value = []
    mock_response = StaticFindingsResponse(
        repository_id=str(repo_id),
        scan_id=None,
        source="static",
        summary={
            "total_findings": 0,
            "error_count": 0,
            "warning_count": 0,
            "info_count": 0,
            "affected_files_count": 0,
            "top_rules": [],
        },
        findings=[],
    )
    mock_service.get_repository_findings.return_value = mock_response

    async def override_get_db_session() -> Any:
        yield mock_db

    def override_get_static_service() -> StaticAnalysisService:
        return mock_service

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_static_service] = override_get_static_service
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/repositories/{repo_id}/findings/scan")
            assert resp.status_code == 200
            data = resp.json()
            assert data["source"] == "static"
    finally:
        app.dependency_overrides.clear()
