"""Unit and integration tests for AI Test Generation (P5-02).

Acceptance Criteria:
    - Test generation endpoint synthesizes pytest tests.
    - Stored in generated_tests table with status 'unvalidated'.
    - Hard Rule 4: Secrets and tokens redacted prior to LLM calls.
    - Hard Rule 5: Labelled strictly with source: 'llm_generated'.
    - Hard Rule 7: LLM calls route strictly through LLMProvider.
"""

import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.fake_llm import FakeLLMProvider
from app.core.db import get_db_session
from app.indexing.models import CodeChunkRecord
from app.main import app
from app.repos.models import Repository
from app.static.models import StaticFinding
from app.tests_gen.models import GeneratedTest
from app.tests_gen.schemas import GenerateTestRequest
from app.tests_gen.service import TestGenerationService, get_test_generation_service


@pytest.mark.asyncio
async def test_generate_and_store_test_unvalidated_status() -> None:
    """AC Test: Synthesized test is stored with status 'unvalidated' and source 'llm_generated'."""
    repo_id = uuid.uuid4()
    mock_session = MagicMock(spec=AsyncSession)

    # Mock chunk in database
    mock_chunk = CodeChunkRecord(
        id=uuid.uuid4(),
        repository_id=repo_id,
        file_path="app/repos/filter.py",
        start_line=1,
        end_line=40,
        content=(
            "class RepoFileFilter:\n"
            "    def check_path(self, path: str) -> FilterResult:\n"
            "        ...\n"
        ),
        context_header="Repo file filtering logic",
    )

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [mock_chunk]
    res_mock = MagicMock()
    res_mock.scalars.return_value = scalars_mock
    res_mock.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = res_mock

    saved_records: list[GeneratedTest] = []

    def mock_add(record: Any) -> None:
        if isinstance(record, GeneratedTest):
            saved_records.append(record)

    mock_session.add = mock_add

    fake_llm = FakeLLMProvider()
    service = TestGenerationService(llm_provider=fake_llm)

    request = GenerateTestRequest(
        target_file="app/repos/filter.py",
        target_symbol="RepoFileFilter",
        test_type="unit",
        focus_description="Verify rejection of path traversal symlinks",
    )

    result = await service.generate_and_store_test(
        session=mock_session,
        repository_id=repo_id,
        request=request,
    )

    # Verify Acceptance Criteria
    assert result.status == "unvalidated"  # Hard requirement P5-02
    assert result.source == "llm_generated"  # Hard Rule 5
    assert result.target_file == "app/repos/filter.py"
    assert result.target_symbol == "RepoFileFilter"
    assert result.test_framework == "pytest"
    assert result.test_name.startswith("test_")
    assert "assert" in result.test_code
    assert result.test_file_path == "tests/generated/test_filter.py"
    assert result.model_version == fake_llm.model_name

    # Verify session added entity
    assert len(saved_records) == 1
    assert saved_records[0].status == "unvalidated"


@pytest.mark.asyncio
async def test_generate_regression_test_from_static_finding() -> None:
    """Verify regression test generation targeting a specific StaticFinding."""
    repo_id = uuid.uuid4()
    finding_id = uuid.uuid4()
    mock_session = MagicMock(spec=AsyncSession)

    mock_finding = StaticFinding(
        id=finding_id,
        repository_id=repo_id,
        file_path="app/core/db.py",
        rule="B008",
        category="bugrisk",
        severity="warning",
        message="Do not perform function call `Depends` in argument defaults",
        line_start=25,
        line_end=25,
        fix_available=True,
        fix_message="Use Annotated",
        source="static",
    )

    async def mock_execute(stmt: Any) -> Any:
        stmt_str = str(stmt).lower()
        res = MagicMock()
        if "from static_findings" in stmt_str:
            res.scalar_one_or_none.return_value = mock_finding
        else:
            res.scalar_one_or_none.return_value = None
            scalars = MagicMock()
            scalars.all.return_value = []
            res.scalars.return_value = scalars
        return res

    mock_session.execute = mock_execute

    fake_llm = FakeLLMProvider()
    service = TestGenerationService(llm_provider=fake_llm)

    request = GenerateTestRequest(
        target_file="app/core/db.py",
        finding_id=str(finding_id),
        test_type="regression",
        focus_description="Ensure Depends works with Annotated",
    )

    result = await service.generate_and_store_test(
        session=mock_session,
        repository_id=repo_id,
        request=request,
    )

    assert result.status == "unvalidated"
    assert result.finding_id == finding_id
    assert result.source == "llm_generated"
    # Ensure finding information was injected into LLM prompt
    assert len(fake_llm.captured_messages) > 0
    prompt_content = " ".join(m["content"] for m in fake_llm.captured_messages[-1])
    assert "B008" in prompt_content


@pytest.mark.asyncio
async def test_test_generation_hard_rule_4_secret_redaction() -> None:
    """Verify that credentials and tokens in focus/code are redacted before LLM call."""
    repo_id = uuid.uuid4()
    mock_session = MagicMock(spec=AsyncSession)

    res_mock = MagicMock()
    res_mock.scalar_one_or_none.return_value = None
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []
    res_mock.scalars.return_value = scalars_mock
    mock_session.execute.return_value = res_mock

    fake_llm = FakeLLMProvider()
    service = TestGenerationService(llm_provider=fake_llm)

    secret = "ghp_123456789012345678901234567890123456"
    request = GenerateTestRequest(
        target_file="app/config.py",
        focus_description=f"Verify token {secret} validation",
        custom_code_snippet=f"TOKEN = '{secret}'\n",
    )

    await service.generate_and_store_test(
        session=mock_session,
        repository_id=repo_id,
        request=request,
    )

    assert len(fake_llm.captured_messages) > 0
    sent_prompt = " ".join(m["content"] for m in fake_llm.captured_messages[-1])
    assert secret not in sent_prompt
    assert "[REDACTED_SECRET]" in sent_prompt or "[REDACTED_" in sent_prompt


@pytest.mark.asyncio
async def test_api_generate_and_list_tests() -> None:
    """Test POST and GET /repositories/{id}/tests endpoints."""
    repo_id = uuid.uuid4()
    mock_repo = Repository(
        id=repo_id,
        full_name="org/proj",
        source="github",
        default_branch="main",
        status="ready",
    )

    test_id = uuid.uuid4()
    mock_test_entity = GeneratedTest(
        id=test_id,
        repository_id=repo_id,
        target_file="app/repos/fetcher.py",
        target_symbol="safe_clone_github_repo",
        test_framework="pytest",
        test_name="test_safe_clone_shallow",
        test_code="def test_safe_clone_shallow():\n    assert True\n",
        test_file_path="tests/generated/test_fetcher.py",
        status="unvalidated",
        source="llm_generated",
        model_version="fake-gpt-4o-mini",
    )

    mock_db = MagicMock(spec=AsyncSession)
    mock_db.get.return_value = mock_repo

    mock_service = MagicMock(spec=TestGenerationService)
    mock_service.generate_and_store_test.return_value = mock_test_entity
    mock_service.to_response.return_value = {
        "id": str(test_id),
        "repository_id": str(repo_id),
        "target_file": "app/repos/fetcher.py",
        "target_symbol": "safe_clone_github_repo",
        "finding_id": None,
        "test_framework": "pytest",
        "test_name": "test_safe_clone_shallow",
        "test_code": "def test_safe_clone_shallow():\n    assert True\n",
        "test_file_path": "tests/generated/test_fetcher.py",
        "status": "unvalidated",
        "error_message": None,
        "execution_output": None,
        "execution_duration_ms": None,
        "source": "llm_generated",
        "model_version": "fake-gpt-4o-mini",
        "created_at": "2026-11-13T00:00:00Z",
        "updated_at": "2026-11-13T00:00:00Z",
    }
    mock_service.list_tests.return_value = {
        "repository_id": str(repo_id),
        "total_count": 1,
        "unvalidated_count": 1,
        "passed_count": 0,
        "failed_count": 0,
        "source": "llm_generated",
        "tests": [mock_service.to_response.return_value],
    }
    mock_service.get_test.return_value = mock_test_entity

    async def override_get_db_session() -> Any:
        yield mock_db

    def override_get_test_service() -> TestGenerationService:
        return mock_service

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_test_generation_service] = override_get_test_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. POST /repositories/{id}/tests/generate
            post_resp = await client.post(
                f"/repositories/{repo_id}/tests/generate",
                json={
                    "target_file": "app/repos/fetcher.py",
                    "target_symbol": "safe_clone_github_repo",
                    "test_type": "unit",
                },
            )
            assert post_resp.status_code == 201
            post_data = post_resp.json()
            assert post_data["status"] == "unvalidated"
            assert post_data["source"] == "llm_generated"
            assert post_data["test_name"] == "test_safe_clone_shallow"

            # 2. GET /repositories/{id}/tests
            get_resp = await client.get(f"/repositories/{repo_id}/tests")
            assert get_resp.status_code == 200
            get_data = get_resp.json()
            assert get_data["source"] == "llm_generated"
            assert get_data["total_count"] == 1
            assert get_data["unvalidated_count"] == 1
            assert len(get_data["tests"]) == 1

            # 3. GET /repositories/{id}/tests/{test_id}
            item_resp = await client.get(f"/repositories/{repo_id}/tests/{test_id}")
            assert item_resp.status_code == 200
            assert item_resp.json()["id"] == str(test_id)

            # 4. 404 on missing repository
            mock_db.get.return_value = None
            missing_id = uuid.uuid4()
            bad_resp = await client.post(
                f"/repositories/{missing_id}/tests/generate",
                json={"target_file": "missing.py"},
            )
            assert bad_resp.status_code == 404
    finally:
        app.dependency_overrides.clear()
