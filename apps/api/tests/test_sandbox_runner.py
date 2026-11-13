"""Unit and integration tests for Docker Sandbox Runner (P5-03).

Acceptance Criteria:
    - Docker sandbox runner executes generated tests with resource constraints:
        * No network access (--network none)
        * Memory limit (512m)
        * CPU limit (1.0)
        * Process timeout limit (20s)
    - Status transitions from 'unvalidated' -> 'passed' | 'failed' | 'error':
        * Exit code 0 -> 'passed'
        * Exit code 1 (assertion failure) -> 'failed'
        * Exit code > 1 or timeout -> 'error'
    - Supporting modules correctly gathered and provided to execution workspace.
    - API endpoints:
        * POST /repositories/{id}/tests/{test_id}/run
        * POST /repositories/{id}/tests/run-all
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.indexing.models import CodeChunkRecord
from app.main import app
from app.repos.models import Repository
from app.tests_gen.models import GeneratedTest
from app.tests_gen.sandbox import (
    DockerSandboxRunner,
    SandboxConfig,
    SandboxRunResult,
    _write_files_to_dir,
)
from app.tests_gen.service import TestGenerationService


@pytest.mark.asyncio
async def test_sandbox_config_defaults() -> None:
    """Verify default sandbox isolation and resource limits."""
    config = SandboxConfig()
    assert config.image == "python:3.12-slim"
    assert config.memory_limit == "512m"
    assert config.cpu_limit == "1.0"
    assert config.network_disabled is True
    assert config.timeout_seconds == 20


@pytest.mark.asyncio
async def test_write_files_to_dir(tmp_path: Any) -> None:
    """Verify file hierarchy written to sandbox workspace."""
    target_dir = str(tmp_path)
    test_code = "def test_foo(): assert True\n"
    test_file_path = "tests/test_foo.py"
    supporting_files = {
        "app/utils.py": "def add(a, b): return a + b\n",
        "app/math/sub.py": "def sub(a, b): return a - b\n",
    }

    clean_path = _write_files_to_dir(
        target_dir=target_dir,
        test_code=test_code,
        test_file_path=test_file_path,
        supporting_files=supporting_files,
    )

    assert clean_path == "tests/test_foo.py"
    assert (tmp_path / "tests" / "test_foo.py").read_text() == test_code
    assert (tmp_path / "app" / "utils.py").read_text() == supporting_files["app/utils.py"]
    assert (tmp_path / "app" / "math" / "sub.py").read_text() == supporting_files["app/math/sub.py"]


@pytest.mark.asyncio
async def test_docker_command_assembly() -> None:
    """Verify Docker CLI arguments enforce hard security boundaries."""
    runner = DockerSandboxRunner()

    captured_cmd: list[str] = []

    async def mock_create_subprocess_exec(*cmd: str, **kwargs: Any) -> Any:
        nonlocal captured_cmd
        captured_cmd = list(cmd)
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"1 passed in 0.02s", b"")
        mock_proc.returncode = 0
        return mock_proc

    with (
        patch.object(runner, "is_docker_available", return_value=True),
        patch("asyncio.create_subprocess_exec", side_effect=mock_create_subprocess_exec),
    ):
        result = await runner.run_test(
            test_code="def test_ok(): assert 1 == 1\n",
            test_file_path="tests/test_math.py",
        )

        assert result.status == "passed"
        assert result.exit_code == 0
        assert result.runner_type == "docker"

        # Verify command flags
        assert captured_cmd[0] == "docker"
        assert captured_cmd[1] == "run"
        assert "--rm" in captured_cmd
        assert "--network" in captured_cmd
        assert captured_cmd[captured_cmd.index("--network") + 1] == "none"
        assert "--memory" in captured_cmd
        assert captured_cmd[captured_cmd.index("--memory") + 1] == "512m"
        assert "--cpus" in captured_cmd
        assert captured_cmd[captured_cmd.index("--cpus") + 1] == "1.0"
        assert "--security-opt" in captured_cmd
        assert captured_cmd[captured_cmd.index("--security-opt") + 1] == "no-new-privileges:true"
        assert ":/workspace:ro" in " ".join(captured_cmd)


@pytest.mark.asyncio
async def test_sandbox_docker_status_mappings() -> None:
    """Verify exit code status mappings: 0 -> passed, 1 -> failed, >1 -> error."""
    runner = DockerSandboxRunner()

    async def make_mock_runner(exit_code: int, stdout: str, stderr: str) -> Any:
        async def mock_exec(*cmd: str, **kwargs: Any) -> Any:
            mock_proc = AsyncMock()
            mock_proc.communicate.return_value = (stdout.encode(), stderr.encode())
            mock_proc.returncode = exit_code
            return mock_proc

        return mock_exec

    with patch.object(runner, "is_docker_available", return_value=True):
        # 1. Exit code 0 -> passed
        with patch(
            "asyncio.create_subprocess_exec", side_effect=await make_mock_runner(0, "1 passed", "")
        ):
            res = await runner.run_test("def test_ok(): assert True")
            assert res.status == "passed"
            assert res.exit_code == 0

        # 2. Exit code 1 -> failed (assertion failure)
        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=await make_mock_runner(1, "1 failed", "AssertionError"),
        ):
            res = await runner.run_test("def test_fail(): assert False")
            assert res.status == "failed"
            assert res.exit_code == 1
            assert res.error_message == "Pytest assertion failure"

        # 3. Exit code 2 -> error (pytest command-line or collection error)
        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=await make_mock_runner(2, "", "SyntaxError"),
        ):
            res = await runner.run_test("def test_err(:")
            assert res.status == "error"
            assert res.exit_code == 2


@pytest.mark.asyncio
async def test_sandbox_docker_timeout_handling() -> None:
    """Verify timeout terminates process and sets status to error with code 124."""
    runner = DockerSandboxRunner(config=SandboxConfig(timeout_seconds=1))

    async def mock_exec_timeout(*cmd: str, **kwargs: Any) -> Any:
        mock_proc = AsyncMock()
        mock_proc.communicate.side_effect = TimeoutError()
        mock_proc.kill = MagicMock()
        mock_proc.wait = AsyncMock()
        return mock_proc

    with (
        patch.object(runner, "is_docker_available", return_value=True),
        patch("asyncio.create_subprocess_exec", side_effect=mock_exec_timeout),
    ):
        res = await runner.run_test("import time; time.sleep(100)")
        assert res.status == "error"
        assert res.exit_code == 124
        assert "timed out" in res.stderr.lower()


@pytest.mark.asyncio
async def test_isolated_process_runner_real_execution() -> None:
    """Verify isolated process fallback executes genuine Python tests accurately."""
    runner = DockerSandboxRunner()

    with patch.object(runner, "is_docker_available", return_value=False):
        # Test passing case
        res_pass = await runner.run_test(
            test_code="def test_add(): assert 1 + 1 == 2\n",
            test_file_path="test_math.py",
        )
        assert res_pass.status == "passed"
        assert res_pass.exit_code == 0
        assert res_pass.runner_type == "isolated_process"

        # Test assertion failure case
        res_fail = await runner.run_test(
            test_code="def test_add(): assert 1 + 1 == 999\n",
            test_file_path="test_math.py",
        )
        assert res_fail.status == "failed"
        assert res_fail.exit_code == 1

        # Test syntax error case
        res_err = await runner.run_test(
            test_code="def broken_syntax(:\n",
            test_file_path="test_err.py",
        )
        assert res_err.status == "error"
        assert res_err.exit_code != 0


@pytest.mark.asyncio
async def test_service_execute_sandbox_test() -> None:
    """Verify TestGenerationService.execute_sandbox_test transitions test status and records output."""
    repo_id = uuid.uuid4()
    test_id = uuid.uuid4()

    mock_test = GeneratedTest(
        id=test_id,
        repository_id=repo_id,
        test_name="test_filter_rule",
        test_file_path="tests/test_filter.py",
        target_file="app/repos/filter.py",
        target_symbol="filter_path",
        status="unvalidated",
        source="llm_generated",
        test_code="def test_filter_rule(): assert True",
        execution_output=None,
        error_message=None,
    )

    mock_chunk = CodeChunkRecord(
        id=uuid.uuid4(),
        repository_id=repo_id,
        file_path="app/repos/filter.py",
        start_line=1,
        end_line=20,
        content="def filter_path(p: str) -> bool: return True\n",
        context_header="filter header",
    )

    mock_session = MagicMock(spec=AsyncSession)

    def mock_get(entity_cls: Any, pk: Any) -> Any:
        if pk == test_id:
            return mock_test
        return None

    mock_session.get = AsyncMock(side_effect=mock_get)

    # Mock chunk retrieval for supporting files
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [mock_chunk]
    res_mock = MagicMock()
    res_mock.scalars.return_value = scalars_mock
    mock_session.execute = AsyncMock(return_value=res_mock)

    mock_sandbox = MagicMock(spec=DockerSandboxRunner)
    mock_sandbox.run_test = AsyncMock(
        return_value=SandboxRunResult(
            status="passed",
            exit_code=0,
            stdout="1 passed in 0.05s",
            stderr="",
            execution_duration_ms=50,
            error_message=None,
            runner_type="docker",
        )
    )

    service = TestGenerationService()

    updated = await service.execute_sandbox_test(
        session=mock_session,
        repository_id=repo_id,
        test_id=test_id,
        sandbox_runner=mock_sandbox,
    )

    assert updated.status == "passed"
    assert updated.execution_output == "1 passed in 0.05s"
    assert updated.execution_duration_ms == 50
    assert updated.error_message is None
    assert mock_sandbox.run_test.called


@pytest.mark.asyncio
async def test_api_run_test_endpoint() -> None:
    """Verify POST /repositories/{id}/tests/{test_id}/run endpoint."""
    repo_id = uuid.uuid4()
    test_id = uuid.uuid4()

    mock_repo = Repository(
        id=repo_id,
        full_name="test-repo",
        url="https://github.com/example/repo",
        default_branch="main",
        status="ready",
    )

    mock_test = GeneratedTest(
        id=test_id,
        repository_id=repo_id,
        test_name="test_login",
        test_file_path="tests/test_login.py",
        target_file="app/auth.py",
        target_symbol="login",
        status="unvalidated",
        source="llm_generated",
        test_code="def test_login(): assert True",
    )

    mock_session = MagicMock(spec=AsyncSession)

    def mock_get(entity_cls: Any, pk: Any) -> Any:
        if entity_cls == Repository and pk == repo_id:
            return mock_repo
        if entity_cls == GeneratedTest and pk == test_id:
            return mock_test
        return None

    mock_session.get = AsyncMock(side_effect=mock_get)

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []
    res_mock = MagicMock()
    res_mock.scalars.return_value = scalars_mock
    mock_session.execute = AsyncMock(return_value=res_mock)

    mock_sandbox = MagicMock(spec=DockerSandboxRunner)
    mock_sandbox.run_test = AsyncMock(
        return_value=SandboxRunResult(
            status="passed",
            exit_code=0,
            stdout="1 passed in 0.01s",
            stderr="",
            execution_duration_ms=25,
            error_message=None,
            runner_type="docker",
        )
    )

    async def override_get_db() -> Any:
        yield mock_session

    from app.tests_gen.service import get_test_generation_service

    test_svc = TestGenerationService()

    # Patch execute_sandbox_test directly on service to verify API binding
    test_svc.execute_sandbox_test = AsyncMock(  # type: ignore[method-assign]
        return_value=GeneratedTest(
            id=test_id,
            repository_id=repo_id,
            test_name="test_login",
            test_file_path="tests/test_login.py",
            target_file="app/auth.py",
            target_symbol="login",
            status="passed",
            source="llm_generated",
            test_code="def test_login(): assert True",
            execution_output="1 passed in 0.01s",
            execution_duration_ms=25,
        )
    )

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_test_generation_service] = lambda: test_svc

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/repositories/{repo_id}/tests/{test_id}/run")
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == str(test_id)
            assert data["status"] == "passed"
            assert data["source"] == "llm_generated"
            assert data["execution_output"] == "1 passed in 0.01s"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_run_all_tests_endpoint() -> None:
    """Verify POST /repositories/{id}/tests/run-all batch endpoint."""
    repo_id = uuid.uuid4()
    test1_id = uuid.uuid4()
    test2_id = uuid.uuid4()

    mock_repo = Repository(
        id=repo_id,
        full_name="test-repo",
        url="https://github.com/example/repo",
        default_branch="main",
        status="ready",
    )

    t1 = GeneratedTest(
        id=test1_id,
        repository_id=repo_id,
        test_name="test_one",
        test_file_path="tests/test_one.py",
        target_file="app/one.py",
        status="passed",
        source="llm_generated",
        test_code="def test_one(): assert 1 == 1",
    )
    t2 = GeneratedTest(
        id=test2_id,
        repository_id=repo_id,
        test_name="test_two",
        test_file_path="tests/test_two.py",
        target_file="app/two.py",
        status="failed",
        source="llm_generated",
        test_code="def test_two(): assert 1 == 2",
    )

    mock_session = MagicMock(spec=AsyncSession)
    mock_session.get = AsyncMock(return_value=mock_repo)

    from app.tests_gen.service import get_test_generation_service

    test_svc = TestGenerationService()
    test_svc.execute_all_unvalidated = AsyncMock(return_value=[t1, t2])  # type: ignore[method-assign]

    async def override_get_db() -> Any:
        yield mock_session

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_test_generation_service] = lambda: test_svc

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(f"/repositories/{repo_id}/tests/run-all")
            assert resp.status_code == 200
            data = resp.json()
            assert data["repository_id"] == str(repo_id)
            assert data["total_executed"] == 2
            assert data["passed_count"] == 1
            assert data["failed_count"] == 1
            assert data["error_count"] == 0
            assert data["source"] == "llm_generated"
            assert len(data["results"]) == 2
    finally:
        app.dependency_overrides.clear()
