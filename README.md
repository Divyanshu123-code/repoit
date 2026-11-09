# RepoPilot AI

RepoPilot AI connects to a Python repository, indexes it (Tree-sitter), answers questions with RAG + citations, predicts defect risk (scikit-learn/XGBoost), shows static findings (Ruff) and dependency/change-impact (NetworkX).

## System Architecture

RepoPilot AI is designed as a modular monolith accompanied by a background worker service:

- **Web Frontend**: React + TypeScript (Vite) single-page application.
- **API Server**: FastAPI service handling requests, auth, metadata, and RAG chat.
- **Worker**: Redis-backed asynchronous worker for repository ingestion, AST parsing, metric calculation, embedding, and scanning.
- **Database**: PostgreSQL with `pgvector` extension for relational data and vector similarity search.
- **Message Broker & Queue**: Redis backing the task queue.
- **ML Package**: Standalone, reproducible scikit-learn / XGBoost training and evaluation pipeline.

---

## Folder Map

```
repopilot/
├── apps/
│   ├── api/          # FastAPI REST API (auth, scans, RAG, risk queries)
│   ├── web/          # React + TypeScript UI (file tree, chat, risk, graph)
│   └── worker/       # Asynchronous ingestion & scan worker (Tree-sitter, Ruff, ML)
├── packages/
│   └── ml/           # Defect prediction models, training pipelines, and evaluation
├── infra/            # Docker Compose orchestration and deployment configs
├── docs/             # Architecture, decisions, backlog, data model, and progress log
├── tests/            # Automated test suite (pytest)
├── .env.example      # Environment variables template
├── .gitignore        # Git ignore rules for Python, Node, macOS, data, and models
└── AGENTS.md         # Operational guidelines and hard rules for AI agents
```

### Component Directory Summaries

| Directory | Type | Purpose & Technologies |
|---|---|---|
| [`apps/web`](apps/web/) | Application | React 18, TypeScript, Vite, TanStack Query |
| [`apps/api`](apps/api/) | Application | FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2 |
| [`apps/worker`](apps/worker/) | Application | RQ or Arq + Redis, Tree-sitter, Radon |
| [`packages/ml`](packages/ml/) | Package | scikit-learn, XGBoost, SHAP, PyDriller |
| [`infra`](infra/) | Infrastructure | Docker Compose, Dockerfiles, Postgres+pgvector, Redis |
| [`docs`](docs/) | Documentation | Architecture, decisions, data models, progress |

---

## Getting Started & Run Steps

### Prerequisites
- Python 3.11+
- Node.js 18+ & npm
- Docker and Docker Compose

### 1. Environment Configuration
Copy the sample environment file and configure local values:
```bash
cp .env.example .env
```

### 2. Running with Docker Compose
Run the entire local stack with a single command:
```bash
docker compose up --build
```
This boots:
- API server on `http://localhost:8000` (Health check at `http://localhost:8000/healthz`)
- Web UI on `http://localhost:5173`
- PostgreSQL with pgvector on port `5432`
- Redis on port `6379`
- Background worker listening to Redis queue

### 3. Local Development (Alternative)

**API Backend:**
```bash
cd apps/api
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

**Worker:**
```bash
cd apps/worker
python -m worker.main
```

**Web Frontend:**
```bash
cd apps/web
npm install
npm run dev
```

---

## Documentation Links

- [Architecture Design](docs/ARCHITECTURE.md) — System boundaries, module breakdown, pipelines, security.
- [Project Backlog](docs/BACKLOG.md) — Phased milestones, acceptance criteria, cut line.
- [Decision Log](docs/DECISIONS.md) — Architecture Decision Records (ADRs).
- [Data Model & API](docs/DATA_MODEL_AND_API.md) — PostgreSQL schemas, pgvector indexes, REST endpoints.
- [Progress Log](docs/PROGRESS.md) — Changelog of completed tasks.
- [Agent Rules](AGENTS.md) — Rules and conventions for development.
