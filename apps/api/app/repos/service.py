"""Repository registration and validation service."""

import io
import re
import uuid
import zipfile
from collections.abc import Sequence
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repos.models import Repository

# Valid GitHub owner: 1-39 alphanumeric characters or single hyphens (not leading/trailing)
GITHUB_OWNER_REGEX = re.compile(r"^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,37}[a-zA-Z0-9])?$")
# Valid GitHub repository name: alphanumeric, hyphens, underscores, periods (1-100 chars)
GITHUB_REPO_REGEX = re.compile(r"^[a-zA-Z0-9_.-]{1,100}$")


class InvalidRepoURLError(ValueError):
    """Raised when an invalid or unsupported repository URL is provided."""


class InvalidUploadError(ValueError):
    """Raised when an uploaded file is invalid or corrupted."""


def validate_github_url(raw_url: str) -> tuple[str, str]:
    """Validate a public GitHub URL and extract (normalized_url, full_name).

    Args:
        raw_url: The URL string supplied by the user.

    Returns:
        tuple of (normalized_url, full_name) where full_name is "owner/repo".

    Raises:
        InvalidRepoURLError: If the URL is not a valid public GitHub repository URL.
    """
    if not raw_url or not isinstance(raw_url, str):
        raise InvalidRepoURLError("Repository URL cannot be empty.")

    cleaned_url = raw_url.strip()
    try:
        parsed = urlparse(cleaned_url)
    except Exception as exc:
        raise InvalidRepoURLError(f"Malformed repository URL: {exc}") from exc

    if parsed.scheme not in ("http", "https"):
        raise InvalidRepoURLError(
            f"Invalid URL scheme '{parsed.scheme}'. Only 'https://' or 'http://' GitHub URLs are accepted."
        )

    netloc = parsed.netloc.lower()
    if netloc not in ("github.com", "www.github.com"):
        raise InvalidRepoURLError(
            f"Unsupported repository host '{parsed.netloc}'. Only public GitHub repositories (github.com) are supported."
        )

    # Normalize path segments (remove leading/trailing slashes and .git extension)
    path_segments = [seg for seg in parsed.path.strip("/").split("/") if seg]
    if len(path_segments) != 2:
        raise InvalidRepoURLError(
            "Invalid GitHub repository path. URL must follow the format 'https://github.com/owner/repository'."
        )

    owner, repo_name = path_segments[0], path_segments[1]
    repo_name = repo_name.removesuffix(".git")

    if not GITHUB_OWNER_REGEX.match(owner):
        raise InvalidRepoURLError(f"Invalid GitHub username or organization name '{owner}'.")

    if not GITHUB_REPO_REGEX.match(repo_name) or repo_name in (".", ".."):
        raise InvalidRepoURLError(f"Invalid GitHub repository name '{repo_name}'.")

    full_name = f"{owner}/{repo_name}"
    normalized_url = f"https://github.com/{full_name}"
    return normalized_url, full_name


def validate_zip_content(filename: str, content: bytes) -> str:
    """Validate that the uploaded bytes constitute a non-empty, readable ZIP file.

    Returns:
        A sanitized repository name based on the filename.
    """
    if not content:
        raise InvalidUploadError("Uploaded archive cannot be empty.")

    # Check magic bytes for ZIP: PK\x03\x04
    if not content.startswith(b"PK\x03\x04"):
        raise InvalidUploadError("Uploaded file is not a valid ZIP archive.")

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            if not zf.namelist():
                raise InvalidUploadError("ZIP archive contains no files.")
    except zipfile.BadZipFile as exc:
        raise InvalidUploadError(f"Corrupted ZIP archive: {exc}") from exc

    # Sanitize filename
    clean_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", filename).strip("_.")
    if clean_name.lower().endswith(".zip"):
        clean_name = clean_name[:-4]

    return clean_name or "uploaded_repository"


async def register_github_repository(
    session: AsyncSession,
    url: str,
) -> Repository:
    """Validate and register a public GitHub repository.

    If the repository has already been registered, the existing record is returned.
    """
    normalized_url, full_name = validate_github_url(url)

    # Check for existing repository with this URL
    stmt = select(Repository).where(Repository.url == normalized_url)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    repo = Repository(
        source="github",
        url=normalized_url,
        full_name=full_name,
        default_branch="main",
        status="registered",
    )
    session.add(repo)
    await session.commit()
    await session.refresh(repo)
    return repo


async def register_zip_repository(
    session: AsyncSession,
    filename: str,
    content: bytes,
) -> Repository:
    """Validate and register an uploaded ZIP repository archive."""
    full_name = validate_zip_content(filename, content)

    repo = Repository(
        source="upload",
        url=None,
        full_name=full_name,
        default_branch="main",
        status="registered",
    )
    session.add(repo)
    await session.commit()
    await session.refresh(repo)
    return repo


async def list_repositories(session: AsyncSession) -> Sequence[Repository]:
    """Retrieve all registered repositories ordered by created_at descending."""
    stmt = select(Repository).order_by(Repository.created_at.desc())
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_repository_by_id(
    session: AsyncSession,
    repo_id: str | uuid.UUID,
) -> Repository | None:
    """Retrieve a single repository by its UUID."""
    if isinstance(repo_id, str):
        try:
            repo_uuid = uuid.UUID(repo_id)
        except ValueError:
            return None
    else:
        repo_uuid = repo_id

    stmt = select(Repository).where(Repository.id == repo_uuid)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
