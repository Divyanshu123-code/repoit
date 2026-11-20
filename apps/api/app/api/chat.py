"""API endpoints for multi-turn repository chat assistant (ChatGPT for GitHub Repos).

Enforces:
- Hard Rule 5: Labelled by source ('llm_generated' for assistant, 'user' for user).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.conversation_service import ConversationService
from app.core.db import get_db_session
from app.repos.models import Repository

router = APIRouter(tags=["chat"])


class CreateSessionRequest(BaseModel):
    """Payload for creating a new chat session."""

    title: str = Field(default="New Chat", max_length=256)


class SendMessageRequest(BaseModel):
    """Payload for sending a user message in a chat session."""

    content: str = Field(min_length=1, max_length=4000, description="User prompt or question")
    max_citations: int = Field(default=5, ge=1, le=20)


class ChatMessageResponse(BaseModel):
    """Structured response for an individual chat message."""

    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    abstained: bool
    citations: list[dict[str, Any]]
    source: str
    model_version: str
    created_at: datetime


class ChatSessionResponse(BaseModel):
    """Structured response for a chat session."""

    id: uuid.UUID
    repository_id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessageResponse] = Field(default_factory=list)


def get_conversation_service() -> ConversationService:
    """Dependency provider for ConversationService."""
    return ConversationService()


@router.post(
    "/repositories/{repository_id}/chat/sessions",
    response_model=ChatSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new conversation session for a repository",
)
async def create_chat_session(
    repository_id: uuid.UUID,
    payload: CreateSessionRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> ChatSessionResponse:
    """Initialize a stateful conversational session with repository context."""
    repo = (
        await db.execute(select(Repository).where(Repository.id == repository_id))
    ).scalar_one_or_none()
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {repository_id} not found.",
        )

    chat_session = await service.create_session(db, repository_id, title=payload.title)
    return ChatSessionResponse(
        id=chat_session.id,
        repository_id=chat_session.repository_id,
        title=chat_session.title,
        created_at=chat_session.created_at,
        updated_at=chat_session.updated_at,
        messages=[],
    )


@router.get(
    "/repositories/{repository_id}/chat/sessions",
    response_model=list[ChatSessionResponse],
    status_code=status.HTTP_200_OK,
    summary="List all conversation sessions for a repository",
)
async def list_chat_sessions(
    repository_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> list[ChatSessionResponse]:
    """Retrieve chat sessions for a repository, ordered by updated_at descending."""
    sessions = await service.list_sessions(db, repository_id)
    return [
        ChatSessionResponse(
            id=s.id,
            repository_id=s.repository_id,
            title=s.title,
            created_at=s.created_at,
            updated_at=s.updated_at,
            messages=[],
        )
        for s in sessions
    ]


@router.get(
    "/repositories/{repository_id}/chat/sessions/{session_id}",
    response_model=ChatSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get conversation session details with full message history",
)
async def get_chat_session(
    repository_id: uuid.UUID,
    session_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> ChatSessionResponse:
    """Retrieve an active chat session and its full message history."""
    chat_session = await service.get_session(db, session_id)
    if chat_session is None or chat_session.repository_id != repository_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session {session_id} not found for repository {repository_id}.",
        )

    messages = [
        ChatMessageResponse(
            id=m.id,
            session_id=m.session_id,
            role=m.role,
            content=m.content,
            abstained=m.abstained,
            citations=m.citations,
            source=m.source,
            model_version=m.model_version,
            created_at=m.created_at,
        )
        for m in chat_session.messages
    ]

    return ChatSessionResponse(
        id=chat_session.id,
        repository_id=chat_session.repository_id,
        title=chat_session.title,
        created_at=chat_session.created_at,
        updated_at=chat_session.updated_at,
        messages=messages,
    )


@router.post(
    "/repositories/{repository_id}/chat/sessions/{session_id}/messages",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Send a message in a conversation session and receive grounded AI response",
)
async def send_chat_message(
    repository_id: uuid.UUID,
    session_id: uuid.UUID,
    payload: SendMessageRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> ChatMessageResponse:
    """Process a user conversational turn and generate a grounded, multi-turn AI response."""
    chat_session = await service.get_session(db, session_id)
    if chat_session is None or chat_session.repository_id != repository_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session {session_id} not found for repository {repository_id}.",
        )

    _, assistant_msg = await service.send_message(
        session=db,
        session_id=session_id,
        user_text=payload.content,
        max_citations=payload.max_citations,
    )

    return ChatMessageResponse(
        id=assistant_msg.id,
        session_id=assistant_msg.session_id,
        role=assistant_msg.role,
        content=assistant_msg.content,
        abstained=assistant_msg.abstained,
        citations=assistant_msg.citations,
        source=assistant_msg.source,
        model_version=assistant_msg.model_version,
        created_at=assistant_msg.created_at,
    )


@router.delete(
    "/repositories/{repository_id}/chat/sessions/{session_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a conversation session",
)
async def delete_chat_session(
    repository_id: uuid.UUID,
    session_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> dict[str, str]:
    """Permanently delete a chat session and all contained messages."""
    deleted = await service.delete_session(db, session_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session {session_id} not found.",
        )
    return {"status": "deleted", "session_id": str(session_id)}
