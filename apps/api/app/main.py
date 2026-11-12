"""FastAPI application entrypoint for RepoPilot AI API."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.ml import router as ml_router
from app.api.rag import router as rag_router
from app.api.repos import router as repos_router
from app.api.search import router as search_router
from app.core.config import get_settings
from app.core.db import close_database
from app.core.logging import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for setup and teardown."""
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)
    logger.info(
        "Starting RepoPilot API",
        extra={"environment": settings.ENVIRONMENT, "debug": settings.DEBUG},
    )
    yield
    logger.info("Shutting down RepoPilot API")
    await close_database()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    settings = get_settings()
    application = FastAPI(
        title="RepoPilot AI API",
        description="FastAPI backend for code indexing, RAG, static analysis, and defect risk prediction",
        version="0.1.0",
        lifespan=lifespan,
        debug=settings.DEBUG,
    )

    # Health probes mounted at root
    application.include_router(health_router)

    # Repository endpoints mounted at root and /api/v1
    application.include_router(repos_router)
    application.include_router(repos_router, prefix="/api/v1")

    # Semantic search endpoints mounted at root and /api/v1
    application.include_router(search_router)
    application.include_router(search_router, prefix="/api/v1")

    # RAG assistant endpoints mounted at root and /api/v1
    application.include_router(rag_router)
    application.include_router(rag_router, prefix="/api/v1")

    # Defect risk ML endpoints mounted at root and /api/v1
    application.include_router(ml_router)
    application.include_router(ml_router, prefix="/api/v1")

    return application


app = create_app()
