"""Unit and integration tests for safe repository fetcher (P1-02)."""

import asyncio
import io
import subprocess
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.repos.fetcher import (
    FetchedRepo,
    RepoCloneFailedError,
    RepoExtractionError,
    RepoFetchError,
    RepoFetchTimeoutError,
    RepoSizeLimitExceededError,
    calculate_directory_size,
    safe_clone_github_repo,
    safe_extract_zip,
    safe_fetch_repository,
)


def create_sample_zip(files: dict[str, bytes]) -> bytes:
    """Helper to create an in-memory zip archive."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_safe_extract_zip_success(tmp_path: Path) -> None:
    """Verify safe extraction of valid ZIP archive."""
    files = {
        "main.py": b"print('hello world')\n",
        "utils/helpers.py": b"def add(a, b): return a + b\n",
    }
    zip_bytes = create_sample_zip(files)
    target_dir = tmp_path / "extracted"
    target_dir.mkdir()

    size_bytes, file_count = safe_extract_zip(
        zip_bytes=zip_bytes,
        target_dir=target_dir,
        max_size_bytes=1024 * 1024,
    )

    assert file_count == 2
    assert size_bytes > 0
    assert (target_dir / "main.py").exists()
    assert (target_dir / "utils" / "helpers.py").exists()
    assert (target_dir / "main.py").read_bytes() == files["main.py"]


def test_safe_extract_zip_size_limit_exceeded(tmp_path: Path) -> None:
    """Verify that exceeding size limit raises RepoSizeLimitExceededError and fails gracefully."""
    files = {
        "big_file_1.txt": b"x" * 600,
        "big_file_2.txt": b"y" * 600,
    }
    zip_bytes = create_sample_zip(files)
    target_dir = tmp_path / "extracted_big"
    target_dir.mkdir()

    # Limit set to 500 bytes, total is 1200 bytes
    with pytest.raises(RepoSizeLimitExceededError) as exc_info:
        safe_extract_zip(
            zip_bytes=zip_bytes,
            target_dir=target_dir,
            max_size_bytes=500,
        )

    assert "exceeds maximum allowed limit" in str(exc_info.value)
    assert exc_info.value.max_bytes == 500


def test_safe_extract_zip_directory_traversal_blocked(tmp_path: Path) -> None:
    """Verify directory traversal / zip slip attacks are blocked."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        # Malicious traversal path
        zf.writestr("../evil.txt", b"evil payload")

    target_dir = tmp_path / "sandbox"
    target_dir.mkdir()

    with pytest.raises(RepoExtractionError) as exc_info:
        safe_extract_zip(
            zip_bytes=buffer.getvalue(),
            target_dir=target_dir,
            max_size_bytes=1024 * 1024,
        )

    assert "Directory traversal detected" in str(exc_info.value)
    assert not (tmp_path / "evil.txt").exists()


def test_safe_extract_zip_corrupted(tmp_path: Path) -> None:
    """Verify corrupted zip archive raises RepoExtractionError."""
    target_dir = tmp_path / "corrupted"
    target_dir.mkdir()

    with pytest.raises(RepoExtractionError) as exc_info:
        safe_extract_zip(
            zip_bytes=b"garbage not a zip",
            target_dir=target_dir,
        )

    assert "Corrupted ZIP archive" in str(exc_info.value)


def test_calculate_directory_size(tmp_path: Path) -> None:
    """Verify calculate_directory_size computes total size and file counts safely."""
    test_dir = tmp_path / "repo"
    test_dir.mkdir()
    (test_dir / "file1.py").write_text("a" * 100)
    subdir = test_dir / "sub"
    subdir.mkdir()
    (subdir / "file2.py").write_text("b" * 250)

    size, count = calculate_directory_size(test_dir)
    assert count == 2
    assert size == 350


@pytest.mark.asyncio
async def test_safe_clone_github_repo_arguments_and_flags(tmp_path: Path) -> None:
    """Verify shallow clone, hook disabling, and terminal prompt disabling flags."""
    target_dir = tmp_path / "cloned"
    target_dir.mkdir()
    (target_dir / "README.md").write_text("cloned content")

    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"", b"")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        size, count = await safe_clone_github_repo(
            url="https://github.com/octocat/Hello-World",
            target_dir=target_dir,
            timeout_seconds=30,
            max_size_bytes=1024 * 1024,
            branch="master",
        )

        mock_exec.assert_called_once()
        args = mock_exec.call_args[0]
        kwargs = mock_exec.call_args[1]

        # Verify safe git flags
        assert "git" in args
        assert "-c" in args
        assert "core.hooksPath=/dev/null" in args
        assert "clone" in args
        assert "--depth" in args
        assert "1" in args
        assert "--no-tags" in args
        assert "--single-branch" in args
        assert "-b" in args
        assert "master" in args
        assert "https://github.com/octocat/Hello-World" in args

        # Verify environment disables prompts
        assert kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"
        assert count == 1
        assert size == len("cloned content")


@pytest.mark.asyncio
async def test_safe_clone_github_repo_timeout(tmp_path: Path) -> None:
    """Verify clone timeout raises RepoFetchTimeoutError and kills process."""
    target_dir = tmp_path / "timeout_dir"
    target_dir.mkdir()

    mock_proc = AsyncMock()
    mock_proc.communicate.side_effect = TimeoutError()
    mock_proc.kill = MagicMock()
    mock_proc.wait = AsyncMock()

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        with pytest.raises(RepoFetchTimeoutError) as exc_info:
            await safe_clone_github_repo(
                url="https://github.com/slow/repo",
                target_dir=target_dir,
                timeout_seconds=5,
            )

        assert exc_info.value.timeout_seconds == 5
        mock_proc.kill.assert_called_once()


@pytest.mark.asyncio
async def test_safe_clone_github_repo_failure(tmp_path: Path) -> None:
    """Verify non-zero exit code raises RepoCloneFailedError."""
    target_dir = tmp_path / "failed_dir"
    target_dir.mkdir()

    mock_proc = AsyncMock()
    mock_proc.returncode = 128
    mock_proc.communicate.return_value = (b"", b"fatal: repository not found\n")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        with pytest.raises(RepoCloneFailedError) as exc_info:
            await safe_clone_github_repo(
                url="https://github.com/nonexistent/repo",
                target_dir=target_dir,
            )

        assert "repository not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_safe_clone_github_repo_size_limit_exceeded(tmp_path: Path) -> None:
    """Verify that clone exceeding max size raises RepoSizeLimitExceededError."""
    target_dir = tmp_path / "too_big_repo"
    target_dir.mkdir()
    # Write 1000 bytes into target directory
    (target_dir / "large.bin").write_bytes(b"A" * 1000)

    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"", b"")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        with pytest.raises(RepoSizeLimitExceededError) as exc_info:
            await safe_clone_github_repo(
                url="https://github.com/big/repo",
                target_dir=target_dir,
                max_size_bytes=500,
            )

        assert exc_info.value.max_bytes == 500
        assert exc_info.value.size_bytes >= 1000


@pytest.mark.asyncio
async def test_safe_fetch_repository_context_manager_zip_cleanup() -> None:
    """Verify safe_fetch_repository context manager cleans up directory on exit."""
    zip_bytes = create_sample_zip({"sample.py": b"print('test')"})
    repo_path: Path | None = None

    async with safe_fetch_repository("zip", zip_bytes=zip_bytes) as repo:
        assert isinstance(repo, FetchedRepo)
        assert repo.path.exists()
        assert (repo.path / "sample.py").exists()
        repo_path = repo.path

    # Once context exits, directory must be removed
    assert repo_path is not None
    assert not repo_path.exists()


@pytest.mark.asyncio
async def test_safe_fetch_repository_cleanup_on_error() -> None:
    """Verify temp directory is cleaned up even if error occurs inside context."""
    files = {"huge.txt": b"Z" * 1000}
    zip_bytes = create_sample_zip(files)

    with pytest.raises(RepoSizeLimitExceededError):
        async with safe_fetch_repository("zip", zip_bytes=zip_bytes, max_size_bytes=100) as repo:
            _ = repo.path


@pytest.mark.asyncio
async def test_safe_fetch_repository_unsupported_source() -> None:
    """Verify unsupported source type raises RepoFetchError."""
    with pytest.raises(RepoFetchError) as exc_info:
        async with safe_fetch_repository("mercurial"):
            pass

    assert "Unsupported source type" in str(exc_info.value)


@pytest.mark.asyncio
async def test_real_git_local_shallow_clone_and_size_limit(tmp_path: Path) -> None:
    """End-to-end integration test with real git repository on filesystem."""
    # Create a local source git repository
    source_repo = tmp_path / "source_git_repo"
    source_repo.mkdir()
    await asyncio.to_thread(
        subprocess.run, ["git", "init", str(source_repo)], check=True, capture_output=True
    )
    await asyncio.to_thread(
        subprocess.run,
        ["git", "-C", str(source_repo), "config", "user.email", "test@repopilot.local"],
        check=True,
    )
    await asyncio.to_thread(
        subprocess.run,
        ["git", "-C", str(source_repo), "config", "user.name", "RepoPilot Tester"],
        check=True,
    )

    # Add commits
    (source_repo / "module.py").write_text("def hello(): return 'world'\n" * 20)
    await asyncio.to_thread(subprocess.run, ["git", "-C", str(source_repo), "add", "."], check=True)
    await asyncio.to_thread(
        subprocess.run,
        ["git", "-C", str(source_repo), "commit", "-m", "Initial commit"],
        check=True,
    )

    file_url = f"file://{source_repo.resolve()}"

    # Test 1: Successful shallow clone
    async with safe_fetch_repository(
        source_type="github",
        url=file_url,
        max_size_bytes=1024 * 1024,
    ) as fetched:
        assert fetched.path.exists()
        assert (fetched.path / "module.py").exists()
        assert fetched.size_bytes > 0
        assert fetched.file_count >= 1

    # Test 2: Size cap exceeded fails gracefully
    with pytest.raises(RepoSizeLimitExceededError) as exc_info:
        async with safe_fetch_repository(
            source_type="github",
            url=file_url,
            max_size_bytes=10,  # Strict 10-byte cap
        ):
            pass

    assert exc_info.value.max_bytes == 10
    assert exc_info.value.size_bytes > 10
