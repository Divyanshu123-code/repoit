# Decision Log (ADR-lite)

| # | Decision | Reason | Revisit when |
|---|---|---|---|
| 1 | Python-only MVP | Parsing, linting, ML metrics all strong in Python; one language done well | MVP complete |
| 2 | Modular monolith + worker | Small team, simpler deploy, clear module boundaries | Scale/team grows |
| 3 | PostgreSQL + pgvector (no separate vector DB) | One datastore, joins between vectors and metadata | >1M chunks or latency issues |
| 4 | Redis + Arq for jobs | Scans are long-running; keep requests fast; native `asyncio` compatibility | Need workflows/retries beyond basics |
| 5 | Provider-agnostic LLM/embedding interfaces | Swap vendors, mock in tests, control cost | — |
| 6 | Two ML tracks (PROMISE baseline, mined Python dataset) | NASA metrics don't transfer cleanly to Python; own dataset removes train/serve mismatch | Track B results available |
| 7 | Module/function-level risk, not commit-level (MVP) | Matches available labels; avoids false claims | After Track B |
| 8 | Public repos / zip upload only in MVP | Avoid private-code privacy + token risk | OAuth phase |
| 9 | Results labelled by source type | Transparency; static vs predicted vs generated | — |
| 10 | No execution of repo code during ingestion | Untrusted input | — |
| 11 | LLM: OpenAI `gpt-4o-mini`, Embeddings: `text-embedding-3-small` (1536-dim) | Cost-effective baseline, reliable structured JSON output, low latency; swappable provider interface | Phase 2 eval harness comparison (P2-07) |
| 12 | Job queue: Arq (asyncio-native Redis queue) | Native `asyncio` integration with FastAPI and asyncpg; avoids thread blocking for I/O tasks | Complex DAG workflows required (e.g. Temporal) |
| 13 | Auth: Email + Session/JWT (with GitHub OAuth login-only in Phase 1+) | Clean user model for public repo indexing; avoids requesting sensitive private repo scopes | Ingestion of private repositories is required |
| 14 | Deployment target: Docker multi-container runner (Render / Fly.io / GCP Cloud Run) | Reuses local `docker-compose.yml` multi-container architecture for API, worker, web, postgres, and redis | Enterprise VPC / multi-region scaling required |

## Locked decisions (Phase 0 complete)
All open decisions for Phase 0 have been locked. No open items remain. Future decisions must be proposed via pull requests and recorded in the table above.
