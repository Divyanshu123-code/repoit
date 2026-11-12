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
- [x] P1-02 Safe fetch (shallow clone into temp dir, size/time limits, no execution). AC: >limit repo fails gracefully.
- [x] P1-03 File filter (binaries, vendor, generated, secrets patterns, size cap). AC: unit tests with fixture repo.
- [x] P1-04 Tree-sitter parsing: symbols, imports, line ranges. AC: fixture repo extracts expected symbol list exactly.
- [x] P1-05 Metrics via radon + fan-in/out. AC: values match hand-computed fixtures.
- [x] P1-06 Worker job `scan_repo` with per-stage status + failure handling. AC: killed mid-scan -> status `failed` with reason; re-run works.
- [x] P1-07 UI: repo overview (tree, language stats, scan status). AC: shows scan progress live.

## Phase 2 — Semantic search & RAG (week 5–6)
- [x] P2-01 Chunker (symbol-based + window fallback). AC: chunks never split a function mid-body when it fits limit.
- [x] P2-02 EmbeddingProvider interface + 1 implementation + fake for tests.
- [x] P2-03 pgvector index + semantic search endpoint. AC: returns path + line range + score.
- [x] P2-04 Retrieval eval harness: 30–50 questions with expected files; report Recall@k, MRR. AC: script outputs a table; baseline stored in `docs/eval/`.
- [x] P2-05 RAG assistant with citations + abstention threshold. AC: unanswerable question yields "not enough evidence".
- [x] P2-06 Chat UI with expandable evidence panel.
- [x] P2-07 Compare 2 embedding models / chunk sizes using the eval harness; record decision.

## Phase 3 — ML defect prediction (week 7–8)
- [x] P3-01 Dataset notebook/script: inspect CM1/KC1 (docs, license, labels, imbalance, duplicates).
- [x] P3-02 Leakage-safe sklearn Pipeline + 5 models + CV. AC: results table for all models.
- [x] P3-03 Final test evaluation + SHAP + error analysis report (`docs/eval/ml_trackA.md` and `docs/eval/ml_model_comparison.md` detailing: (a) what each model did and how it was trained, (b) results across models, and (c) which model was best and why).
- [x] P3-04 Artifact export + `model_card.json` (dataset, version, metrics, limitations).
- [x] P3-05 Track B: mine Python repos (PyDriller), SZZ labelling, radon features; document labelling noise. AC: dataset v1 + datasheet.
- [x] P3-06 Track B training with project-wise split; compare vs Track A.
- [x] P3-07 Inference service + `ml_predictions` storage + risk UI with model version + limitations text.

## Phase 4 — Static analysis & graph (week 9)
- [x] P4-01 Ruff runner + normalised finding schema. AC: findings stored with rule, severity, line.
- [ ] P4-02 Import graph builder (NetworkX) + persisted edges.
- [ ] P4-03 Impact analysis (reverse reachability, depth limit). AC: controlled-change fixture returns expected set.
- [ ] P4-04 Graph UI (select node -> affected set) + findings table with triage filter.

## Phase 5 — AI debugging, tests, hardening (week 10–12)
- [ ] P5-01 Debug assistant: finding + code + graph context -> evidence vs hypothesis sections.
- [ ] P5-02 Test generation endpoint; stored as `generated_tests` with status `unvalidated`.
- [ ] P5-03 Docker sandbox runner (no network, limits) -> status `passed/failed/error`.
- [ ] P5-04 Security pass: secrets redaction, token handling review, dependency audit.
- [ ] P5-05 Integration + E2E tests (ingest -> search -> scan -> impact).
- [ ] P5-06 Deploy + demo repo + README + architecture diagram + evaluation report + resume bullets from measured numbers only.

## Cut line
If time runs short, cut in this order: P5-03 sandbox, P4-04 graph UI polish, P3-05/06 Track B. Never cut: eval harness, tests, citations.
