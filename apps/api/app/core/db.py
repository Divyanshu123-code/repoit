"""SQLAlchemy 2.x asynchronous database engine and session configuration."""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base declarative model class for SQLAlchemy 2.x."""


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_database_mode: str = "primary"


def get_engine() -> AsyncEngine:
    """Lazily initialize and return the global async database engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        db_url = settings.DATABASE_URL
        if db_url.startswith("sqlite"):
            _engine = create_async_engine(
                db_url,
                echo=settings.DEBUG,
            )
        else:
            _engine = create_async_engine(
                db_url,
                echo=settings.DEBUG,
                pool_pre_ping=True,
            )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the global async sessionmaker instance."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def init_database() -> None:
    """Initialize database connection, falling back to local SQLite if primary database is unreachable."""
    global _engine, _session_factory, _database_mode
    settings = get_settings()

    engine = get_engine()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        _database_mode = "primary"
        logger.info("Connected successfully to primary database (%s)", engine.url)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Primary database (%s) unreachable: %s. Activating local SQLite database fallback...",
            settings.DATABASE_URL,
            exc,
        )
        await close_database()
        fallback_url = "sqlite+aiosqlite:///repopilot.db"
        _engine = create_async_engine(fallback_url, echo=settings.DEBUG)
        _session_factory = async_sessionmaker(
            bind=_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        _database_mode = "sqlite_fallback"

    # Ensure tables exist when running on SQLite
    if _engine is not None and _engine.url.drivername.startswith("sqlite"):
        import app.auth.models
        import app.chat.models
        import app.graph.models
        import app.indexing.models
        import app.ml.models
        import app.repos.models
        import app.static.models
        import app.tests_gen.models  # noqa: F401

        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("SQLite database tables verified and initialized.")


def get_database_mode() -> str:
    """Return current database connection mode: 'primary' or 'sqlite_fallback'."""
    return _database_mode


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session per request."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


async def check_database_health() -> bool:
    """Execute a test query against the database to confirm reachability."""
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Database health check failed", extra={"error": str(exc)})
        return False


async def close_database() -> None:
    """Dispose of the global async database engine."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
