"""Tests for RAG assistant with citations and abstention threshold (P2-05).

Acceptance Criteria:
- Unanswerable question yields "not enough evidence".
- Hard Rule 4: Never log or send secrets/tokens. Redact before any LLM call.
- Hard Rule 5: Labelled by source (llm_generated for answer, static for citations).
- Hard Rule 7: LLM/embedding calls go ONLY through app/ai/providers/.
"""

import uuid
from typing import Any

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.ai.providers import (
    FakeEmbeddingProvider,
    FakeLLMProvider,
    OpenAILLMProvider,
    get_llm_provider,
)
from app.ai.rag_service import RAGService
from app.api.rag import get_rag_service
from app.core.config import Settings
from app.core.db import get_db_session
from app.indexing.models import ChunkStrategy, CodeChunk, CodeChunkRecord
from app.indexing.search_service import SemanticSearchService
from app.main import app
from app.repos.models import Repository


class FakeRAGDbSession:
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

        if "delete" in stmt_str and "code_chunks" in stmt_str:
            self.chunks.clear()

            class FakeDelete:
                def all(self) -> list[Any]:
                    return []

            return FakeDelete()

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
def fake_rag_db() -> FakeRAGDbSession:
    return FakeRAGDbSession()


@pytest.mark.asyncio
async def test_openai_llm_provider_mock_transport() -> None:
    """Verifies OpenAILLMProvider chat requests and secret redaction (Hard Rule 4)."""
    captured_requests: list[httpx.Request] = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        data = {
            "choices": [
                {
                    "message": {
                        "content": "Authentication is handled by create_access_token in [auth/jwt.py:8-14]."
                    }
                }
            ]
        }
        return httpx.Response(200, json=data)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        llm = OpenAILLMProvider(
            api_key="sk-test-key",
            model_name="gpt-4o-mini",
            client=client,
        )

        messages = [
            {"role": "system", "content": "You are assistant."},
            {
                "role": "user",
                "content": "Here is token AKIAIOSFODNN7EXAMPLE and question about auth.",
            },
        ]
        completion = await llm.generate_completion(messages)

        assert "Authentication is handled" in completion
        assert len(captured_requests) == 1
        req = captured_requests[0]
        assert req.url == "https://api.openai.com/v1/chat/completions"
        assert req.headers["Authorization"] == "Bearer sk-test-key"

        import json

        body = json.loads(req.content.decode("utf-8"))
        # Hard Rule 4: Secret was scrubbed before network transmission
        user_msg = body["messages"][1]["content"]
        assert "AKIAIOSFODNN7EXAMPLE" not in user_msg
        assert "[REDACTED_AWS_KEY]" in user_msg


def test_get_llm_provider_factory() -> None:
    """Factory resolves LLMProvider according to configuration."""
    settings_fake = Settings(LLM_PROVIDER="fake", LLM_MODEL="gpt-4o-mini")
    llm_fake = get_llm_provider(settings=settings_fake)
    assert isinstance(llm_fake, FakeLLMProvider)
    assert llm_fake.model_name == "gpt-4o-mini"

    settings_no_key = Settings(LLM_PROVIDER="openai", OPENAI_API_KEY=None)
    with pytest.raises(ValueError, match="OPENAI_API_KEY environment variable is required"):
        get_llm_provider(settings=settings_no_key)

    settings_openai = Settings(
        LLM_PROVIDER="openai", OPENAI_API_KEY="sk-valid-key", LLM_MODEL="gpt-4o-mini"
    )
    llm_openai = get_llm_provider(settings=settings_openai)
    assert isinstance(llm_openai, OpenAILLMProvider)

    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        get_llm_provider("anthropic", settings=settings_fake)


@pytest.mark.asyncio
async def test_rag_service_abstention_when_no_evidence(fake_rag_db: FakeRAGDbSession) -> None:
    """AC: Unanswerable question yields 'not enough evidence'."""
    repo_id = uuid.uuid4()
    provider = FakeEmbeddingProvider(dimension=16)
    search_service = SemanticSearchService(embedding_provider=provider)
    llm = FakeLLMProvider()

    # Index unrelated chunk about linear algebra
    unrelated_chunk = CodeChunk(
        file_path="math/matrix.py",
        start_line=1,
        end_line=10,
        content="def determinant(m): return 1",
        strategy=ChunkStrategy.SYMBOL_BASED,
        char_count=29,
        estimated_tokens=7,
        content_sha256="m1",
    )
    await search_service.index_chunks(fake_rag_db, repo_id, [unrelated_chunk])  # type: ignore[arg-type]

    rag_service = RAGService(
        search_service=search_service,
        llm_provider=llm,
        abstention_threshold=0.5,
    )

    # Ask unanswerable question about Kubernetes deployment
    result = await rag_service.answer_question(
        db=fake_rag_db,  # type: ignore[arg-type]
        repository_id=repo_id,
        question="How to configure Kubernetes Helm chart replicas?",
    )

    # AC: Unanswerable question yields "not enough evidence"
    assert result.abstained is True
    assert "not enough evidence" in result.answer.lower()
    assert result.citations == []
    # Hard Rule 5: Labelled by source
    assert result.source == "llm_generated"


@pytest.mark.asyncio
async def test_rag_service_answerable_question_with_citations(
    fake_rag_db: FakeRAGDbSession,
) -> None:
    """Answerable question yields answer with verified citations and source metadata."""
    repo_id = uuid.uuid4()
    provider = FakeEmbeddingProvider(dimension=32)
    search_service = SemanticSearchService(embedding_provider=provider)
    llm = FakeLLMProvider()

    auth_chunk = CodeChunk(
        file_path="auth/jwt.py",
        start_line=8,
        end_line=14,
        content="def create_access_token(user_id: str) -> str:\n    return jwt.encode(payload, SECRET_KEY)",
        strategy=ChunkStrategy.SYMBOL_BASED,
        symbol_name="create_access_token",
        symbol_type="function",
        context_header="# File: auth/jwt.py\n# Symbol: create_access_token\n",
        char_count=85,
        estimated_tokens=21,
        content_sha256="jwt_hash",
    )
    await search_service.index_chunks(fake_rag_db, repo_id, [auth_chunk])  # type: ignore[arg-type]

    rag_service = RAGService(
        search_service=search_service,
        llm_provider=llm,
        abstention_threshold=0.0,
    )

    result = await rag_service.answer_question(
        db=fake_rag_db,  # type: ignore[arg-type]
        repository_id=repo_id,
        question="How does create_access_token sign JWT tokens in jwt.py?",
    )

    assert result.abstained is False
    assert "not enough evidence" not in result.answer.lower()
    assert len(result.citations) == 1

    citation = result.citations[0]
    assert citation.file_path == "auth/jwt.py"
    assert citation.start_line == 8
    assert citation.end_line == 14
    assert citation.symbol_name == "create_access_token"
    # Rule 5 check: citation source is 'static', answer source is 'llm_generated'
    assert citation.source == "static"
    assert result.source == "llm_generated"


@pytest.mark.asyncio
async def test_rag_api_endpoint_full_flow(fake_rag_db: FakeRAGDbSession) -> None:
    """Tests POST /repositories/{id}/ask endpoint end-to-end."""
    repo_id = uuid.uuid4()
    repo = Repository(
        id=repo_id,
        source="github",
        url="https://github.com/test/repo",
        full_name="test/repo",
        status="scanned",
    )
    fake_rag_db.add(repo)

    provider = FakeEmbeddingProvider(dimension=16)
    search_service = SemanticSearchService(embedding_provider=provider)
    llm = FakeLLMProvider()

    chunk = CodeChunk(
        file_path="app/config.py",
        start_line=1,
        end_line=10,
        content="class Settings(BaseSettings):\n    DATABASE_URL: str",
        strategy=ChunkStrategy.SYMBOL_BASED,
        symbol_name="Settings",
        context_header="# File: app/config.py\n",
        char_count=52,
        estimated_tokens=13,
        content_sha256="cfg_hash",
    )
    await search_service.index_chunks(fake_rag_db, repo_id, [chunk])  # type: ignore[arg-type]

    rag_service = RAGService(
        search_service=search_service,
        llm_provider=llm,
        abstention_threshold=0.0,
    )

    app.dependency_overrides[get_db_session] = lambda: fake_rag_db
    app.dependency_overrides[get_rag_service] = lambda: rag_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Answerable question -> 200
            resp = await client.post(
                f"/repositories/{repo_id}/ask",
                json={"question": "What is Settings in config.py?", "max_citations": 3},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["abstained"] is False
            assert data["source"] == "llm_generated"
            assert len(data["citations"]) >= 1
            assert data["citations"][0]["file_path"] == "app/config.py"
            assert data["citations"][0]["source"] == "static"

            # 2. Non-existent repo -> 404
            bad_id = uuid.uuid4()
            resp_404 = await client.post(
                f"/repositories/{bad_id}/ask",
                json={"question": "Any question?"},
            )
            assert resp_404.status_code == 404

            # 3. Empty question -> 422
            resp_422 = await client.post(
                f"/repositories/{repo_id}/ask",
                json={"question": ""},
            )
            assert resp_422.status_code == 422
    finally:
        app.dependency_overrides.clear()
