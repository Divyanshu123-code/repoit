"""Unit and integration tests for worker scan_repo pipeline (P1-06)."""

import asyncio
import io
import uuid
import zipfile
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import get_db_session
from app.main import app
from app.repos.models import Repository, RepositoryScan
from app.repos.scan_service import (
    RepoNotFoundError,
    get_latest_scan_for_repo,
    list_scans_for_repo,
    run_scan_pipeline,
)


def create_sample_zip(files: dict[str, str]) -> bytes:
    """Helper to build an in-memory zip archive."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buffer.getvalue()


class FakeAsyncSession:
    """In-memory mock session supporting Repository and RepositoryScan entities."""

    def __init__(self) -> None:
        self.entities: dict[uuid.UUID, Any] = {}
        self.committed = False

    def add(self, obj: Any) -> None:
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        self.entities[obj.id] = obj

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, obj: Any) -> None:
        pass

    async def execute(self, stmt: Any) -> Any:
        # Check if querying RepositoryScan or Repository
        target_model = None
        for column in getattr(stmt, "column_descriptions", []):
            target_model = column.get("type")
            break

        class FakeResult:
            def __init__(self, items: list[Any]) -> None:
                self._items = items

            def scalar_one_or_none(self) -> Any:
                return self._items[0] if self._items else None

            def scalars(self) -> Any:
                class ScalarList:
                    def __init__(self, data: list[Any]) -> None:
                        self._data = data

                    def all(self) -> list[Any]:
                        return self._data

                return ScalarList(self._items)

        if target_model is RepositoryScan or "repository_scans" in str(stmt):
            scans = [obj for obj in self.entities.values() if isinstance(obj, RepositoryScan)]
            # Sort descending by created_at
            scans.sort(key=lambda s: s.created_at, reverse=True)
            return FakeResult(scans)

        # Default: Repository
        repos = [obj for obj in self.entities.values() if isinstance(obj, Repository)]
        return FakeResult(repos)


@pytest.fixture
def fake_session() -> FakeAsyncSession:
    return FakeAsyncSession()


@pytest.fixture
def sample_zip_bytes() -> bytes:
    files = {
        "calculator.py": """def add(a: int, b: int) -> int:
    \"\"\"Add two numbers.\"\"\"
    return a + b

def subtract(a: int, b: int) -> int:
    return a - b
""",
        "main.py": """from calculator import add

def main():
    res = add(1, 2)
    print(res)

if __name__ == '__main__':
    main()
""",
    }
    return create_sample_zip(files)


@pytest.mark.asyncio
async def test_full_scan_pipeline_success(
    fake_session: FakeAsyncSession, sample_zip_bytes: bytes
) -> None:
    """Verify that a complete repository scan pipeline executes all stages and sets status ready."""
    repo = Repository(
        id=uuid.uuid4(),
        source="upload",
        full_name="test_repo",
        status="registered",
    )
    fake_session.add(repo)

    scan = await run_scan_pipeline(
        session=fake_session,  # type: ignore[arg-type]
        repo_id=repo.id,
        zip_bytes=sample_zip_bytes,
    )

    # Assert scan outcomes
    assert scan.status == "completed"
    assert scan.current_stage == "completed"
    assert scan.file_count == 2
    assert scan.total_symbols >= 3  # add, subtract, main
    assert scan.total_lines > 0
    assert scan.error_message is None
    assert scan.completed_at is not None
    assert scan.metrics_summary is not None
    assert scan.metrics_summary["modules_count"] == 2
    assert scan.metrics_summary["total_loc"] > 0

    # Assert stage tracking
    assert scan.stage_progress is not None
    assert "fetching" in scan.stage_progress
    assert "filtering" in scan.stage_progress
    assert "parsing" in scan.stage_progress
    assert "metrics" in scan.stage_progress

    # Assert repository transitioned to ready
    assert repo.status == "ready"
    assert repo.indexed_at is not None


@pytest.mark.asyncio
async def test_scan_killed_mid_scan_status_failed_with_reason(
    fake_session: FakeAsyncSession, sample_zip_bytes: bytes
) -> None:
    """Acceptance Criteria: killed mid-scan -> status failed with reason."""
    repo = Repository(
        id=uuid.uuid4(),
        source="upload",
        full_name="test_repo",
        status="registered",
    )
    fake_session.add(repo)

    # Simulate termination/kill at 'parsing' stage
    with pytest.raises(asyncio.CancelledError):
        await run_scan_pipeline(
            session=fake_session,  # type: ignore[arg-type]
            repo_id=repo.id,
            zip_bytes=sample_zip_bytes,
            mock_kill_stage="parsing",
        )

    # Retrieve scan
    scan = await get_latest_scan_for_repo(fake_session, repo.id)  # type: ignore[arg-type]
    assert scan is not None
    assert scan.status == "failed"
    assert scan.current_stage == "failed"
    assert scan.error_message is not None
    assert "killed mid-scan at stage 'parsing'" in scan.error_message
    assert repo.status == "failed"


@pytest.mark.asyncio
async def test_scan_rerun_after_failure_works(
    fake_session: FakeAsyncSession, sample_zip_bytes: bytes
) -> None:
    """Acceptance Criteria: re-run works after a failed or aborted scan."""
    repo = Repository(
        id=uuid.uuid4(),
        source="upload",
        full_name="test_repo",
        status="registered",
    )
    fake_session.add(repo)

    # 1. First run fails (killed mid-scan at filtering)
    with pytest.raises(asyncio.CancelledError):
        await run_scan_pipeline(
            session=fake_session,  # type: ignore[arg-type]
            repo_id=repo.id,
            zip_bytes=sample_zip_bytes,
            mock_kill_stage="filtering",
        )

    first_scan = await get_latest_scan_for_repo(fake_session, repo.id)  # type: ignore[arg-type]
    assert first_scan is not None
    assert first_scan.status == "failed"
    assert repo.status == "failed"

    # 2. Re-run scan without errors
    second_scan = await run_scan_pipeline(
        session=fake_session,  # type: ignore[arg-type]
        repo_id=repo.id,
        zip_bytes=sample_zip_bytes,
    )

    assert second_scan.status == "completed"
    assert second_scan.current_stage == "completed"
    assert second_scan.file_count == 2
    assert repo.status == "ready"
    assert repo.indexed_at is not None

    # History shows both scans
    all_scans = await list_scans_for_repo(fake_session, repo.id)  # type: ignore[arg-type]
    assert len(all_scans) >= 2


@pytest.mark.asyncio
async def test_scan_pipeline_fails_on_corrupt_archive(fake_session: FakeAsyncSession) -> None:
    """Verify that corrupt archive fails gracefully and records error reason."""
    repo = Repository(
        id=uuid.uuid4(),
        source="upload",
        full_name="corrupt_repo",
        status="registered",
    )
    fake_session.add(repo)

    scan = await run_scan_pipeline(
        session=fake_session,  # type: ignore[arg-type]
        repo_id=repo.id,
        zip_bytes=b"not a valid zip",
    )

    assert scan.status == "failed"
    assert scan.current_stage == "failed"
    assert scan.error_message is not None
    assert "Corrupted ZIP archive" in scan.error_message
    assert repo.status == "failed"


@pytest.mark.asyncio
async def test_scan_pipeline_nonexistent_repo(fake_session: FakeAsyncSession) -> None:
    """Verify ValueError when attempting to scan non-existent repository."""
    with pytest.raises(RepoNotFoundError):
        await run_scan_pipeline(
            session=fake_session,  # type: ignore[arg-type]
            repo_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_api_trigger_and_get_scan(sample_zip_bytes: bytes) -> None:
    """Verify API endpoints for triggering and retrieving scans."""
    fake_session = FakeAsyncSession()
    repo_id = uuid.uuid4()
    repo = Repository(
        id=repo_id,
        source="upload",
        full_name="api_test_repo",
        status="registered",
    )
    fake_session.add(repo)

    async def override_get_db_session() -> AsyncIterator[FakeAsyncSession]:
        yield fake_session

    app.dependency_overrides[get_db_session] = override_get_db_session

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),  # type: ignore[arg-type]
            base_url="http://test",
        ) as client:
            # 1. Trigger scan
            with patch("app.api.repos.run_scan_pipeline") as mock_pipeline:
                fake_scan = RepositoryScan(
                    id=uuid.uuid4(),
                    repository_id=repo_id,
                    status="completed",
                    current_stage="completed",
                    file_count=3,
                    total_lines=150,
                    total_symbols=12,
                )
                mock_pipeline.return_value = fake_scan
                fake_session.add(fake_scan)

                resp = await client.post(f"/repositories/{repo_id}/scan")
                assert resp.status_code == 202
                data = resp.json()
                assert data["repository_id"] == str(repo_id)
                assert data["status"] == "completed"

            # 2. Get latest scan
            resp_get = await client.get(f"/repositories/{repo_id}/scan")
            assert resp_get.status_code == 200
            assert resp_get.json()["id"] == str(fake_scan.id)

            # 3. Get all scans
            resp_list = await client.get(f"/repositories/{repo_id}/scans")
            assert resp_list.status_code == 200
            assert len(resp_list.json()) >= 1
    finally:
        app.dependency_overrides.pop(get_db_session, None)
