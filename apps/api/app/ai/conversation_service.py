"""Conversational repository intelligence service (ChatGPT for GitHub Repos).

Orchestrates multi-turn chat sessions with repository context injection,
semantic chunk retrieval, and grounded response synthesis.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.context_builder import build_repository_context
from app.ai.providers import LLMProvider, get_llm_provider
from app.ai.redaction import redact_secrets
from app.chat.models import ChatMessage, ChatSession
from app.indexing.models import SearchResultItem
from app.indexing.search_service import SemanticSearchService

logger = logging.getLogger("repopilot.ai.conversation")

CHATGPT_SYSTEM_PROMPT = """You are RepoPilot AI — the dedicated ChatGPT expert for this GitHub repository.
You have analyzed and indexed every single file, function, class, and metric in this codebase.

Your Core Identity & Strengths:
Unlike external tools that only skim high-level README files, you have granular visibility into every file, line, and dependency in this project.
Your purpose is to help the user understand the repository completely and assist with every single file or doubt they have.

Response Guidelines:
1. When asked to explain the project (e.g. "tell me about this project", "explain this repo", "overview", "what does this do"):
   - Executive Summary: Explain clearly what the project actually is and what it does in the real world based on its files and domain.
   - Comprehensive File-by-File Breakdown: Walk through the codebase layers (API/Routers, Business Services, Data Models, Core Config), explicitly naming key files and explaining their specific roles.
   - Core Architecture & Data Flow: Describe how user requests move through the system (e.g. Router -> Validation -> Service -> Database).
   - Code Health & Scale: Mention lines of code, complexity, and maintainability.
   - Open Door for File-Level Doubts: State clearly that the user can ask about ANY file or line, and you will walk through the exact code.
2. When asked about specific files, functions, or lines:
   - Provide a granular, code-level explanation referencing bracketed citations [file_path:start_line-end_line].
   - Clarify schemas, parameter validations, and interactions with other modules.
3. Defect risk predictions are statistical risk estimates from machine learning models, never confirmed bugs (Hard Rule 6).
4. Always structure your responses with clean, readable Markdown (headings, bold text, bullet points, and code blocks).
"""


class ConversationService:
    """Manages multi-turn conversation sessions and intelligent RAG synthesis."""

    def __init__(
        self,
        search_service: SemanticSearchService | None = None,
        llm_provider: LLMProvider | None = None,
    ) -> None:
        self.search_service = search_service or SemanticSearchService()
        self.llm = llm_provider or get_llm_provider()

    async def create_session(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
        title: str = "New Chat",
    ) -> ChatSession:
        """Create a new chat session for a repository."""
        chat_session = ChatSession(
            repository_id=repository_id,
            title=title,
        )
        session.add(chat_session)
        await session.commit()
        await session.refresh(chat_session)
        return chat_session

    async def list_sessions(
        self,
        session: AsyncSession,
        repository_id: uuid.UUID,
    ) -> list[ChatSession]:
        """List all chat sessions for a repository, ordered by updated_at descending."""
        stmt = (
            select(ChatSession)
            .where(ChatSession.repository_id == repository_id)
            .order_by(desc(ChatSession.updated_at))
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_session(
        self,
        session: AsyncSession,
        session_id: uuid.UUID,
    ) -> ChatSession | None:
        """Fetch a session with its messages."""
        from sqlalchemy.orm import selectinload

        stmt = (
            select(ChatSession)
            .options(selectinload(ChatSession.messages))
            .where(ChatSession.id == session_id)
            .execution_options(populate_existing=True)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_session(
        self,
        session: AsyncSession,
        session_id: uuid.UUID,
    ) -> bool:
        """Delete a chat session and associated messages."""
        chat_session = await self.get_session(session, session_id)
        if chat_session is None:
            return False
        await session.delete(chat_session)
        await session.commit()
        return True

    def _format_evidence(self, matches: list[SearchResultItem]) -> str:
        """Format retrieved code matches into an annotated context block."""
        blocks: list[str] = []
        for i, m in enumerate(matches, start=1):
            header = f"[{m.path}:{m.start_line}-{m.end_line}]"
            if m.symbol_name:
                header += f" (symbol: {m.symbol_name})"
            blocks.append(f"--- Code Evidence {i}: {header} ---\n{m.content}")
        return "\n\n".join(blocks)

    async def send_message(
        self,
        session: AsyncSession,
        session_id: uuid.UUID,
        user_text: str,
        max_citations: int = 5,
    ) -> tuple[ChatMessage, ChatMessage]:
        """Process user message in a multi-turn session and return (user_msg, assistant_msg)."""
        chat_session = await self.get_session(session, session_id)
        if chat_session is None:
            raise ValueError(f"Chat session {session_id} not found")

        clean_user_text = redact_secrets(user_text.strip())

        # 1. Update session title if first turn
        if chat_session.title == "New Chat":
            chat_session.title = clean_user_text[:50] + ("..." if len(clean_user_text) > 50 else "")

        # 2. Persist user turn
        user_message = ChatMessage(
            session_id=session_id,
            role="user",
            content=clean_user_text,
            source="user",
            model_version=self.llm.model_name,
        )
        session.add(user_message)
        await session.commit()
        await session.refresh(user_message)

        # 3. Retrieve rich repository profile & metrics
        repo_ctx = await build_repository_context(session, chat_session.repository_id)
        repo_summary = repo_ctx.format_summary_block()

        # 4. Semantic search for code chunks matching user query
        matches: list[SearchResultItem] = []
        try:
            matches = await self.search_service.search(
                db=session,
                repository_id=chat_session.repository_id,
                query=clean_user_text,
                limit=max_citations,
                min_score=0.0,
            )
        except Exception as search_err:  # noqa: BLE001
            logger.warning("Search failed during conversational turn: %s", search_err)

        evidence_str = (
            self._format_evidence(matches) if matches else "No direct code chunks matched."
        )

        # 5. Build conversation prompt sequence
        system_instruction = (
            f"{CHATGPT_SYSTEM_PROMPT}\n\n"
            f"=== VERIFIED REPOSITORY INTELLIGENCE ===\n"
            f"{repo_summary}\n\n"
            f"=== RETRIEVED CODE EXCERPTS ===\n"
            f"{evidence_str}\n"
        )

        messages_payload: list[dict[str, str]] = [
            {"role": "system", "content": redact_secrets(system_instruction)},
        ]

        # Append prior turns in session (up to last 8 turns for conversational memory)
        existing_history = chat_session.messages or []
        for past_msg in existing_history[-8:]:
            messages_payload.append(
                {
                    "role": past_msg.role,
                    "content": redact_secrets(past_msg.content),
                }
            )

        # Append current user prompt
        messages_payload.append(
            {
                "role": "user",
                "content": clean_user_text,
            }
        )

        # 6. Generate LLM completion
        raw_completion = await self.llm.generate_completion(messages_payload, temperature=0.2)

        # 7. Formulate structured citations
        citations_data: list[dict[str, Any]] = [
            {
                "file_path": m.path,
                "start_line": m.start_line,
                "end_line": m.end_line,
                "content": m.content,
                "symbol_name": m.symbol_name,
                "similarity_score": m.score,
                "source": "static",
            }
            for m in matches
        ]

        # 8. Check for abstention
        lower_comp = raw_completion.lower()
        is_abstained = (
            "not enough evidence" in lower_comp
            and "based on the codebase" not in lower_comp
            and len(matches) == 0
        )

        # 9. Persist assistant turn
        assistant_message = ChatMessage(
            session_id=session_id,
            role="assistant",
            content=raw_completion,
            abstained=is_abstained,
            citations=citations_data if not is_abstained else [],
            source="llm_generated",
            model_version=self.llm.model_name,
        )
        session.add(assistant_message)

        # Update session timestamp
        chat_session.updated_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(assistant_message)

        return user_message, assistant_message
