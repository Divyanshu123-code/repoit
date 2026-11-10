"""API router for repository registration and metadata endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.repos.scan_service import (
    get_latest_scan_for_repo,
    list_scans_for_repo,
    run_scan_pipeline,
)
from app.repos.schemas import (
    ErrorResponse,
    RepoRegisterRequest,
    RepoResponse,
    ScanResponse,
)
from app.repos.service import (
    InvalidRepoURLError,
    InvalidUploadError,
    get_repository_by_id,
    list_repositories,
    register_github_repository,
    register_zip_repository,
)

router = APIRouter(prefix="/repositories", tags=["repositories"])

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=RepoResponse,
    responses={
        422: {"model": ErrorResponse, "description": "Invalid repository URL or upload archive."},
        400: {"model": ErrorResponse, "description": "Missing registration input."},
    },
)
async def register_repository(
    payload: RepoRegisterRequest | None = None,
    session: DatabaseSession = None,  # type: ignore[assignment]
) -> RepoResponse:
    """Register a public GitHub repository via URL.

    Accepts JSON body: `{"url": "https://github.com/owner/repo"}`.
    """
    if not payload or not payload.url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "MISSING_URL",
                    "message": "A 'url' field is required in the request body.",
                }
            },
        )

    try:
        repo = await register_github_repository(session, payload.url)
        return RepoResponse.model_validate(repo)
    except InvalidRepoURLError as exc:
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "INVALID_REPOSITORY_URL", "message": str(exc)}},
        )  # type: ignore[return-value]


@router.post(
    "/upload",
    status_code=status.HTTP_201_CREATED,
    response_model=RepoResponse,
    responses={
        422: {"model": ErrorResponse, "description": "Invalid ZIP archive."},
    },
)
async def upload_repository_archive(
    file: Annotated[UploadFile, File(description="ZIP archive containing repository code")],
    session: DatabaseSession = None,  # type: ignore[assignment]
) -> RepoResponse:
    """Register a repository by uploading a ZIP archive."""
    filename = file.filename or "uploaded_repo.zip"
    content = await file.read()

    try:
        repo = await register_zip_repository(session, filename, content)
        return RepoResponse.model_validate(repo)
    except InvalidUploadError as exc:
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "INVALID_ARCHIVE_UPLOAD", "message": str(exc)}},
        )  # type: ignore[return-value]


@router.get("", response_model=list[RepoResponse])
async def get_all_repositories(
    session: DatabaseSession = None,  # type: ignore[assignment]
) -> list[RepoResponse]:
    """Retrieve all registered repositories."""
    repos = await list_repositories(session)
    return [RepoResponse.model_validate(r) for r in repos]


@router.get(
    "/{repo_id}",
    response_model=RepoResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Repository not found."},
    },
)
async def get_repository(
    repo_id: uuid.UUID,
    session: DatabaseSession = None,  # type: ignore[assignment]
) -> RepoResponse:
    """Retrieve details for a single repository by UUID."""
    repo = await get_repository_by_id(session, str(repo_id))
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "REPOSITORY_NOT_FOUND",
                    "message": f"Repository '{repo_id}' not found.",
                }
            },
        )
    return RepoResponse.model_validate(repo)


@router.post(
    "/{repo_id}/scan",
    response_model=ScanResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        404: {"model": ErrorResponse, "description": "Repository not found."},
    },
)
async def trigger_scan(
    repo_id: uuid.UUID,
    session: DatabaseSession = None,  # type: ignore[assignment]
) -> ScanResponse:
    """Trigger or re-run a background scan for the repository."""
    repo = await get_repository_by_id(session, str(repo_id))
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "REPOSITORY_NOT_FOUND",
                    "message": f"Repository '{repo_id}' not found.",
                }
            },
        )
    scan = await run_scan_pipeline(session, repo_id)
    return ScanResponse.model_validate(scan)


@router.get(
    "/{repo_id}/scan",
    response_model=ScanResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Scan or repository not found."},
    },
)
async def get_latest_scan(
    repo_id: uuid.UUID,
    session: DatabaseSession = None,  # type: ignore[assignment]
) -> ScanResponse:
    """Retrieve the latest scan execution for the repository."""
    scan = await get_latest_scan_for_repo(session, repo_id)
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "SCAN_NOT_FOUND",
                    "message": f"No scan found for repository '{repo_id}'.",
                }
            },
        )
    return ScanResponse.model_validate(scan)


@router.get(
    "/{repo_id}/scans",
    response_model=list[ScanResponse],
    responses={
        404: {"model": ErrorResponse, "description": "Repository not found."},
    },
)
async def get_all_scans(
    repo_id: uuid.UUID,
    session: DatabaseSession = None,  # type: ignore[assignment]
) -> list[ScanResponse]:
    """Retrieve all historical scan executions for the repository."""
    repo = await get_repository_by_id(session, str(repo_id))
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "REPOSITORY_NOT_FOUND",
                    "message": f"Repository '{repo_id}' not found.",
                }
            },
        )
    scans = await list_scans_for_repo(session, repo_id)
    return [ScanResponse.model_validate(s) for s in scans]
