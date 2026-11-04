"""Health and readiness check endpoints."""

from typing import Any

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.core.db import check_database_health

router = APIRouter(tags=["health"])


@router.get("/healthz", status_code=status.HTTP_200_OK)
async def healthz() -> dict[str, str]:
    """Liveness probe indicating whether the API process is alive."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz() -> JSONResponse:
    """Readiness probe verifying operational state, including database connectivity."""
    db_alive = await check_database_health()
    if not db_alive:
        payload: dict[str, Any] = {
            "status": "not_ready",
            "database": "unreachable",
        }
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=payload,
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "ready", "database": "connected"},
    )
