"""FastAPI router for AI Test Generation (P5-02).

Endpoints:
    POST /repositories/{id}/tests/generate -> Generate and store test with status 'unvalidated'
    GET  /repositories/{id}/tests          -> List generated tests
    GET  /repositories/{id}/tests/{test_id} -> Get test details

Enforces:
    - Hard Rule 5: source labelled strictly as 'llm_generated'.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.repos.models import Repository
from app.tests_gen.schemas import (
    GeneratedTestListResponse,
    GeneratedTestResponse,
    GenerateTestRequest,
)
from app.tests_gen.service import TestGenerationService, get_test_generation_service

router = APIRouter(prefix="/repositories/{repository_id}/tests", tags=["tests"])

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
TestServiceDep = Annotated[TestGenerationService, Depends(get_test_generation_service)]


@router.post(
    "/generate",
    response_model=GeneratedTestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate and store pytest test case",
    description=(
        "Synthesizes a unit or regression test for a target file/symbol or static finding. "
        "Stored in generated_tests table with status 'unvalidated'. "
        "Complies with Hard Rule 5: source labelled strictly as 'llm_generated'."
    ),
)
async def generate_test_endpoint(
    repository_id: uuid.UUID,
    request: GenerateTestRequest,
    session: DatabaseSession = None,  # type: ignore[assignment]
    test_service: TestServiceDep = None,  # type: ignore[assignment]
) -> GeneratedTestResponse:
    """Generate pytest test case and store with status 'unvalidated'."""
    repo = await session.get(Repository, repository_id)
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with id '{repository_id}' not found",
        )

    test_record = await test_service.generate_and_store_test(
        session=session,
        repository_id=repository_id,
        request=request,
    )

    return test_service.to_response(test_record)


@router.get(
    "",
    response_model=GeneratedTestListResponse,
    status_code=status.HTTP_200_OK,
    summary="List generated tests for repository",
)
async def list_generated_tests_endpoint(
    repository_id: uuid.UUID,
    status_filter: Annotated[
        str | None,
        Query(alias="status", description="Filter by status (unvalidated, passed, failed, error)"),
    ] = None,
    target_file: Annotated[
        str | None,
        Query(description="Filter by target file path"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    session: DatabaseSession = None,  # type: ignore[assignment]
    test_service: TestServiceDep = None,  # type: ignore[assignment]
) -> GeneratedTestListResponse:
    """List all generated tests for a repository."""
    repo = await session.get(Repository, repository_id)
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with id '{repository_id}' not found",
        )

    return await test_service.list_tests(
        session=session,
        repository_id=repository_id,
        status_filter=status_filter,
        target_file=target_file,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{test_id}",
    response_model=GeneratedTestResponse,
    status_code=status.HTTP_200_OK,
    summary="Get single generated test details",
)
async def get_generated_test_endpoint(
    repository_id: uuid.UUID,
    test_id: uuid.UUID,
    session: DatabaseSession = None,  # type: ignore[assignment]
    test_service: TestServiceDep = None,  # type: ignore[assignment]
) -> GeneratedTestResponse:
    """Get single generated test by ID."""
    repo = await session.get(Repository, repository_id)
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with id '{repository_id}' not found",
        )

    test_record = await test_service.get_test(
        session=session,
        repository_id=repository_id,
        test_id=test_id,
    )
    if test_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generated test '{test_id}' not found in repository '{repository_id}'",
        )

    return test_service.to_response(test_record)
