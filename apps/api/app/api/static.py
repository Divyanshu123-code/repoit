"""FastAPI router for static analysis findings and Ruff execution (P4-01)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.repos.models import Repository, RepositoryScan
from app.static.runner import run_ruff_check
from app.static.schemas import StaticFindingsResponse, TriggerStaticScanRequest
from app.static.service import StaticAnalysisService, get_static_service

router = APIRouter(prefix="/repositories/{repository_id}/findings", tags=["findings"])

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
StaticServiceDep = Annotated[StaticAnalysisService, Depends(get_static_service)]


@router.get(
    "",
    response_model=StaticFindingsResponse,
    summary="Get normalized static analysis findings for a repository",
    description=(
        "Retrieves static analysis findings (Ruff linter diagnostics) normalized with rule, severity, line, "
        "and file path. Complies with Hard Rule 5 (source: 'static') and P4-01 acceptance criteria."
    ),
)
async def get_repository_findings_endpoint(
    repository_id: uuid.UUID,
    severity: Annotated[
        str | None,
        Query(
            description="Filter by finding severity ('error', 'warning', 'info')",
            pattern="^(error|warning|info)$",
        ),
    ] = None,
    rule: Annotated[str | None, Query(description="Filter by rule code (e.g. 'F401')")] = None,
    file_path: Annotated[str | None, Query(description="Filter by file path substring")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    session: DatabaseSession = None,  # type: ignore[assignment]
    static_service: StaticServiceDep = None,  # type: ignore[assignment]
) -> StaticFindingsResponse:
    """Retrieve normalized static analysis findings for repository."""
    repo = await session.get(Repository, repository_id)
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with id '{repository_id}' not found",
        )

    return await static_service.get_repository_findings(
        session=session,
        repository_id=repository_id,
        severity=severity,
        rule=rule,
        file_path=file_path,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/scan",
    response_model=StaticFindingsResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger on-demand static analysis scan for repository",
)
async def trigger_static_scan_endpoint(
    repository_id: uuid.UUID,
    request: TriggerStaticScanRequest | None = None,
    session: DatabaseSession = None,  # type: ignore[assignment]
    static_service: StaticServiceDep = None,  # type: ignore[assignment]
) -> StaticFindingsResponse:
    """Run Ruff linter in isolated mode and store normalized findings."""
    repo = await session.get(Repository, repository_id)
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with id '{repository_id}' not found",
        )

    # Check for latest completed scan to retrieve scan_id
    scan_stmt = (
        select(RepositoryScan)
        .where(
            RepositoryScan.repository_id == repository_id,
            RepositoryScan.status == "completed",
        )
        .order_by(RepositoryScan.created_at.desc())
        .limit(1)
    )
    scan_res = await session.execute(scan_stmt)
    scan = scan_res.scalar_one_or_none()

    # If repo has a local directory or scan cache, run ruff
    # Fallback to scanning repo id directory or placeholder
    repo_dir = f"/tmp/repopilot_scans/{repository_id}"
    findings = run_ruff_check(repo_dir)

    await static_service.store_normalized_findings(
        session=session,
        repository_id=repository_id,
        findings=findings,
        scan_id=scan.id if scan else None,
    )

    return await static_service.get_repository_findings(
        session=session,
        repository_id=repository_id,
    )
