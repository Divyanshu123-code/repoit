"""Tests for repository registration, validation, and endpoints (P1-01)."""

import io
import uuid
import zipfile

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.repos import get_db_session
from app.main import app
from app.repos.models import Repository
from app.repos.service import (
    InvalidRepoURLError,
    InvalidUploadError,
    validate_github_url,
    validate_zip_content,
)

# ==============================================================================
# Unit Tests for URL and Upload Validation Logic
# ==============================================================================


def test_validate_github_url_success() -> None:
    """Valid public GitHub URLs should normalize to standard https URLs."""
    valid_cases = [
        ("https://github.com/psf/requests", "https://github.com/psf/requests", "psf/requests"),
        ("http://github.com/pallets/flask", "https://github.com/pallets/flask", "pallets/flask"),
        (
            "https://github.com/fastapi/fastapi.git",
            "https://github.com/fastapi/fastapi",
            "fastapi/fastapi",
        ),
        (
            "https://www.github.com/tiangolo/sqlmodel/",
            "https://github.com/tiangolo/sqlmodel",
            "tiangolo/sqlmodel",
        ),
    ]
    for raw, expected_url, expected_name in valid_cases:
        norm_url, full_name = validate_github_url(raw)
        assert norm_url == expected_url
        assert full_name == expected_name


def test_validate_github_url_rejections() -> None:
    """Invalid URLs must raise InvalidRepoURLError with descriptive messages."""
    invalid_cases = [
        "",  # empty
        "   ",  # whitespace
        "not-a-url",
        "ftp://github.com/owner/repo",  # bad scheme
        "https://gitlab.com/owner/repo",  # wrong host
        "https://bitbucket.org/owner/repo",
        "https://github.com/owner",  # missing repo
        "https://github.com/owner/repo/pull/1",  # extra path segment
        "https://github.com/-invalid-owner/repo",  # bad owner username
        "https://github.com/owner/..",  # path traversal
    ]
    for invalid in invalid_cases:
        with pytest.raises(InvalidRepoURLError):
            validate_github_url(invalid)


def test_validate_zip_content_valid() -> None:
    """Valid ZIP bytes should produce a sanitized repository name."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("test.py", "print('hello')")
    zip_bytes = buf.getvalue()

    repo_name = validate_zip_content("my-cool-project.zip", zip_bytes)
    assert repo_name == "my-cool-project"


def test_validate_zip_content_corrupted() -> None:
    """Corrupted or non-ZIP bytes should raise InvalidUploadError."""
    with pytest.raises(InvalidUploadError):
        validate_zip_content("corrupted.zip", b"not-a-real-zip-content")

    with pytest.raises(InvalidUploadError):
        validate_zip_content("empty.zip", b"")


# ==============================================================================
# Endpoint Integration Tests
# ==============================================================================


class FakeAsyncSession:
    """In-memory fake session for repository endpoint testing."""

    def __init__(self) -> None:
        self.repos: dict[uuid.UUID, Repository] = {}

    def add(self, entity: Repository) -> None:
        if not entity.id:
            entity.id = uuid.uuid4()
        self.repos[entity.id] = entity

    async def commit(self) -> None:
        pass

    async def refresh(self, entity: Repository) -> None:
        pass

    async def execute(self, stmt: object) -> object:
        items = list(self.repos.values())
        where_clause = getattr(stmt, "_where_criteria", ())
        if where_clause:
            for expr in where_clause:
                right = getattr(expr, "right", None)
                val = getattr(right, "value", None)
                if val is not None:
                    items = [r for r in items if str(r.id) == str(val) or r.url == val]
                    break

        class FakeResult:
            def __init__(self, items: list[Repository]) -> None:
                self._items = items

            def scalar_one_or_none(self) -> Repository | None:
                return self._items[0] if self._items else None

            def scalars(self) -> "FakeResult":
                return self

            def all(self) -> list[Repository]:
                return self._items

        return FakeResult(items)


@pytest.fixture
def fake_session() -> FakeAsyncSession:
    return FakeAsyncSession()


@pytest.mark.asyncio
async def test_api_register_valid_github_repo(fake_session: FakeAsyncSession) -> None:
    """POST /repositories with a valid GitHub URL returns 201 Created."""
    app.dependency_overrides[get_db_session] = lambda: fake_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/repositories",
            json={"url": "https://github.com/psf/requests"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["full_name"] == "psf/requests"
        assert data["source"] == "github"
        assert data["status"] == "registered"
        assert "id" in data

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_register_invalid_github_url_returns_422(
    fake_session: FakeAsyncSession,
) -> None:
    """POST /repositories with an invalid URL returns 422 with a structured error."""
    app.dependency_overrides[get_db_session] = lambda: fake_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/repositories",
            json={"url": "https://gitlab.com/not/supported"},
        )
        assert response.status_code == 422
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "INVALID_REPOSITORY_URL"
        assert "Only public GitHub repositories" in data["error"]["message"]

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_register_empty_url_returns_400(
    fake_session: FakeAsyncSession,
) -> None:
    """POST /repositories with empty payload returns 400 or 422."""
    app.dependency_overrides[get_db_session] = lambda: fake_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/repositories", json={})
        assert response.status_code in (400, 422)

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_upload_valid_zip_archive(fake_session: FakeAsyncSession) -> None:
    """POST /repositories/upload with a valid ZIP archive returns 201 Created."""
    app.dependency_overrides[get_db_session] = lambda: fake_session

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("main.py", "print('hello world')")
    zip_bytes = buf.getvalue()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/repositories/upload",
            files={"file": ("my_repo.zip", zip_bytes, "application/zip")},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["source"] == "upload"
        assert data["full_name"] == "my_repo"
        assert data["status"] == "registered"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_upload_invalid_zip_archive_returns_422(
    fake_session: FakeAsyncSession,
) -> None:
    """POST /repositories/upload with a corrupt file returns 422."""
    app.dependency_overrides[get_db_session] = lambda: fake_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/repositories/upload",
            files={"file": ("corrupt.zip", b"not-valid-zip", "application/zip")},
        )
        assert response.status_code == 422
        data = response.json()
        assert data["error"]["code"] == "INVALID_ARCHIVE_UPLOAD"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_list_repositories(fake_session: FakeAsyncSession) -> None:
    """GET /repositories returns list of registered repositories."""
    fake_session.add(
        Repository(
            source="github",
            url="https://github.com/foo/bar",
            full_name="foo/bar",
            status="registered",
        )
    )
    app.dependency_overrides[get_db_session] = lambda: fake_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/repositories")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["full_name"] == "foo/bar"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_get_repository_by_id(fake_session: FakeAsyncSession) -> None:
    """GET /repositories/{id} returns repo detail or 404."""
    repo = Repository(
        source="github",
        url="https://github.com/example/sample",
        full_name="example/sample",
        status="registered",
    )
    fake_session.add(repo)
    app.dependency_overrides[get_db_session] = lambda: fake_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Found
        response = await client.get(f"/repositories/{repo.id}")
        assert response.status_code == 200
        assert response.json()["full_name"] == "example/sample"

        # Not found
        non_existent = uuid.uuid4()
        response404 = await client.get(f"/repositories/{non_existent}")
        assert response404.status_code == 404
        assert response404.json()["detail"]["error"]["code"] == "REPOSITORY_NOT_FOUND"

    app.dependency_overrides.clear()
