"""Repository scanning service orchestrating ingestion, filtering, parsing, and metrics (P1-06)."""

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.parsing import (
    RepoMetricsSummary,
    TreeSitterPythonParser,
    compute_repository_metrics,
)
from app.repos.fetcher import safe_fetch_repository
from app.repos.filter import RepoFileFilter, RepoFilterSummary
from app.repos.models import Repository, RepositoryScan

logger = logging.getLogger("repopilot.repos.scan")


class RepoNotFoundError(ValueError):
    """Raised when repository cannot be found in database."""


async def get_latest_scan_for_repo(
    session: AsyncSession, repo_id: uuid.UUID
) -> RepositoryScan | None:
    """Retrieve the most recent scan record for a given repository."""
    stmt = (
        select(RepositoryScan)
        .where(RepositoryScan.repository_id == repo_id)
        .order_by(desc(RepositoryScan.created_at))
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_scans_for_repo(session: AsyncSession, repo_id: uuid.UUID) -> list[RepositoryScan]:
    """Retrieve all scan records for a given repository."""
    stmt = (
        select(RepositoryScan)
        .where(RepositoryScan.repository_id == repo_id)
        .order_by(desc(RepositoryScan.created_at))
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_scan_record(session: AsyncSession, repo_id: uuid.UUID) -> RepositoryScan:
    """Create a new pending scan record and transition repo status to scanning."""
    scan = RepositoryScan(
        repository_id=repo_id,
        status="pending",
        current_stage="queued",
        stage_progress={"queued": {"timestamp": datetime.now(UTC).isoformat()}},
    )
    session.add(scan)
    await session.commit()
    await session.refresh(scan)
    return scan


async def run_scan_pipeline(
    session: AsyncSession,
    repo_id: uuid.UUID,
    zip_bytes: bytes | None = None,
    mock_kill_stage: str | None = None,
) -> RepositoryScan:
    """Execute the full repository scan pipeline with stage tracking and failure recovery.

    Stages:
    1. fetching: Safe shallow clone / ZIP unpack
    2. filtering: Prune binaries, vendor dirs, secrets, size limits
    3. parsing: Tree-sitter symbol, import, line range extraction
    4. metrics: LOC, cyclomatic complexity, Halstead, fan-in/fan-out
    5. completed: Persist summary and set repository status to ready

    Args:
        session: Database session
        repo_id: Target repository UUID
        zip_bytes: Raw ZIP archive bytes (if uploaded archive)
        mock_kill_stage: For testing, simulate mid-scan cancellation at this stage
    """
    # 1. Fetch Repository record
    stmt = select(Repository).where(Repository.id == repo_id)
    result = await session.execute(stmt)
    repo = result.scalar_one_or_none()
    if repo is None:
        raise RepoNotFoundError(f"Repository with id {repo_id} not found.")

    # 2. Create or initialize scan record
    scan = await create_scan_record(session, repo_id)
    repo.status = "scanning"
    scan.status = "in_progress"
    scan.started_at = datetime.now(UTC)
    stage_progress: dict[str, Any] = scan.stage_progress or {}
    await session.commit()

    try:
        # Check simulated cancellation
        if mock_kill_stage == "queued":
            raise asyncio.CancelledError("Simulated SIGTERM/kill mid-scan at queued")

        # STAGE 1: FETCHING
        scan.current_stage = "fetching"
        stage_progress["fetching"] = {"started_at": datetime.now(UTC).isoformat()}
        scan.stage_progress = stage_progress
        await session.commit()

        if mock_kill_stage == "fetching":
            raise asyncio.CancelledError("Simulated SIGTERM/kill mid-scan at fetching")

        source_type = "zip" if repo.source in ("upload", "zip") else "github"
        fetch_url = repo.url if source_type == "github" else None

        async with safe_fetch_repository(
            source_type=source_type,
            url=fetch_url,
            zip_bytes=zip_bytes,
        ) as fetched:
            stage_progress["fetching"]["completed_at"] = datetime.now(UTC).isoformat()
            stage_progress["fetching"]["size_bytes"] = fetched.size_bytes
            stage_progress["fetching"]["raw_file_count"] = fetched.file_count

            # STAGE 2: FILTERING
            scan.current_stage = "filtering"
            stage_progress["filtering"] = {"started_at": datetime.now(UTC).isoformat()}
            scan.stage_progress = stage_progress
            await session.commit()

            if mock_kill_stage == "filtering":
                raise asyncio.CancelledError("Simulated SIGTERM/kill mid-scan at filtering")

            file_filter = RepoFileFilter(allowed_extensions={".py"})
            filter_summary: RepoFilterSummary = file_filter.filter_repository(fetched.path)

            stage_progress["filtering"]["completed_at"] = datetime.now(UTC).isoformat()
            stage_progress["filtering"]["total_scanned"] = filter_summary.total_scanned
            stage_progress["filtering"]["accepted_files"] = len(filter_summary.accepted_files)
            stage_progress["filtering"]["skipped_files"] = len(filter_summary.skipped_files)

            # STAGE 3: PARSING
            scan.current_stage = "parsing"
            stage_progress["parsing"] = {"started_at": datetime.now(UTC).isoformat()}
            scan.stage_progress = stage_progress
            await session.commit()

            if mock_kill_stage == "parsing":
                raise asyncio.CancelledError("Simulated SIGTERM/kill mid-scan at parsing")

            parser = TreeSitterPythonParser()
            parsed_modules_code: dict[str, str] = {}
            parsed_modules_imports: dict[str, list[str]] = {}
            total_symbols_count = 0
            total_lines_count = 0

            for rel_file in filter_summary.accepted_files:
                full_file_path = fetched.path / rel_file
                try:
                    code_str = full_file_path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue

                parsed = parser.parse_source(code_str, file_path=rel_file)
                parsed_modules_code[rel_file.as_posix()] = code_str
                parsed_modules_imports[rel_file.as_posix()] = [imp.module for imp in parsed.imports]
                total_symbols_count += len(parsed.symbols)
                total_lines_count += parsed.total_lines

            stage_progress["parsing"]["completed_at"] = datetime.now(UTC).isoformat()
            stage_progress["parsing"]["parsed_files"] = len(parsed_modules_code)
            stage_progress["parsing"]["total_symbols"] = total_symbols_count

            # STAGE 4: METRICS
            scan.current_stage = "metrics"
            stage_progress["metrics"] = {"started_at": datetime.now(UTC).isoformat()}
            scan.stage_progress = stage_progress
            await session.commit()

            if mock_kill_stage == "metrics":
                raise asyncio.CancelledError("Simulated SIGTERM/kill mid-scan at metrics")

            metrics_summary: RepoMetricsSummary = compute_repository_metrics(
                modules_code=parsed_modules_code,
                modules_imports=parsed_modules_imports,
            )

            stage_progress["metrics"]["completed_at"] = datetime.now(UTC).isoformat()
            stage_progress["metrics"]["avg_cc"] = round(
                metrics_summary.avg_cyclomatic_complexity, 2
            )
            stage_progress["metrics"]["avg_mi"] = round(
                metrics_summary.avg_maintainability_index, 2
            )

            # STAGE 5: COMPLETED
            now = datetime.now(UTC)
            scan.current_stage = "completed"
            scan.status = "completed"
            scan.completed_at = now
            scan.file_count = len(parsed_modules_code)
            scan.total_lines = total_lines_count
            scan.total_symbols = total_symbols_count
            scan.metrics_summary = {
                "total_loc": metrics_summary.total_loc,
                "total_sloc": metrics_summary.total_sloc,
                "total_lloc": metrics_summary.total_lloc,
                "total_comments": metrics_summary.total_comments,
                "total_blank": metrics_summary.total_blank,
                "avg_complexity": round(metrics_summary.avg_cyclomatic_complexity, 2),
                "avg_maintainability_index": round(metrics_summary.avg_maintainability_index, 2),
                "modules_count": len(metrics_summary.modules),
                "modules": [
                    {
                        "path": m_path,
                        "loc": m.raw.loc,
                        "sloc": m.raw.sloc,
                        "complexity": m.cyclomatic_complexity,
                        "maintainability_index": round(m.maintainability_index, 1),
                        "functions_count": len(m.functions),
                        "fan_in": m.fan_in,
                        "fan_out": m.fan_out,
                    }
                    for m_path, m in metrics_summary.modules.items()
                ],
            }
            scan.stage_progress = stage_progress

            repo.status = "ready"
            repo.indexed_at = now

            # STAGE 5b: ML Defect Risk Inference (P3-07)
            try:
                from app.ml.inference_service import get_inference_service

                ml_service = get_inference_service()
                await ml_service.predict_and_store_for_modules(
                    session=session,
                    repository_id=repo_id,
                    modules_code=parsed_modules_code,
                    scan_id=scan.id,
                )
            except Exception as ml_err:  # noqa: BLE001
                logger.warning(
                    "ML defect risk inference during scan skipped for repo %s: %s",
                    repo_id,
                    ml_err,
                )

            # STAGE 5c: Static Analysis Findings via Ruff (P4-01)
            try:
                from app.static.service import get_static_service

                static_service = get_static_service()
                await static_service.run_and_store_findings(
                    session=session,
                    repository_id=repo_id,
                    repo_path=fetched.path,
                    scan_id=scan.id,
                )
            except Exception as static_err:  # noqa: BLE001
                logger.warning(
                    "Static analysis during scan skipped for repo %s: %s",
                    repo_id,
                    static_err,
                )

            await session.commit()
            await session.refresh(scan)
            logger.info("Scan completed successfully for repo %s (scan_id=%s)", repo_id, scan.id)
            return scan

    except asyncio.CancelledError as cancel_exc:
        # Gracefully record mid-scan termination/kill
        stage_name = scan.current_stage
        error_msg = f"Scan aborted: killed mid-scan at stage '{stage_name}' ({cancel_exc})"
        logger.warning(error_msg)

        scan.status = "failed"
        scan.current_stage = "failed"
        scan.error_message = error_msg
        scan.completed_at = datetime.now(UTC)
        repo.status = "failed"

        try:
            await session.commit()
            await session.refresh(scan)
        except (SQLAlchemyError, OSError) as db_exc:
            logger.warning("Failed to persist cancelled scan state: %s", db_exc)
        raise

    except Exception as exc:
        # Gracefully record failure with specific reason
        stage_name = scan.current_stage
        error_msg = f"Scan failed at stage '{stage_name}': {exc}"
        logger.exception(error_msg)

        scan.status = "failed"
        scan.current_stage = "failed"
        scan.error_message = error_msg
        scan.completed_at = datetime.now(UTC)
        repo.status = "failed"

        try:
            await session.commit()
            await session.refresh(scan)
        except (SQLAlchemyError, OSError) as db_exc:
            logger.warning("Failed to persist failed scan state: %s", db_exc)
        return scan
