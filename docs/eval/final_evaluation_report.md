# RepoPilot AI — Comprehensive Evaluation & Benchmark Report (P5-06)

**Date**: 2026-11-14  
**Scope**: Full empirical assessment across Ingestion, Retrieval RAG, Machine Learning Defect Modeling, Static & Graph Impact Analysis, and Sandboxed Test Execution.

---

## 1. Executive Benchmark Summary

| Evaluation Track | Benchmark Target | Baseline Metric | RepoPilot AI Champion | Net Gain / Advantage |
| :--- | :--- | :--- | :--- | :--- |
| **Retrieval Evaluation** (Phase 2) | 35-query benchmark across 14 categories | Windowed 1,000-char: MRR 0.811, Recall@10 88.6% | **Symbol-Aware 1,500-char: MRR 0.864, Recall@10 97.1%** | **+6.5% MRR, +8.5% Recall@10**, 1.31 ms query latency |
| **Track A: Defect Modeling** (Phase 3) | NASA PROMISE (KC1, CM1) 21 static metrics | Dummy baseline: ROC-AUC 0.500, PR-AUC 0.155 | **KC1 Random Forest: ROC-AUC 0.820, PR-AUC 0.486** | **76.9% defect recall** (50/65 defects captured) |
| **Track B: Modern Python** (Phase 3) | 978 modules mined across 5 open-source repos | Zero-shot Track A model on Python | **XGBoost & Random Forest LOPO: ROC-AUC 0.908, PR-AUC 0.835** | **0.915 ROC-AUC, 60.0% recall** on held-out test repositories |
| **Change Impact Analysis** (Phase 4) | Multi-tier dependency graph traversal | Manual code search | **NetworkX BFS Reverse Reachability** | Sub-20 ms blast radius calculation with exact path chains |
| **AI Debug Assistant** (Phase 5) | Diagnostic explanation & fix generation | Unstructured chat prompts | **Structured Evidence vs Hypothesis Separation** | 100% secret redaction, caller regression risk analysis |
| **Docker Sandbox Runner** (Phase 5) | Untrusted test execution | Host process execution (unsafe) | **Constrained Container Runner** | `--network none`, 512MB RAM, 1 CPU, 20s timeout |

---

## 2. Phase 2: Code Retrieval & RAG Benchmark

Detailed in `docs/eval/embedding_chunk_comparison.md` and `docs/eval/retrieval_baseline.md`:

### 2.1 Retrieval Experiment Configuration
- **Dataset**: 35 hand-curated questions across 14 domains (`auth`, `database`, `api`, `parsing`, `metrics`, `ingestion`, `chunking`, `ai`, `worker`, `ml`, `static`, `graph`, `core`, `security`) evaluated on a reference codebase.
- **Metric Definitions**:
  - **Recall@k**: Fraction of queries where at least one ground-truth file is retrieved within top $k$ items.
  - **MRR (Mean Reciprocal Rank)**: $\frac{1}{|Q|} \sum_{i=1}^{|Q|} \frac{1}{\text{rank}_i}$ of the first relevant document.

### 2.2 Results Matrix

| Strategy | Chunk Size | Overlap | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR | Latency (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Fixed Window | 500 chars | 50 chars | 74.3% | 85.7% | 88.6% | 91.4% | 0.803 | 1.12 |
| Fixed Window | 1,000 chars | 100 chars | 77.1% | 85.7% | 88.6% | 88.6% | 0.811 | 1.18 |
| Fixed Window | 2,000 chars | 200 chars | 71.4% | 82.9% | 85.7% | 91.4% | 0.774 | 1.25 |
| **Symbol-Aware (Champion)** | **1,500 chars** | **Symbol Body** | **80.0%** | **91.4%** | **94.3%** | **97.1%** | **0.864** | **1.31** |

**Conclusion**: Symbol-aware chunking keeps AST definitions atomic, preventing mid-function splits and delivering superior semantic signal for code retrieval.

---

## 3. Phase 3: Machine Learning Defect Prediction

Detailed in `docs/eval/ml_model_comparison.md`, `docs/eval/ml_trackA.md`, and `docs/eval/ml_trackB.md`:

### 3.1 Dataset Composition & Mining
- **Track A Baseline**: NASA PROMISE benchmark (CM1: 498 modules, 9.84% defect rate; KC1: 2,109 modules, 15.46% defect rate; 21 static McCabe/Halstead features).
- **Track B Modern Python**: 978 Python modules mined across 5 open-source repositories (`repoit`, `flask`, `requests`, `urllib3`, `fastapi`) via PyDriller, SZZ commit back-tracing, and radon AST extraction (11.7% defect rate, 7.58:1 class imbalance).

### 3.2 Track B Leave-One-Project-Out (LOPO) Model Comparison

| Model Architecture | Scaler / Preprocessing | Mean ROC-AUC | Mean PR-AUC | Mean F1 | Defect Recall | Out-of-Fold Latency |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Dummy (Most Frequent) | None | 0.500 | 0.117 | 0.000 | 0.0% | 0.02 ms |
| Logistic Regression | RobustScaler + Class Weights | 0.887 | 0.792 | 0.774 | 81.3% | 0.12 ms |
| Decision Tree | RobustScaler | 0.812 | 0.710 | 0.742 | 75.0% | 0.08 ms |
| **Random Forest** | RobustScaler + Balanced | **0.907** | **0.833** | **0.809** | **82.6%** | **0.85 ms** |
| **Gradient Boosting / XGBoost** | RobustScaler | **0.908** | **0.835** | **0.801** | **80.4%** | **0.78 ms** |

### 3.3 Held-Out Multi-Project Generalization Test
Trained on `flask`, `requests`, and `urllib3`; tested on completely unseen projects `fastapi` and `repoit`:
- **ROC-AUC**: **0.915**
- **PR-AUC**: **0.694**
- **Defect Recall**: **60.0%**
- **Top SHAP Attributions**: Lines of executable code (`lOCode`), cyclomatic complexity (`v(g)`), and total operators (`n`).

---

## 4. Phase 4: Import Graph & Change Impact

- **Graph Topology**: Module dependencies parsed using Tree-sitter import extraction and represented as directed NetworkX graphs ($A \to B$ for $A$ imports $B$).
- **Impact Simulation**: Reverse reachability algorithm with BFS traversal attributing shortest paths and blast radius counts.
- **Performance**: Traversal across interconnected codebases completes in **< 20 ms**, categorized into direct (depth 1) and transitive (depth $\ge 2$) tiers.

---

## 5. Phase 5: AI Debug Assistant & Sandboxed Execution

- **AI Debug Assistant**: Generates structured reports separating verified `EVIDENCE` (`source: static` / `graph_derived`) from AI `HYPOTHESIS` (`source: llm_generated`), preventing hallucinated diagnoses from being conflated with static facts.
- **Docker Sandbox Runner**:
  - Enforces Hard Rule 3: repo code is untrusted.
  - Limits: `--network none`, `--memory 512m`, `--cpus 1.0`, `--security-opt no-new-privileges:true`, read-only workspace, 20s timeout.
  - Deterministic status transitions: exit code 0 $\rightarrow$ `passed`, exit code 1 $\rightarrow$ `failed`, timeout/exit > 1 $\rightarrow$ `error`.
- **Security & Redaction Engine**: 12-pattern credential scrubber applied across all LLM messages, search queries, and structured JSON logs.

---

## 6. Verification & Test Metrics

- **Total Passing Automated Tests**: **285 tests** (142 root verification tests + 143 backend API/unit tests).
- **Code Quality**:
  - `ruff format`: 100% compliant.
  - `ruff check`: Clean (0 warnings or errors).
  - `mypy --strict app`: Clean (0 issues across 64 source files).
  - Web frontend: Production TypeScript and Vite builds passing cleanly.
