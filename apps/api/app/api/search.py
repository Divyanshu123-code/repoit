"""API endpoints for semantic code search (P2-03)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.indexing.models import SearchResponse
from app.indexing.search_service import SemanticSearchService
from app.repos.models import Repository

router = APIRouter(tags=["search"])


def get_search_service() -> SemanticSearchService:
    """Dependency provider for SemanticSearchService."""
    return SemanticSearchService()


@router.get(
    "/repositories/{repository_id}/search",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Semantic code search across indexed repository chunks",
)
async def search_repository_code(
    repository_id: uuid.UUID,
    q: Annotated[str, Query(min_length=1, description="Natural language or code query")],
    limit: Annotated[int, Query(ge=1, le=100, description="Max results")] = 10,
    min_score: Annotated[float, Query(ge=0.0, le=1.0, description="Min similarity score")] = 0.0,
    db: Annotated[AsyncSession, Depends(get_db_session)] = ...,  # type: ignore[assignment]
    search_service: Annotated[SemanticSearchService, Depends(get_search_service)] = ...,  # type: ignore[assignment]
) -> SearchResponse:
    """Perform semantic code search using pgvector embeddings and cosine similarity.

    Returns matching code chunks with:
    - path (file path)
    - start_line & end_line (line range)
    - score (cosine similarity)
    - source (Rule 5: labelled 'static')
    """
    # 1. Verify repository exists
    result = await db.execute(select(Repository).where(Repository.id == repository_id))
    repo = result.scalar_one_or_none()
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {repository_id} not found.",
        )

    # 2. Execute semantic search
    matches = await search_service.search(
        db=db,
        repository_id=repository_id,
        query=q,
        limit=limit,
        min_score=min_score,
    )

    return SearchResponse(
        repository_id=repository_id,
        query=q,
        count=len(matches),
        results=matches,
    )
