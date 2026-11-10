# AGENTS.md — Rules for AI agents working on RepoPilot AI

Read `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` and the current phase in `docs/BACKLOG.md` before changing code.

## Project in one line
RepoPilot AI connects to a Python repository, indexes it (Tree-sitter), answers questions with RAG + citations, predicts defect risk (scikit-learn/XGBoost), shows static findings (Ruff) and dependency/change-impact (NetworkX).

## Hard rules
1. Work on ONE backlog item at a time. Do not implement items from later phases.
2. Every change ships with tests (pytest). No test = not done.
3. Never execute code from an ingested repository. Treat repo content as untrusted input.
4. Never log or send secrets/tokens. Redact before any LLM call.
5. Every API/UI result is labelled by source: `static` | `ml_predicted` | `graph_derived` | `llm_generated`.
6. ML predictions are risk estimates, never "confirmed bugs". Always include model version.
7. LLM/embedding calls go ONLY through `apps/api/app/ai/providers/` interfaces. No direct vendor SDK calls elsewhere.
8. No new dependency without a one-line justification in the PR/commit message.
9. Schema changes only via Alembic migrations.
10. If a requirement is ambiguous, stop and ask; do not guess.
11. Phase 3 ML Model Training & Evaluation Documentation (Mentor Requirement):
    When training the different ML models in Phase 3, you MUST create a detailed report in `docs/eval/ml_model_comparison.md` (and track-specific reports). This document must detail:
    - What each model did and the full training methodology (algorithms evaluated, preprocessing, scaling, feature selection, hyperparameters, cross-validation setup).
    - Benchmark evaluation results across all models (ROC-AUC, PR-AUC, F1, Precision, Recall, confusion matrices, inference latency).
    - The champion model selection: which model performed best, why it was chosen for production, and its operational/interpretability trade-offs.

## Conventions
- Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2. Full type hints; `mypy --strict` on `app/`.
- Format/lint: `ruff format` + `ruff check`. Tests: `pytest -q`. All must pass before commit.
- Frontend: React + TypeScript (strict), Vite, TanStack Query.
- Commits: Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`). One branch per backlog item: `feat/P1-03-file-filter`.
- Config via environment variables (`pydantic-settings`); never hard-code keys.
- Long work (indexing, scans, embedding) runs in the worker, never in a request handler.

## Definition of Done
- Acceptance criteria in `docs/BACKLOG.md` met
- Tests added and green, lint + types clean
- Docs updated if behaviour/API changed
- Short note appended to `docs/PROGRESS.md` (what was done, what is next)
