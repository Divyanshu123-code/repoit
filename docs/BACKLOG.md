# Backlog — phases, tasks, acceptance criteria

Status legend: [ ] todo, [~] in progress, [x] done. One task = one branch = one commit series.

## Phase 0 — Foundation (week 1–2)
- [x] P0-01 Monorepo scaffold (`apps/web`, `apps/api`, `apps/worker`, `packages/ml`, `docs`, `infra`). AC: tree matches ARCHITECTURE; README with run steps.
- [x] P0-02 Docker Compose: api, worker, web, postgres+pgvector, redis. AC: `docker compose up` brings all healthy; `/healthz` returns 200.
- [x] P0-03 FastAPI skeleton: settings, logging, DB session, Alembic init. AC: migration runs; pytest hits `/healthz`.
- [x] P0-04 CI (GitHub Actions): ruff, mypy, pytest, web build. AC: failing lint blocks merge.
- [x] P0-05 React + TS shell with routing + API client. AC: page shows API health.
- [x] P0-06 Lock open decisions in DECISIONS.md. AC: no "open" items remain.

## Phase 1 — Ingestion & parsing (week 3–4)
- [x] P1-01 Repo registration (public GitHub URL / zip upload) + `repositories` table. AC: invalid URL rejected with clear error.
- [ ] P1-02 Safe fetch (shallow clone into temp dir, size/time limits, no execution). AC: >limit repo fails gracefully.
- [ ] P1-03 File filter (binaries, vendor, generated, secrets patterns, size cap). AC: unit tests with fixture repo.
- [ ] P1-04 Tree-sitter parsing: symbols, imports, line ranges. AC: fixture repo extracts expected symbol list exactly.
- [ ] P1-05 Metrics via radon + fan-in/out. AC: values match hand-computed fixtures.
- [ ] P1-06 Worker job `scan_repo` with per-stage status + failure handling. AC: killed m
