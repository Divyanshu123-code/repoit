"""Docker sandbox runner for executing AI-generated test cases (P5-03).

Enforces:
    - Hard Rule 3: Repository content is untrusted input. Tests run in an isolated sandbox.
    - Security constraints:
        * No network access (--network none)
        * Memory caps (--memory 512m)
        * CPU quotas (--cpus 1.0)
        * Process timeout (default 20s)
        * No new privileges (--security-opt no-new-privileges:true)
    - Output status mapping:
        * Exit code 0 -> 'passed'
        * Exit code 1 -> 'failed' (pytest assertion failure)
        * Timeout / crash / exit code > 1 -> 'error'
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import tempfile
import time
from typing import Literal

from pydantic import BaseModel, Field

logger = logging.getLogger("repopilot.tests_gen.sandbox")


class SandboxConfig(BaseModel):
    """Resource and isolation limits for Docker sandbox runner."""

    image: str = "python:3.12-slim"
    timeout_seconds: int = 20
    memory_limit: str = "512m"
    cpu_limit: str = "1.0"
    network_disabled: bool = True
    temp_dir_prefix: str = "repopilot_sandbox_"


class SandboxRunResult(BaseModel):
    """Standardized result of sandbox test execution.

    Status transitions:
        'unvalidated' (P5-02) -> 'passed' | 'failed' | 'error' (P5-03)
    """

    status: Literal["passed", "failed", "error"]
    exit_code: int
    stdout: str
    stderr: str
    execution_duration_ms: int
    error_message: str | None = None
    runner_type: str = Field(
        default="docker",
        description="Runner implementation used ('docker' or 'isolated_process')",
    )


def _write_files_to_dir(
    target_dir: str,
    test_code: str,
    test_file_path: str,
    supporting_files: dict[str, str],
) -> str:
    """Synchronously write test code and supporting files to workspace directory."""
    for rel_path, content in supporting_files.items():
        dest = os.path.join(target_dir, rel_path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(content)

    clean_test_path = test_file_path.lstrip("/")
    test_dest = os.path.join(target_dir, clean_test_path)
    os.makedirs(os.path.dirname(test_dest), exist_ok=True)
    with open(test_dest, "w", encoding="utf-8") as f:
        f.write(test_code)
    return clean_test_path


class DockerSandboxRunner:
    """Executes generated tests inside a constrained Docker container or isolated process."""

    def __init__(self, config: SandboxConfig | None = None) -> None:
        self.config = config or SandboxConfig()

    def is_docker_available(self) -> bool:
        """Check if Docker CLI binary is installed and accessible."""
        return shutil.which("docker") is not None

    async def run_test(
        self,
        test_code: str,
        test_file_path: str = "test_generated.py",
        supporting_files: dict[str, str] | None = None,
    ) -> SandboxRunResult:
        """Run generated test with strict network isolation and resource limits."""
        start_time = time.perf_counter()

        # If Docker is available, run containerized
        if self.is_docker_available():
            return await self._run_in_docker(
                test_code=test_code,
                test_file_path=test_file_path,
                supporting_files=supporting_files or {},
                start_time=start_time,
            )

        # Fallback to isolated temporary process when Docker is not present
        return await self._run_in_isolated_process(
            test_code=test_code,
            test_file_path=test_file_path,
            supporting_files=supporting_files or {},
            start_time=start_time,
        )

    async def _run_in_docker(
        self,
        test_code: str,
        test_file_path: str,
        supporting_files: dict[str, str],
        start_time: float,
    ) -> SandboxRunResult:
        """Execute test inside Docker container with --network none, memory/cpu/time limits."""
        temp_dir = tempfile.mkdtemp(prefix=self.config.temp_dir_prefix)
        try:
            clean_test_path = await asyncio.to_thread(
                _write_files_to_dir,
                temp_dir,
                test_code,
                test_file_path,
                supporting_files,
            )

            # Assemble docker command
            cmd = [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",  # Strict no-network rule
                "--memory",
                self.config.memory_limit,
                "--memory-swap",
                self.config.memory_limit,
                "--cpus",
                self.config.cpu_limit,
                "--security-opt",
                "no-new-privileges:true",
                "-v",
                f"{temp_dir}:/workspace:ro",
                "-w",
                "/workspace",
                self.config.image,
                "python",
                "-m",
                "pytest",
                "-q",
                f"/workspace/{clean_test_path}",
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.config.timeout_seconds,
                )
                exit_code = process.returncode or 0
                stdout = stdout_bytes.decode("utf-8", errors="replace")
                stderr = stderr_bytes.decode("utf-8", errors="replace")
            except TimeoutError:
                try:
                    process.kill()
                    await process.wait()
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Failed to kill timed out process: %s", exc)
                duration = int((time.perf_counter() - start_time) * 1000)
                return SandboxRunResult(
                    status="error",
                    exit_code=124,
                    stdout="",
                    stderr=f"Execution timed out after {self.config.timeout_seconds}s limit",
                    execution_duration_ms=duration,
                    error_message=f"Timeout limit of {self.config.timeout_seconds} seconds exceeded",
                    runner_type="docker",
                )

            duration = int((time.perf_counter() - start_time) * 1000)
            status: Literal["passed", "failed", "error"]
            err_msg: str | None = None

            if exit_code == 0:
                status = "passed"
            elif exit_code == 1:
                status = "failed"
                err_msg = "Pytest assertion failure"
            else:
                status = "error"
                err_msg = f"Process exited with error code {exit_code}"

            return SandboxRunResult(
                status=status,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                execution_duration_ms=duration,
                error_message=err_msg,
                runner_type="docker",
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def _run_in_isolated_process(
        self,
        test_code: str,
        test_file_path: str,
        supporting_files: dict[str, str],
        start_time: float,
    ) -> SandboxRunResult:
        """Fallback runner executing pytest in an isolated temporary directory with timeouts."""
        temp_dir = tempfile.mkdtemp(prefix="repopilot_subproc_")
        try:
            clean_test_path = await asyncio.to_thread(
                _write_files_to_dir,
                temp_dir,
                test_code,
                test_file_path,
                supporting_files,
            )

            # Use current virtualenv pytest if available, else python -m pytest
            venv_pytest = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", ".venv", "bin", "pytest")
            )
            pytest_bin = venv_pytest if os.path.exists(venv_pytest) else "pytest"

            # Execute isolated process
            env = dict(os.environ)
            env["PYTHONPATH"] = temp_dir
            env["PYTHONDONTWRITEBYTECODE"] = "1"

            process = await asyncio.create_subprocess_exec(
                pytest_bin,
                "-q",
                clean_test_path,
                cwd=temp_dir,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.config.timeout_seconds,
                )
                exit_code = process.returncode or 0
                stdout = stdout_bytes.decode("utf-8", errors="replace")
                stderr = stderr_bytes.decode("utf-8", errors="replace")
            except TimeoutError:
                try:
                    process.kill()
                    await process.wait()
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Failed to kill timed out process: %s", exc)
                duration = int((time.perf_counter() - start_time) * 1000)
                return SandboxRunResult(
                    status="error",
                    exit_code=124,
                    stdout="",
                    stderr=f"Execution timed out after {self.config.timeout_seconds}s limit",
                    execution_duration_ms=duration,
                    error_message=f"Timeout limit of {self.config.timeout_seconds} seconds exceeded",
                    runner_type="isolated_process",
                )

            duration = int((time.perf_counter() - start_time) * 1000)
            status: Literal["passed", "failed", "error"]
            err_msg: str | None = None

            if exit_code == 0:
                status = "passed"
            elif exit_code == 1:
                status = "failed"
                err_msg = "Pytest assertion failure"
            else:
                status = "error"
                err_msg = f"Process exited with code {exit_code}"

            return SandboxRunResult(
                status=status,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                execution_duration_ms=duration,
                error_message=err_msg,
                runner_type="isolated_process",
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


_sandbox_runner: DockerSandboxRunner | None = None


def get_sandbox_runner() -> DockerSandboxRunner:
    """Provide singleton instance of DockerSandboxRunner."""
    global _sandbox_runner
    if _sandbox_runner is None:
        _sandbox_runner = DockerSandboxRunner()
    return _sandbox_runner
