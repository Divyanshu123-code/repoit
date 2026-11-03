# Background Worker (`apps/worker`)

Background worker process powered by Redis (RQ or Arq) for long-running ingestion, parsing, embedding, and scanning pipelines.

## Responsibilities
- **Repository Ingestion (`scan_repo`)**:
  1. Fetch repository code (shallow clone or unpack zip) safely without code execution.
  2. Filter out binary files, vendor directories, minified/generated assets, and secret files (`.env`, private keys).
  3. Parse Python files using Tree-sitter into ASTs, extracting symbols (module, class, function), line ranges, and imports.
  4. Compute code metrics via Radon (LOC, cyclomatic complexity, Halstead metrics) and calculate fan-in / fan-out.
  5. Chunk source code by symbol boundaries with sliding window fallback, compute vector embeddings, and store them in PostgreSQL (`pgvector`).
  6. Construct the dependency/import graph (NetworkX) and persist graph edges.
  7. Run Ruff static analysis, normalize findings against the standard schema, and store results.
  8. Execute ML risk models to predict defect probabilities per module/symbol and store predictions with the model version.
  9. Record per-stage status checkpoints so interrupted scans can be diagnosed or resumed.

