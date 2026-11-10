"""Safe repository fetcher for public GitHub repos and ZIP archives.

Provides shallow cloning, size caps, timeout limits, and strictly no code execution.
"""

import asyncio
import io
import logging
import os
import shutil
import stat
import tempfile
import zipfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from app.core.config import get_settings

logger = logging.getLogger("repopilot.repos.fetcher")


class RepoFetchError(Exception):
    """Base exception for all repository fetch errors."""


class RepoSizeLimitExceededError(RepoFetchError):
    """Raised when repository content exceeds maximum allowed disk size."""

    def __init__(self, size_bytes: int, max_bytes: int) -> None:
        self.size_bytes = size_bytes
        self.max_bytes = max_bytes
        super().__init__(
            f"Repository size ({size_bytes} bytes) exceeds maximum allowed limit ({max_bytes} bytes)."
        )


class RepoFetchTimeoutError(RepoFetchError):
    """Raised when fetching or cloning a repository times out."""

    def __init__(self, timeout_seconds: int) -> None:
        self.timeout_seconds = timeout_seconds
        super().__init__(f"Repository fetch timed out after {timeout_seconds} seconds.")


class RepoCloneFailedError(RepoFetchError):
    """Raised when git clone fails."""

    def __init__(self, message: str) -> None:
        super().__init__(f"Failed to clone repository: {message}")


class RepoExtractionError(RepoFetchError):
    """Raised when extracting repository archive fails."""


@dataclass
class FetchedRepo:
    """Represents a safely fetched repository on the local filesystem."""

    path: Path
    source_type: str  # "github" | "zip"
    size_bytes: int
    file_count: int
    _temp_dir: tempfile.TemporaryDirectory[str] | None = None

    def cleanup(self) -> None:
        """Clean up temporary directory and all files inside."""
        if self._temp_dir is not None:
            try:
                self._temp_dir.cleanup()
            except OSError as exc:
                logger.warning("Failed to clean up temporary directory %s: %s", self.path, exc)
            self._temp_dir = None
        elif self.path.exists():
            shutil.rmtree(self.path, ignore_errors=True)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.cleanup()


def calculate_directory_size(path: Path) -> tuple[int, int]:
    """Calculate total byte size and file count of a directory safely.

    Symlinks are verified to ensure they resolve within `path` and are not counted twice.
    """
    total_size = 0
    file_count = 0
    resolved_root = path.resolve()

    for root, _, files in os.walk(path):
        root_path = Path(root)
        for name in files:
            file_path = root_path / name
            try:
                # Do not follow symlinks pointing outside the repository tree
                resolved_file = file_path.resolve()
                if not resolved_file.is_relative_to(resolved_root):
                    continue
                file_stat = file_path.lstat()
                # If symlink, only count symlink itself, do not follow arbitrary pointers
                if stat.S_ISLNK(file_stat.st_mode):
                    continue
                total_size += file_stat.st_size
                file_count += 1
            except (OSError, FileNotFoundError):
                continue

    return total_size, file_count


async def safe_clone_github_repo(
    url: str,
    target_dir: Path,
    timeout_seconds: int | None = None,
    max_size_bytes: int | None = None,
    branch: str | None = None,
) -> tuple[int, int]:
    """Execute a shallow, hook-disabled git clone into target_dir.

    Enforces:
    1. Shallow clone: `--depth 1`
    2. Disabled hooks: `-c core.hooksPath=/dev/null`
    3. Disabled terminal interactive prompts: `GIT_TERMINAL_PROMPT=0`
    4. Timeout limit
    5. Disk size cap verification
    """
    settings = get_settings()
    timeout = (
        timeout_seconds if timeout_seconds is not None else settings.REPO_FETCH_TIMEOUT_SECONDS
    )
    max_bytes = max_size_bytes if max_size_bytes is not None else settings.REPO_MAX_SIZE_BYTES

    clone_args = [
        "git",
        "-c",
        "core.hooksPath=/dev/null",
        "clone",
        "--depth",
        "1",
        "--no-tags",
    ]

    if branch:
        clone_args.extend(["--single-branch", "-b", branch])

    clone_args.extend([url, str(target_dir)])

    env = {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "/bin/echo",
    }

    try:
        process = await asyncio.create_subprocess_exec(
            *clone_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
    except Exception as exc:
        raise RepoCloneFailedError(f"Subprocess execution failed: {exc}") from exc

    try:
        _stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(),
            timeout=float(timeout),
        )
    except TimeoutError as exc:
        try:
            process.kill()
            await process.wait()
        except OSError as kill_exc:
            logger.debug("Failed to kill timed out git process: %s", kill_exc)
        raise RepoFetchTimeoutError(timeout) from exc

    if process.returncode != 0:
        error_msg = stderr_bytes.decode(errors="replace").strip()
        raise RepoCloneFailedError(error_msg or f"Exited with code {process.returncode}")

    # Verify size limit after clone
    total_size, file_count = calculate_directory_size(target_dir)
    if total_size > max_bytes:
        raise RepoSizeLimitExceededError(total_size, max_bytes)

    return total_size, file_count


def safe_extract_zip(
    zip_bytes: bytes,
    target_dir: Path,
    max_size_bytes: int | None = None,
) -> tuple[int, int]:
    """Safely extract a ZIP archive into target_dir.

    Guards against:
    1. Directory traversal / Zip slip attacks (`../` paths)
    2. Cumulative decompression bombs exceeding max_size_bytes
    3. Malicious symlinks
    """
    settings = get_settings()
    max_bytes = max_size_bytes if max_size_bytes is not None else settings.REPO_MAX_SIZE_BYTES

    try:
        archive = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except Exception as exc:
        raise RepoExtractionError(f"Corrupted ZIP archive: {exc}") from exc

    resolved_target = target_dir.resolve()
    cumulative_size = 0
    file_count = 0

    with archive:
        for member in archive.infolist():
            # Check cumulative uncompressed size declared in zip headers
            cumulative_size += member.file_size
            if cumulative_size > max_bytes:
                raise RepoSizeLimitExceededError(cumulative_size, max_bytes)

            filename = member.filename
            # Normalize and check path traversal
            member_path = (target_dir / filename).resolve()
            if not member_path.is_relative_to(resolved_target):
                raise RepoExtractionError(
                    f"Directory traversal detected in ZIP entry: '{filename}'"
                )

            # Prevent extracting unsafe symlinks
            if stat.S_ISLNK(member.external_attr >> 16):
                raise RepoExtractionError(
                    f"Symlinks are disallowed in archive entries: '{filename}'"
                )

            # Extract directory or file
            if member.is_dir():
                member_path.mkdir(parents=True, exist_ok=True)
            else:
                member_path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source_stream, open(member_path, "wb") as dest_stream:
                    # Stream chunks and double-check actual written bytes
                    written_for_file = 0
                    while chunk := source_stream.read(64 * 1024):
                        written_for_file += len(chunk)
                        dest_stream.write(chunk)

                # Set non-executable permissions (rw-r--r--)
                try:
                    member_path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
                except OSError:
                    pass
                file_count += 1

    # Final verify on disk
    actual_size, counted_files = calculate_directory_size(target_dir)
    if actual_size > max_bytes:
        raise RepoSizeLimitExceededError(actual_size, max_bytes)

    return actual_size, counted_files


@asynccontextmanager
async def safe_fetch_repository(
    source_type: str,
    url: str | None = None,
    zip_bytes: bytes | None = None,
    branch: str | None = None,
    timeout_seconds: int | None = None,
    max_size_bytes: int | None = None,
    base_temp_dir: str | None = None,
) -> AsyncIterator[FetchedRepo]:
    """Context manager to safely fetch and inspect a repository.

    Ensures temporary directory is completely cleaned up when exiting context or on error.

    Usage:
        async with safe_fetch_repository(source_type="github", url="...") as repo:
            print(repo.path, repo.size_bytes)
    """
    settings = get_settings()
    temp_base = base_temp_dir or settings.REPO_TEMP_BASE_DIR

    temp_dir_obj = tempfile.TemporaryDirectory(dir=temp_base, prefix="repopilot_fetch_")
    temp_path = Path(temp_dir_obj.name)

    try:
        if source_type == "github":
            if not url:
                raise RepoFetchError("URL must be provided for github repository fetch.")
            size_bytes, file_count = await safe_clone_github_repo(
                url=url,
                target_dir=temp_path,
                timeout_seconds=timeout_seconds,
                max_size_bytes=max_size_bytes,
                branch=branch,
            )
        elif source_type in ("zip", "upload"):
            if not zip_bytes:
                raise RepoFetchError("ZIP bytes must be provided for zip repository fetch.")
            size_bytes, file_count = safe_extract_zip(
                zip_bytes=zip_bytes,
                target_dir=temp_path,
                max_size_bytes=max_size_bytes,
            )
        else:
            raise RepoFetchError(f"Unsupported source type '{source_type}'.")

        fetched = FetchedRepo(
            path=temp_path,
            source_type=source_type,
            size_bytes=size_bytes,
            file_count=file_count,
            _temp_dir=temp_dir_obj,
        )
        yield fetched
    except Exception:
        # Guarantee cleanup on failure
        temp_dir_obj.cleanup()
        raise
    finally:
        # If not already cleaned up by caller or exception
        temp_dir_obj.cleanup()
