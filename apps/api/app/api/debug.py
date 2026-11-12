"""FastAPI router for AI Debug Assistant (P5-01).

Correlates:
    Finding + Code Context + Graph Context
Into:
    Evidence (verified facts) vs Hypothesis (root causes, recommended fix, regression risks, verification plan).

Enforces Hard Rule 5: source labelled strictly as 'llm_generated'.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.debug_assistant import (
    DebugAnalysisRequest,
    DebugAnalysisResponse,
    DebugAssistantService,
    get_debug_assistant_service,
)
from app.core.db import get_db_session
from app.repos.models import Repository

router = APIRouter(prefix="/repositories/{repository_id}/debug", tags=["debug"])

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
DebugServiceDep = Annotated[DebugAssistantService, Depends(get_debug_assistant_service)]


@router.post(
    "",
    response_model=DebugAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze code finding with evidence vs hypothesis debug assistant",
    description=(
        "Correlates static findings, code context, and import graph context into strictly "
        "separated EVIDENCE (ground truth) and HYPOTHESIS (root causes, fixes, regression risks) sections. "
        "Enforces Hard Rule 5: results labelled by source."
    ),
)
async def analyze_debug_issue_endpoint(
    repository_id: uuid.UUID,
    request: DebugAnalysisRequest,
    session: DatabaseSession = None,  # type: ignore[assignment]
    debug_service: DebugServiceDep = None,  # type: ignore[assignment]
) -> DebugAnalysisResponse:
    """Execute AI debug investigation."""
    repo = await session.get(Repository, repository_id)
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with id '{repository_id}' not found",
        )

    return await debug_service.analyze_issue(
        session=session,
        repository_id=repository_id,
        request=request,
    )
