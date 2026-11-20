"""Unit and integration tests for conversational repository intelligence (ChatGPT for GitHub Repos)."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.ai.context_builder import build_repository_context
from app.ai.conversation_service import ConversationService
from app.ai.providers.fake_llm import FakeLLMProvider
from app.core.db import Base, get_db_session
from app.main import app
from app.repos.models import Repository, RepositoryScan


@pytest.fixture
async def async_test_db() -> AsyncSession:
    """In-memory SQLite async test database with all models registered."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        import app.auth.models
        import app.chat.models
        import app.graph.models
        import app.indexing.models
        import app.ml.models
        import app.repos.models
        import app.static.models
        import app.tests_gen.models  # noqa: F401

        await conn.run_sync(Base.metadata.create_all)

    session_factory = sessionmaker(  # type: ignore[call-overload]
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session


@pytest.mark.asyncio
async def test_context_builder_summary(async_test_db: AsyncSession) -> None:
    """Verify build_repository_context extracts scan metrics into structured text."""
    repo_id = uuid.uuid4()
    repo = Repository(
        id=repo_id,
        source="github",
        url="https://github.com/test/repo",
        full_name="test/repo",
        default_branch="main",
        status="ready",
    )
    async_test_db.add(repo)

    scan = RepositoryScan(
        repository_id=repo_id,
        status="completed",
        current_stage="completed",
        file_count=10,
        total_lines=1500,
        total_symbols=45,
        metrics_summary={
            "total_loc": 1500,
            "total_sloc": 1200,
            "avg_complexity": 3.5,
            "avg_maintainability_index": 78.0,
            "modules": [
                {
                    "path": "app/core.py",
                    "loc": 500,
                    "complexity": 12,
                    "maintainability_index": 70.0,
                },
                {
                    "path": "app/utils.py",
                    "loc": 200,
                    "complexity": 4,
                    "maintainability_index": 85.0,
                },
            ],
        },
    )
    async_test_db.add(scan)
    await async_test_db.commit()

    ctx = await build_repository_context(async_test_db, repo_id)
    summary = ctx.format_summary_block()

    assert "test/repo" in summary
    assert "1500 lines of code" in summary
    assert "app/core.py" in summary
    assert "500 LOC" in summary


@pytest.mark.asyncio
async def test_conversation_service_multi_turn(async_test_db: AsyncSession) -> None:
    """Verify ConversationService handles multi-turn conversation and updates titles."""
    repo_id = uuid.uuid4()
    repo = Repository(
        id=repo_id,
        source="github",
        url="https://github.com/test/repo",
        full_name="test/repo",
        default_branch="main",
        status="ready",
    )
    async_test_db.add(repo)
    await async_test_db.commit()

    fake_llm = FakeLLMProvider()
    conv_service = ConversationService(llm_provider=fake_llm)

    # 1. Create session
    chat_sess = await conv_service.create_session(async_test_db, repo_id)
    assert chat_sess.title == "New Chat"

    # 2. First turn
    user_msg1, asst_msg1 = await conv_service.send_message(
        session=async_test_db,
        session_id=chat_sess.id,
        user_text="What is the purpose of this project?",
    )
    assert user_msg1.role == "user"
    assert asst_msg1.role == "assistant"
    assert "Repository Purpose" in asst_msg1.content
    assert asst_msg1.source == "llm_generated"

    # Check title auto-update
    loaded_sess = await conv_service.get_session(async_test_db, chat_sess.id)
    assert loaded_sess is not None
    assert "What is the purpose" in loaded_sess.title

    # 3. Second turn (multi-turn memory)
    user_msg2, asst_msg2 = await conv_service.send_message(
        session=async_test_db,
        session_id=chat_sess.id,
        user_text="Tell me the file with most lines of code",
    )
    assert user_msg2.role == "user"
    assert asst_msg2.role == "assistant"
    assert asst_msg2.source == "llm_generated"

    # Verify message sequence in DB
    refreshed = await conv_service.get_session(async_test_db, chat_sess.id)
    assert refreshed is not None
    assert len(refreshed.messages) == 4


@pytest.mark.asyncio
async def test_chat_api_endpoints(async_test_db: AsyncSession) -> None:
    """Verify FastAPI chat session and messaging endpoints."""
    repo_id = uuid.uuid4()
    repo = Repository(
        id=repo_id,
        source="github",
        url="https://github.com/test/repo",
        full_name="test/repo",
        default_branch="main",
        status="ready",
    )
    async_test_db.add(repo)
    await async_test_db.commit()

    async def override_get_db() -> AsyncSession:
        return async_test_db

    app.dependency_overrides[get_db_session] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Create chat session
            res_create = await client.post(
                f"/repositories/{repo_id}/chat/sessions",
                json={"title": "Custom Investigation"},
            )
            assert res_create.status_code == 201
            data = res_create.json()
            session_id = data["id"]
            assert data["title"] == "Custom Investigation"

            # 2. List sessions
            res_list = await client.get(f"/repositories/{repo_id}/chat/sessions")
            assert res_list.status_code == 200
            assert len(res_list.json()) == 1

            # 3. Post a message
            res_msg = await client.post(
                f"/repositories/{repo_id}/chat/sessions/{session_id}/messages",
                json={"content": "What is the purpose of this project?"},
            )
            assert res_msg.status_code == 200
            msg_data = res_msg.json()
            assert msg_data["role"] == "assistant"
            assert msg_data["source"] == "llm_generated"
            assert "RepoPilot AI" in msg_data["content"]

            # 4. Get session with history
            res_get = await client.get(f"/repositories/{repo_id}/chat/sessions/{session_id}")
            assert res_get.status_code == 200
            session_data = res_get.json()
            assert len(session_data["messages"]) == 2  # user + assistant

            # 5. Delete session
            res_del = await client.delete(f"/repositories/{repo_id}/chat/sessions/{session_id}")
            assert res_del.status_code == 200
            assert res_del.json()["status"] == "deleted"

            # Verify deleted
            res_get_deleted = await client.get(
                f"/repositories/{repo_id}/chat/sessions/{session_id}"
            )
            assert res_get_deleted.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db_session, None)
