# Decision Log (ADR-lite)

| # | Decision | Reason | Revisit when |
|---|---|---|---|
| 1 | Python-only MVP | Parsing, linting, ML metrics all strong in Python; one language done well | MVP complete |
| 2 | Modular monolith + worker | Small team, simpler deploy, clear module boundaries | Scale/team grows |
| 3 | PostgreSQL + pgvector (no separate vector DB) | One datastore, joins between vectors and metadata | >1M chunks or latency issues |
| 4 | Redis + RQ/Arq for jobs | Scans are long-running; keep requests fast | Need workflows/retries beyond basics |
| 5 | Provider-agnostic LLM/embedding interfaces | Swap vendors, mock in tests, control cost | — |
| 6 | Two ML tracks (PROMISE baseline, mined Python dataset) | NASA metrics don't transfer cleanly to Python; own dataset removes train/serve mismatch | Track B results available |
| 7 | Module/function-level risk, not commit-level (MVP) | Matches available labels; avoids false claims | After Track B |
| 8 | Public repos / zip upload only in MVP | Avoid private-code privacy + token risk | OAuth phase |
| 9 | Results labelled by source type | Transparency; static vs predicted vs generated | — |
| 10 | No execution of repo code during ingestion | Untrusted input | — |

## Open decisions (lock in Phase 0)
- LLM provider + embedding model (compare 2 on the retrieval eval set)
- Job queue: RQ (simpler) vs Arq (async)
- Auth: email/password vs GitHub OAuth login (login only, not repo access)
- Deployment target (Render/Fly/GCP/AWS)
