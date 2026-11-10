"""API endpoints for RAG code assistant (P2-05)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag_service import RAGAnswer, RAGService
from app.core.db import get_db_session
from app.repos.models import Repository

router = APIRouter(tags=["rag"])


class AskQuestionRequest(BaseModel):
    """Payload for asking the RAG assistant a question about a repository."""

    question: str = Field(min_length=1, max_length=1000, description="Natural language question")
    max_citations: int = Field(
        default=5, ge=1, le=20, description="Maximum number of evidence chunks"
    )
    min_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Optional minimum similarity score override"
    )


def get_rag_service() -> RAGService:
    """Dependency provider for RAGService."""
    return RAGService()


@router.post(
    "/repositories/{repository_id}/ask",
    response_model=RAGAnswer,
    status_code=status.HTTP_200_OK,
    summary="Ask a question about a repository with grounded code citations and abstention",
)
async def ask_repository_question(
    repository_id: uuid.UUID,
    payload: AskQuestionRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)] = ...,  # type: ignore[assignment]
    rag_service: Annotated[RAGService, Depends(get_rag_service)] = ...,  # type: ignore[assignment]
) -> RAGAnswer:
    """Query the RAG assistant about repository architecture or logic.

    Guarantees:
    - Answers grounded in codebase citations with line ranges.
    - Abstains with 'not enough evidence' when information is absent.
    - Results labelled by source (Rule 5: llm_generated answer, static citations).
    """
    # 1. Verify repository exists
    result = await db.execute(select(Repository).where(Repository.id == repository_id))
    repo = result.scalar_one_or_none()
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {repository_id} not found.",
        )

    # 2. Generate answer
    return await rag_service.answer_question(
        db=db,
        repository_id=repository_id,
        question=payload.question,
        max_citations=payload.max_citations,
        min_score=payload.min_score,
    )
