# RepoPilot AI — Architecture

## 1. Style
Modular monolith + background worker. One deployable API, one worker, one Postgres (pgvector), one Redis. Modules have strict boundaries so they can be split later; microservices now would add cost without benefit.

## 2. Components
| Component | Tech | Responsibility |
|---|---|---|
| Web | React + TS (Vite) | Repo overview, search, chat, risk table, findings, graph view |
| API | FastAPI | Auth, repo/scan/chat endpoints, job creation, read APIs |
| Worker | RQ or Arq + Redis | Ingestion, parsing, chunking, embedding, scans |
| DB | PostgreSQL + pgvector | Relational data + vectors |
| ML package | scikit-learn, XGBoost | Training/eval (offline) and inference (in API/worker) |
| AI layer | provider interfaces | Embeddings + LLM, swappable |

## 3. Backend module layout (`apps/api/app/`)
```
core/        config, logging, security, db session
auth/        sessions/OAuth
repos/       repository + file ingestion, filtering
parsing/     tree-sitter wrappers, symbol + metric extraction
indexing/    chunking, embeddings, pgvector store
retrieval/   semantic search, (later) hybrid + rerank
assistant/   RAG orchestration, prompts, citation builder, abstention
risk/        feature building, model loading, inference
static/      ruff runner + normaliser (finding schema)
graph/       import graph, impact analysis (NetworkX)
tests_gen/   test generation + (later) sandbox runner
ai/providers/  EmbeddingProvider, LLMProvider interfaces + implementations
api/         routers (thin) -> services
```
Rule: routers call services; services call repositories; modules talk through service interfaces only.

## 4. Pipelines
**Ingestion (worker job `scan_repo`)**
1. Fetch repo (shallow clone of public repo / uploaded zip) into temp dir, no code execution.
2. Filter: ignore binaries, vendored/generated dirs, large files, secrets patterns (`.env`, keys).
3. Parse `.py` with Tree-sitter -> files, symbols (module/class/function), imports, line ranges.
4. Compute metrics per function/module (LOC, cyclomatic complexity, Halstead via `radon`, fan-in/out).
5. Chunk by symbol (fallback: sliding window with overlap) -> embed -> store in pgvector.
6. Build import graph -> store edges.
7. Run Ruff -> normalise -> store findings.
8. Run risk model on compatible modules -> store predictions with model version.
9. Mark scan complete; every step records status so failed scans can resume/report.

**RAG query**
question -> embed -> top-k vector search (filtered by repo) -> assemble context (chunks + related findings + graph neighbours) -> LLM with "answer only from evidence" prompt -> answer + citations (file, line range). If retrieval score below threshold -> abstain with "not enough evidence".

## 5. ML design
- `packages/ml/` is a standalone, reproducible package: data loading, preprocessing pipeline, training, evaluation, report generation, artifact export (`joblib` + `model_card.json`).
- Track A: PROMISE/NASA (CM1 or KC1) baseline. Models: Dummy, LogReg, DecisionTree, RandomForest, XGBoost. Stratified CV, tuning on train only, test untouched until final.
- Track B: self-mined Python dataset (PyDriller + SZZ labelling; features via radon). Project-wise split. This is the model served to users once validated; Track A stays as documented baseline.
- Metrics: precision, recall, F1, ROC-AUC, PR-AUC, confusion matrix; SHAP for explanations.
- Serving: load artifact at startup; response includes `model_version`, `risk_probability`, `risk_band`, top contributing features.

## 6. Security
- Repo code is untrusted: parsing only, no execution; generated tests run only in a sandbox (Docker, no network, CPU/mem/time limits) — Phase 5.
- Tokens encrypted at rest, least-privilege scopes, revocable. MVP: public repos only.
- Secrets redaction before logs/prompts; opt-in before sending code to external providers.
- Retention: user can delete a repo and all derived data (cascade).

## 7. Observability
Structured JSON logs with request/scan IDs, `/healthz` + `/readyz`, per-stage scan timing, LLM latency/token logging (no content), basic metrics endpoint.

## 8. Environments
`docker compose up` runs web, api, worker, postgres(pgvector), redis. CI (GitHub Actions): lint, types, tests, build images.
