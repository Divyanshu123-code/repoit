"""Root verification tests for Docker Sandbox Runner (P5-03).

Acceptance Criteria:
    - Docker sandbox runner executes generated tests in isolated sandbox.
    - Security constraints enforced:
        * No network access (--network none)
        * Memory caps (--memory 512m)
        * CPU quotas (--cpus 1.0)
        * Process timeout limit (20s)
    - Test execution transitions status from 'unvalidated' -> 'passed' | 'failed' | 'error'.
    - Hard Rule 5: Source labelled strictly as 'llm_generated'.
"""

import pytest

from app.tests_gen.models import GeneratedTest
from app.tests_gen.sandbox import DockerSandboxRunner, SandboxConfig, SandboxRunResult
from app.tests_gen.schemas import BatchRunResponse, GeneratedTestResponse


def test_sandbox_config_security_bounds() -> None:
    """Verify security boundaries and resource quotas in SandboxConfig."""
    cfg = SandboxConfig()
    assert cfg.image == "python:3.12-slim"
    assert cfg.timeout_seconds == 20
    assert cfg.memory_limit == "512m"
    assert cfg.cpu_limit == "1.0"
    assert cfg.network_disabled is True


def test_sandbox_run_result_validation() -> None:
    """Verify SandboxRunResult status constraints and transitions."""
    res_pass = SandboxRunResult(
        status="passed",
        exit_code=0,
        stdout="1 passed in 0.01s",
        stderr="",
        execution_duration_ms=10,
        runner_type="docker",
    )
    assert res_pass.status == "passed"
    assert res_pass.exit_code == 0

    res_fail = SandboxRunResult(
        status="failed",
        exit_code=1,
        stdout="1 failed",
        stderr="AssertionError",
        execution_duration_ms=15,
        error_message="Pytest assertion failure",
        runner_type="docker",
    )
    assert res_fail.status == "failed"
    assert res_fail.exit_code == 1

    res_err = SandboxRunResult(
        status="error",
        exit_code=124,
        stdout="",
        stderr="Timeout after 20s",
        execution_duration_ms=20000,
        error_message="Timeout exceeded",
        runner_type="docker",
    )
    assert res_err.status == "error"
    assert res_err.exit_code == 124


def test_batch_run_response_rule_5() -> None:
    """Verify BatchRunResponse enforces Hard Rule 5 source='llm_generated'."""
    batch_resp = BatchRunResponse(
        repository_id="repo-123",
        total_executed=3,
        passed_count=2,
        failed_count=1,
        error_count=0,
        results=[],
    )
    assert batch_resp.source == "llm_generated"
    assert batch_resp.total_executed == 3
    assert batch_resp.passed_count == 2
    assert batch_resp.failed_count == 1
    assert batch_resp.error_count == 0


@pytest.mark.asyncio
async def test_sandbox_runner_isolated_fallback() -> None:
    """Verify isolated process runner executes basic test cleanly."""
    runner = DockerSandboxRunner()
    result = await runner._run_in_isolated_process(
        test_code="def test_basic_math(): assert 2 + 2 == 4\n",
        test_file_path="test_math.py",
        supporting_files={},
        start_time=0.0,
    )
    assert result.status == "passed"
    assert result.exit_code == 0
    assert result.runner_type == "isolated_process"
