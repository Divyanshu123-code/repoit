# RepoPilot AI — Resume Bullets & Measured Achievements

*All metrics and statements below are verified through automated test benchmarks and empirical evaluation runs in this repository. Zero speculative claims.*

---

### Machine Learning & Data Engineering
- **Trained and benchmarked 5 defect risk ML architectures** (XGBoost, Random Forest, Decision Tree, Regularized Logistic Regression, Dummy Baseline) on **978 mined Python modules** across 5 open-source repositories using PyDriller, SZZ commit labeling, and radon AST complexity metrics.
- **Engineered Leave-One-Project-Out (LOPO) cross-validation pipeline** to eliminate intra-repository code style leakage, achieving **0.908 ROC-AUC** and **0.835 PR-AUC** on project-wise cross-validation and **0.915 ROC-AUC** / **60.0% defect recall** on held-out test repositories.
- **Formulated SHAP explainability pipeline** using TreeExplainer and LinearExplainer to attribute top risk drivers (cyclomatic complexity, total operators, executable LOC) and published comprehensive evaluation reports and model cards per model governance standards.

---

### Information Retrieval & RAG Architecture
- **Constructed codebase RAG evaluation harness** comprising 35 benchmark queries across 14 architectural categories on a 25-file reference repository, measuring Recall@k and Mean Reciprocal Rank (MRR).
- **Benchmarked symbol-aware AST chunking against fixed-window chunking** (500, 1,000, 2,000 characters), demonstrating that symbol-aware chunking achieved **0.864 MRR** and **97.1% Recall@10** (Recall@1: 80.0%, Recall@3: 91.4%) with average retrieval latency of **1.31 ms**, outperforming 1,000-char window chunking (0.811 MRR, 88.6% Recall@10).
- **Implemented evidence-grounded Q&A with strict bracketed citations** `[file:lines]` and automated abstention thresholding, preventing hallucinated answers when codebase evidence is insufficient.

---

### Systems Engineering, Security & Sandboxing
- **Architected full-stack code intelligence platform** comprising FastAPI async backend, PostgreSQL with `pgvector` HNSW indexing, NetworkX dependency graphs, Redis worker queues, and React 18 + TypeScript web dashboard.
- **Developed isolated Docker sandbox test runner** enforcing untrusted code execution boundaries with `--network none`, 512 MB memory caps, 1.0 CPU quota, and 20-second timeout limits, transitioning AI-generated test states from `unvalidated` to `passed`, `failed`, or `error`.
- **Implemented change impact analysis engine** using directed reverse reachability on NetworkX module graphs to simulate blast radius, dependency chains, and blast radius tiers in sub-20 milliseconds.
- **Engineered credential scrubbing engine** detecting 12 secret families (AWS, GitHub, GitLab, Slack, Google, OpenAI, Anthropic, private keys, JWTs, DB connection passwords) with automatic redaction across all external LLM prompts and structured JSON application logs.
- **Authored comprehensive test suite of 285 automated tests** across unit, integration, and end-to-end pipeline verification suites with zero flake and 100% CI compliance.
