# API Application (`apps/api`)

FastAPI REST API server handling authentication, repository metadata, scan lifecycle management, RAG querying, and analytical endpoints.

## Responsibilities
- **Authentication & Sessions**: User registration/login and session management.
- **Repository Management**: Repo registration (public GitHub URLs and uploaded zips) and metadata persistence.
- **Scan Orchestration**: Enqueueing ingestion and scan jobs to the background worker (`/repositories/{id}/scans`).
- **Query & RAG Endpoints**: Semantic search, vector similarity queries via pgvector, and contextual assistant chat with citation tracking.
- **Insights Endpoints**: Query interfaces for defect risk predictions, static findings, dependency graphs, and change-impact analysis.
- **Health Checks**: `/healthz` (liveness) and `/readyz` (readiness) endpoints.

## Backend Module Layout (`app/`)
- `core/`: Configuration (`pydantic-settings`), logging, security, and database session lifecycle.
- `auth/`: User sessions, credential handling, or OAuth integration.
- `repos/`: Repository metadata, ingestion boundaries, and path/content filtering.
- `parsing/`: Tree-sitter wrappers, symbol extraction (module/class/function), import extraction, and metric calculation.
- `indexing/`: Text chunking, embedding generation, and pgvector vector storage.
- `retrieval/`: Vector search, threshold-based filtering, and future hybrid reranking.
- `assistant/`: RAG orchestration, prompt templates, citation generation, and abstention on low confidence.
- `risk/`: Feature compilation, model artifact loading, and inference.
- `static/`: Ruff execution, finding schema normalization, and persistence.
- `graph/`: Import graph construction (NetworkX) and change-impact reachability queries.
- `tests_gen/`: Candidate test generation and execution in an isolated sandbox.
- `ai/providers/`: Swappable `EmbeddingProvider` and `LLMProvider` abstractions and vendor implementations.
- `api/`: Thin FastAPI router layer delegating to service interfaces.

