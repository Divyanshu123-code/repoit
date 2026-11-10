# Retrieval Evaluation Baseline (P2-04)

Generated automatically by `scripts/eval_retrieval.py`.

### Retrieval Evaluation Benchmark Results

| Metric | Score | Target | Status |
| :--- | :---: | :---: | :---: |
| **Recall@1** | 80.0% | ≥ 60.0% | ✅ Pass |
| **Recall@3** | 91.4% | ≥ 75.0% | ✅ Pass |
| **Recall@5** | 97.1% | ≥ 85.0% | ✅ Pass |
| **Recall@10** | 97.1% | ≥ 90.0% | ✅ Pass |
| **MRR (Mean Reciprocal Rank)** | 0.864 | ≥ 0.700 | ✅ Pass |
| **Average Latency** | 1.31 ms | ≤ 50.0 ms | ✅ Pass |

#### Performance by Category

| Category | Queries | Category MRR |
| :--- | :---: | :---: |
| `ai` | 3 | 0.833 |
| `api` | 3 | 1.000 |
| `auth` | 5 | 0.867 |
| `chunking` | 1 | 0.500 |
| `core` | 1 | 1.000 |
| `database` | 4 | 0.750 |
| `graph` | 3 | 1.000 |
| `ingestion` | 3 | 0.567 |
| `metrics` | 2 | 1.000 |
| `ml` | 3 | 1.000 |
| `parsing` | 2 | 1.000 |
| `security` | 1 | 1.000 |
| `static` | 1 | 1.000 |
| `worker` | 3 | 0.733 |

#### Detailed Query Breakdown

| ID | Query | Expected Target | Rank | RR | Latency |
| :--- | :--- | :--- | :---: | :---: | :---: |
| Q01 | How are JWT bearer tokens signed and created?... | `auth/jwt.py` | 3 | 0.33 | 1.7ms |
| Q02 | Validate and decode signature of incoming JWT... | `auth/jwt.py` | 1 | 1.00 | 1.4ms |
| Q03 | Bcrypt password hashing and salting... | `auth/password.py` | 1 | 1.00 | 1.3ms |
| Q04 | Verify plaintext password against bcrypt hash... | `auth/password.py` | 1 | 1.00 | 1.3ms |
| Q05 | FastAPI login endpoint credentials authentica... | `api/routes/auth.py` | 1 | 1.00 | 1.3ms |
| Q06 | Database engine initialization and async sess... | `database/connection.py` | 1 | 1.00 | 1.3ms |
| Q07 | Ping database connection health check... | `database/connection.py` | 1 | 1.00 | 1.3ms |
| Q08 | SQLAlchemy Base declarative model definition... | `database/models.py` | 1 | 1.00 | 1.2ms |
| Q09 | Repository and CodeChunk entity table schema... | `database/models.py` | — (>10) | 0.00 | 1.3ms |
| Q10 | Register a new public GitHub repository endpo... | `api/routes/repos.py` | 1 | 1.00 | 1.3ms |
| Q11 | Retrieve repository status and metrics detail... | `api/routes/repos.py` | 1 | 1.00 | 1.3ms |
| Q12 | Semantic code search API route query... | `api/routes/search.py` | 1 | 1.00 | 1.3ms |
| Q13 | Tree-sitter AST parser extracting Python func... | `parsing/treesitter.py` | 1 | 1.00 | 1.3ms |
| Q14 | Walk tree-sitter AST cursor collecting symbol... | `parsing/treesitter.py` | 1 | 1.00 | 1.3ms |
| Q15 | Compute radon cyclomatic complexity and maint... | `parsing/metrics.py` | 1 | 1.00 | 1.3ms |
| Q16 | Raw lines of code LOC and SLOC analysis... | `parsing/metrics.py` | 1 | 1.00 | 1.4ms |
| Q17 | Git shallow clone with depth 1 and hooks disa... | `repos/fetcher.py` | 1 | 1.00 | 1.4ms |
| Q18 | Filter out binary files and vendor dependenci... | `repos/filter.py` | 5 | 0.20 | 1.3ms |
| Q19 | Detect secret tokens and credentials in file ... | `repos/filter.py` | 2 | 0.50 | 1.3ms |
| Q20 | Symbol-aware code chunker preserving function... | `ai/chunker.py` | 2 | 0.50 | 1.3ms |
| Q21 | Vector embedding provider interface embed_tex... | `ai/embeddings.py` | 2 | 0.50 | 1.3ms |
| Q22 | OpenAI embedding batch REST API call... | `ai/embeddings.py` | 1 | 1.00 | 1.2ms |
| Q23 | RAG prompt formatting with source citations a... | `ai/rag_pipeline.py` | 1 | 1.00 | 1.3ms |
| Q24 | Background worker job for scanning repository... | `worker/tasks.py` | 1 | 1.00 | 1.3ms |
| Q25 | Periodic cleanup job for removing stale tempo... | `worker/scheduler.py` | 1 | 1.00 | 1.3ms |
| Q26 | Redis worker job queue and task dispatch... | `worker/tasks.py` | 5 | 0.20 | 1.3ms |
| Q27 | Predict probability of software defect risk u... | `ml/defect_predict.py` | 1 | 1.00 | 1.3ms |
| Q28 | Defect risk classifier model initialization... | `ml/defect_predict.py` | 1 | 1.00 | 1.3ms |
| Q29 | Extract code metric features into ML tensor v... | `ml/features.py` | 1 | 1.00 | 1.3ms |
| Q30 | Run ruff linter static code analysis with JSO... | `static/ruff_runner.py` | 1 | 1.00 | 1.3ms |
| Q31 | Build directed module import graph with Netwo... | `graph/networkx_graph.py` | 1 | 1.00 | 1.3ms |
| Q32 | Change impact analysis reverse reachability d... | `graph/impact.py` | 1 | 1.00 | 1.3ms |
| Q33 | Dependency graph fan-in and fan-out edges... | `graph/networkx_graph.py` | 1 | 1.00 | 1.4ms |
| Q34 | Structured JSON logging formatter with reques... | `core/logging.py` | 1 | 1.00 | 1.3ms |
| Q35 | Constant-time string comparison preventing ti... | `core/security.py` | 1 | 1.00 | 1.3ms |
