# Data model & API contract (v0)

## Tables (PostgreSQL; `vector(DIM)` via pgvector)
```sql
users(id uuid pk, email text unique, created_at timestamptz)
repositories(id uuid pk, owner_user_id uuid fk, source text, url text, full_name text,
             default_branch text, status text, indexed_at timestamptz, created_at timestamptz)
scan_runs(id uuid pk, repository_id uuid fk, status text, stage text, error text,
          started_at timestamptz, completed_at timestamptz, tool_versions jsonb)
repository_files(id uuid pk, repository_id uuid fk, scan_run_id uuid fk, path text, language text,
                 content_hash text, size_bytes int, loc int)
symbols(id uuid pk, file_id uuid fk, kind text, name text, qualified_name text,
        start_line int, end_line int, metrics jsonb)
code_chunks(id uuid pk, file_id uuid fk, symbol_id uuid null fk, start_line int, end_line int,
            chunk_text text, token_count int, embedding vector(DIM), embedding_model text)
dependency_edges(id uuid pk, repository_id uuid fk, scan_run_id uuid fk,
                 source_file_id uuid, target_file_id uuid, edge_type text)
static_findings(id uuid pk, scan_run_id uuid fk, file_id uuid fk, rule_id text, severity text,
                message text, line_number int, tool text)
ml_predictions(id uuid pk, scan_run_id uuid fk, file_id uuid fk, symbol_id uuid null,
               model_version text, risk_probability real, risk_band text, top_features jsonb)
conversations(id uuid pk, user_id uuid fk, repository_id uuid fk, created_at timestamptz)
messages(id uuid pk, conversation_id uuid fk, role text, content text,
         citations jsonb, source_type text, created_at timestamptz)
generated_tests(id uuid pk, repository_id uuid fk, target_symbol_id uuid, test_content text,
                validation_status text, run_output text, created_at timestamptz)
model_versions(id text pk, track text, dataset text, metrics jsonb, artifact_path text, created_at timestamptz)
```
Indexes: `code_chunks` HNSW on `embedding` (cosine); btree on `(repository_id, path)`, `static_findings(scan_run_id, severity)`.
All repo-derived tables cascade-delete from `repositories`.

## Endpoints (REST, `/api/v1`)
| Method | Path | Purpose |
|---|---|---|
| GET | /healthz, /readyz | Health |
| POST | /repositories | Register repo `{url}` or upload zip |
| GET | /repositories, /repositories/{id} | List / detail + overview |
| DELETE | /repositories/{id} | Delete repo + derived data |
| POST | /repositories/{id}/scans | Start scan -> `{scan_id}` (202) |
| GET | /scans/{id} | Status, stage, error |
| GET | /repositories/{id}/files | Tree + per-file summary |
| POST | /repositories/{id}/search | `{query, k}` -> snippets w/ path, lines, score |
| POST | /repositories/{id}/chat | `{conversation_id?, question}` -> answer + citations + `source_type` |
| GET | /repositories/{id}/risk | Module risk list (model_version, probability, band) |
| GET | /repositories/{id}/findings | Static findings (filters: severity, rule, file) |
| GET | /repositories/{id}/graph | Nodes + edges |
| GET | /repositories/{id}/impact?file=...&depth=2 | Affected files (graph_derived) |
| POST | /repositories/{id}/tests | Generate candidate tests for symbol |
| POST | /tests/{id}/run | Run in sandbox (Phase 5) |

## Response conventions
- Errors: `{ "error": { "code": "...", "message": "..." } }`
- Every result item carries `source_type`: `static | ml_predicted | graph_derived | llm_generated`
- Chat citation: `{ "path": "...", "start_line": 10, "end_line": 42, "score": 0.81 }`
- Pagination: `?limit=&cursor=`
