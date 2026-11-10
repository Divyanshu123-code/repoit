"""Tests for pgvector index and semantic search endpoint (P2-03).

Acceptance Criteria:
- Returns path + line range + score.
- Hard Rule 5: Every API/UI result is labelled by source ('static').
"""

import uuid
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.ai.providers.fake import FakeEmbeddingProvider
from app.api.repos import get_db_session
from app.api.search import get_search_service
from app.indexing.models import ChunkStrategy, CodeChunk, CodeChunkRecord
from app.indexing.search_service import SemanticSearchService, _cosine_similarity
from app.main import app
from app.repos.models import Repository


def test_cosine_similarity_calculation() -> None:
    """Verifies vector cosine similarity edge cases."""
    # Identical vectors -> 1.0
    assert abs(_cosine_similarity([1.0, 0.0], [1.0, 0.0]) - 1.0) < 1e-5
    # Orthogonal vectors -> 0.0
    assert abs(_cosine_similarity([1.0, 0.0], [0.0, 1.0])) < 1e-5
    # Opposite vectors -> -1.0
    assert abs(_cosine_similarity([1.0, 0.0], [-1.0, 0.0]) - (-1.0)) < 1e-5
    # Empty or mismatched vectors -> 0.0
    assert _cosine_similarity([], []) == 0.0
    assert _cosine_similarity([1.0], [1.0, 2.0]) == 0.0


class FakeSearchSession:
    """In-memory mock session supporting Repository and CodeChunkRecord."""

    def __init__(self) -> None:
        self.repos: dict[uuid.UUID, Repository] = {}
        self.chunks: dict[uuid.UUID, CodeChunkRecord] = {}

    def add(self, obj: Any) -> None:
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        if isinstance(obj, Repository):
            self.repos[obj.id] = obj
        elif isinstance(obj, CodeChunkRecord):
            self.chunks[obj.id] = obj

    async def commit(self) -> None:
        pass

    async def execute(self, stmt: Any) -> Any:
        stmt_str = str(stmt).lower()

        # Handle DELETE statement
        if "delete" in stmt_str and "code_chunks" in stmt_str:
            self.chunks.clear()

            class FakeDeleteResult:
                def all(self) -> list[Any]:
                    return []

            return FakeDeleteResult()

        # Handle SELECT Repository
        if "repositories" in stmt_str:
            target_id = None
            where_clause = getattr(stmt, "_where_criteria", ())
            for expr in where_clause:
                right = getattr(expr, "right", None)
                val = getattr(right, "value", None)
                if val is not None:
                    target_id = val
                    break

            repo = (
                self.repos.get(target_id)
                if target_id
                else next(iter(self.repos.values()))
                if self.repos
                else None
            )

            class FakeRepoResult:
                def __init__(self, item: Repository | None) -> None:
                    self._item = item

                def scalar_one_or_none(self) -> Repository | None:
                    return self._item

            return FakeRepoResult(repo)

        # Handle SELECT CodeChunkRecord
        chunk_list = list(self.chunks.values())

        class FakeChunkResult:
            def __init__(self, items: list[CodeChunkRecord]) -> None:
                self._items = items

            def scalars(self) -> "FakeChunkResult":
                return self

            def all(self) -> list[CodeChunkRecord]:
                return self._items

        return FakeChunkResult(chunk_list)


@pytest.fixture
def fake_search_db() -> FakeSearchSession:
    return FakeSearchSession()


@pytest.mark.asyncio
async def test_search_service_index_and_search(fake_search_db: FakeSearchSession) -> None:
    """Verifies indexing and semantic search results meet Acceptance Criteria."""
    repo_id = uuid.uuid4()
    provider = FakeEmbeddingProvider(dimension=32)
    service = SemanticSearchService(embedding_provider=provider)

    chunks = [
        CodeChunk(
            file_path="app/auth/login.py",
            start_line=10,
            end_line=25,
            content="def authenticate_user(token: str) -> bool:\n    return verify_jwt(token)",
            strategy=ChunkStrategy.SYMBOL_BASED,
            symbol_name="authenticate_user",
            symbol_type="function",
            context_header="# File: app/auth/login.py\n# Symbol: authenticate_user\n",
            char_count=65,
            estimated_tokens=16,
            content_sha256="hash1",
        ),
        CodeChunk(
            file_path="app/math/matrix.py",
            start_line=5,
            end_line=30,
            content="def multiply_matrices(a, b):\n    return [[sum(x*y for x,y in zip(r,c)) for c in zip(*b)] for r in a]",
            strategy=ChunkStrategy.SYMBOL_BASED,
            symbol_name="multiply_matrices",
            symbol_type="function",
            context_header="# File: app/math/matrix.py\n# Symbol: multiply_matrices\n",
            char_count=90,
            estimated_tokens=22,
            content_sha256="hash2",
        ),
    ]

    indexed_count = await service.index_chunks(fake_search_db, repo_id, chunks)  # type: ignore[arg-type]
    assert indexed_count == 2
    assert len(fake_search_db.chunks) == 2

    # Query for authentication
    results = await service.search(
        db=fake_search_db,  # type: ignore[arg-type]
        repository_id=repo_id,
        query="authenticate jwt user login",
        limit=5,
    )

    assert len(results) > 0
    top = results[0]

    # Acceptance Criteria verification: returns path + line range + score
    assert top.path == "app/auth/login.py"
    assert top.start_line == 10
    assert top.end_line == 25
    assert isinstance(top.score, float)
    assert top.score >= -1.0 and top.score <= 1.0

    # Rule 5 verification: source must be 'static'
    assert top.source == "static"


@pytest.mark.asyncio
async def test_search_endpoint_full_flow(fake_search_db: FakeSearchSession) -> None:
    """Tests GET /repositories/{id}/search endpoint end-to-end."""
    repo_id = uuid.uuid4()
    repo = Repository(
        id=repo_id,
        source="github",
        url="https://github.com/test/repo",
        full_name="test/repo",
        status="scanned",
    )
    fake_search_db.add(repo)

    provider = FakeEmbeddingProvider(dimension=16)
    service = SemanticSearchService(embedding_provider=provider)

    chunk = CodeChunk(
        file_path="app/main.py",
        start_line=1,
        end_line=15,
        content="def create_app():\n    return FastAPI()",
        strategy=ChunkStrategy.SYMBOL_BASED,
        symbol_name="create_app",
        symbol_type="function",
        context_header="# File: app/main.py\n",
        char_count=35,
        estimated_tokens=8,
        content_sha256="hash_main",
    )
    await service.index_chunks(fake_search_db, repo_id, [chunk])  # type: ignore[arg-type]

    app.dependency_overrides[get_db_session] = lambda: fake_search_db
    app.dependency_overrides[get_search_service] = lambda: service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Successful search
            resp = await client.get(f"/repositories/{repo_id}/search?q=FastAPI+app&limit=5")
            assert resp.status_code == 200
            data = resp.json()
            assert data["repository_id"] == str(repo_id)
            assert data["query"] == "FastAPI app"
            assert data["count"] == 1

            item = data["results"][0]
            # AC: returns path + line range + score
            assert item["path"] == "app/main.py"
            assert item["start_line"] == 1
            assert item["end_line"] == 15
            assert "score" in item
            # Rule 5: source labelled 'static'
            assert item["source"] == "static"

            # 2. Non-existent repo -> 404
            non_existent_id = uuid.uuid4()
            resp_404 = await client.get(f"/repositories/{non_existent_id}/search?q=anything")
            assert resp_404.status_code == 404

            # 3. Empty query -> 422
            resp_422 = await client.get(f"/repositories/{repo_id}/search?q=")
            assert resp_422.status_code == 422
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_search_score_filtering_and_limits(fake_search_db: FakeSearchSession) -> None:
    """Verifies that min_score filters results and limit caps returned count."""
    repo_id = uuid.uuid4()
    provider = FakeEmbeddingProvider(dimension=32)
    service = SemanticSearchService(embedding_provider=provider)

    chunks = [
        CodeChunk(
            file_path="app/math/calc.py",
            start_line=1,
            end_line=10,
            content="def add(a: int, b: int) -> int:\n    return a + b",
            strategy=ChunkStrategy.SYMBOL_BASED,
            symbol_name="add",
            char_count=30,
            estimated_tokens=7,
            content_sha256="c1",
        ),
        CodeChunk(
            file_path="app/math/advanced.py",
            start_line=1,
            end_line=20,
            content="def calculate_mean(values: list[float]) -> float:\n    return sum(values) / len(values)",
            strategy=ChunkStrategy.SYMBOL_BASED,
            symbol_name="calculate_mean",
            char_count=50,
            estimated_tokens=12,
            content_sha256="c2",
        ),
    ]

    await service.index_chunks(fake_search_db, repo_id, chunks)  # type: ignore[arg-type]

    # Limit = 1
    results_limit_1 = await service.search(
        db=fake_search_db,  # type: ignore[arg-type]
        repository_id=repo_id,
        query="calculate mean statistics",
        limit=1,
    )
    assert len(results_limit_1) == 1
    assert results_limit_1[0].symbol_name == "calculate_mean"

    # min_score = 0.99 (higher than any match) -> empty
    results_high_min = await service.search(
        db=fake_search_db,  # type: ignore[arg-type]
        repository_id=repo_id,
        query="calculate mean",
        min_score=0.99,
    )
    assert len(results_high_min) == 0


@pytest.mark.asyncio
async def test_search_service_idempotent_reindexing(fake_search_db: FakeSearchSession) -> None:
    """Reindexing a repository replaces previous chunks without duplication."""
    repo_id = uuid.uuid4()
    provider = FakeEmbeddingProvider(dimension=16)
    service = SemanticSearchService(embedding_provider=provider)

    chunk_v1 = CodeChunk(
        file_path="app/v1.py",
        start_line=1,
        end_line=5,
        content="def v1(): pass",
        strategy=ChunkStrategy.SYMBOL_BASED,
        char_count=14,
        estimated_tokens=3,
        content_sha256="v1",
    )
    chunk_v2 = CodeChunk(
        file_path="app/v2.py",
        start_line=1,
        end_line=5,
        content="def v2(): pass",
        strategy=ChunkStrategy.SYMBOL_BASED,
        char_count=14,
        estimated_tokens=3,
        content_sha256="v2",
    )

    await service.index_chunks(fake_search_db, repo_id, [chunk_v1])  # type: ignore[arg-type]
    assert len(fake_search_db.chunks) == 1

    # Reindex with chunk_v2
    await service.index_chunks(fake_search_db, repo_id, [chunk_v2])  # type: ignore[arg-type]
    assert len(fake_search_db.chunks) == 1
    assert next(iter(fake_search_db.chunks.values())).file_path == "app/v2.py"
